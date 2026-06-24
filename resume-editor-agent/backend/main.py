"""Resume Editor Agent — FastAPI server with agent loop + SSE streaming."""
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(override=True)

# ── Logging ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"resume-editor-agent.{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ],
)
logger = logging.getLogger("resume-editor-agent")

# ── Registry setup ─────────────────────────────────────────────────────
from .subagent import SubagentRegistry
from .subagents import (
    GapAnalysisSubagent,
    AssessmentSubagent,
    RemediationSubagent,
    RewriteSubagent,
    CompanyAnalysisSubagent,
)
from .coordinator import Coordinator
from .hooks import HOOKS
from .task_manager import TaskManager
from .subagent import call_llm as _call_llm

registry = SubagentRegistry()
registry.register(GapAnalysisSubagent())
registry.register(AssessmentSubagent())
registry.register(RemediationSubagent())
registry.register(RewriteSubagent())
registry.register(CompanyAnalysisSubagent())
coordinator = Coordinator(registry)
task_manager = TaskManager()

from .memory_manager import MemoryManager

memory_mgr = MemoryManager()

HOOKS.register("pre_subagent", lambda step, inputs, ctx: {
    **inputs,
    "user_profile": memory_mgr.get_profile(),
})

# ── Hook registrations ────────────────────────────────────────────────────

HOOKS.register("post_subagent", lambda step, result, ctx: (
    logger.info("[hook] Subagent %s completed: %d chars, truncated=%s",
                step["id"], len(result.get("text", "")), result.get("truncated"))
))

HOOKS.register("on_all_done", lambda cache, metadata: (
    logger.info("[hook] All done: %d completed steps: %s",
                len(metadata.get("completed_steps", [])),
                metadata.get("completed_steps"))
))

HOOKS.register("on_error", lambda step_id, error, ctx: (
    logger.warning("[hook] Step %s error: %s", step_id, error[:100])
))

logger.info("Registered %d hook handlers", sum(len(v) for v in HOOKS._hooks.values()))

# ── App ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("Resume Editor Agent starting")
    logger.info("Registry: %s", [a.id for a in registry.list_all()])
    logger.info("Models: %s", os.getenv("MODEL_ID", "NOT SET"))
    logger.info("Log file: %s", log_file)
    logger.info("Listening on http://0.0.0.0:%s", os.getenv("PORT", "8001"))
    logger.info("=" * 50)
    yield


app = FastAPI(title="Resume Editor Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/agent")
async def run_agent(
    resume_text: str = Form(...),
    jd_text: str = Form(...),
    goal: str = Form(""),
    model_id: str = Form("deepseek-v4-flash"),
):
    """Start an agent run. Returns SSE stream with plan + execution events."""
    run_id = uuid.uuid4().hex[:12]
    req_start = time.time()
    logger.info(
        "AGENT RUN START | run_id=%s resume=%dchars jd=%dchars goal=%s",
        run_id, len(resume_text), len(jd_text), goal or "(none)",
    )
    # Log actual input content (truncated) for debugging traceability
    logger.info("AGENT INPUT | run_id=%s resume_head=%.500s", run_id, resume_text.strip())
    logger.info("AGENT INPUT | run_id=%s jd_head=%.500s", run_id, jd_text.strip())
    if goal:
        logger.info("AGENT INPUT | run_id=%s goal=%s", run_id, goal.strip())

    async def event_stream():
        try:
            # 1. Plan — stream LLM thinking then emit final steps
            steps: list[dict] | None = None
            plan_done = False
            async for event in coordinator.plan_stream(resume_text, jd_text, goal, model_id):
                event["run_id"] = run_id
                event_type = event.pop("type", "event")
                if event_type == "plan":
                    steps = event.get("steps")
                    plan_done = True
                    logger.info(
                        "PLAN COMPLETE | run_id=%s steps=%s elapsed=%.1fs",
                        run_id, [s["id"] for s in (steps or [])],
                        time.time() - req_start,
                    )
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

            if not steps:
                raise RuntimeError("Plan did not return any steps")

            # Save plan
            if task_manager:
                try:
                    task_manager.save_plan(run_id, {"steps": steps})
                except Exception as e:
                    logger.warning("Failed to save plan: %s", e)

            logger.info("EXEC START | run_id=%s plan_steps=%s", run_id, [s["id"] for s in steps])

            # 2. Execute — 2-phase: compile prompts (fast) then infer LLM (streaming)
            async for event in coordinator.execute(steps, resume_text, jd_text, goal, run_id, model_id):
                e_run_id = event.get("run_id", run_id)
                event["run_id"] = e_run_id
                event_type = event.pop("type", "event")

                # Named events keep their SSE type; unnamed data events for streaming
                if event_type in ("step_output", "step_error"):
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception("AGENT RUN ERROR | run_id=%s", run_id)
            yield f"event: error\ndata: {json.dumps({'run_id': run_id, 'error': str(e)[:500]})}\n\n"
        finally:
            total = time.time() - req_start
            logger.info("AGENT RUN END | run_id=%s total=%.1fs", run_id, total)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/intercept")
async def intercept_step(
    run_id: str = Form(...),
    step_id: str = Form(...),
    feedback: str = Form(...),
    model_id: str = Form("deepseek-v4-flash"),
):
    """User intercept: re-run a completed subagent with feedback."""
    logger.info("Intercept: run_id=%s step_id=%s feedback=%s", run_id, step_id, feedback[:80])

    HOOKS.fire("on_intercept", run_id, step_id, feedback)

    agent = registry.get(step_id)
    if not agent:
        raise HTTPException(400, f"Unknown subagent: {step_id}")

    async def re_run_stream():
        try:
            previous = None
            if task_manager:
                previous = task_manager.get_result(run_id, step_id)

            bundle = await agent.run(
                inputs={},
                emit=lambda data: None,
                feedback=feedback,
                previous_result=previous,
            )

            # Call LLM with the compiled prompt bundle
            text, thinking, truncated = await _call_llm(
                system=bundle.system,
                prompt=bundle.prompt,
                max_tokens=bundle.max_tokens,
                step_id=step_id,
                model_id=model_id,
            )
            result = {"text": text, "thinking": thinking, "truncated": truncated}

            if task_manager:
                task_manager.save_result(run_id, step_id, result)

            yield f"event: step_revised\ndata: {json.dumps({'run_id': run_id, 'step_id': step_id, **result})}\n\n"
        except Exception as e:
            logger.error("Intercept re-run failed: %s", str(e)[:200])
            yield f"event: error\ndata: {json.dumps({'run_id': run_id, 'error': str(e)[:200]})}\n\n"

    return StreamingResponse(
        re_run_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "registry": [a.id for a in registry.list_all()],
        "registry_size": len(registry.list_all()),
    }

@app.get("/api/models")
async def list_models():
    """Return available model options for the frontend model selector."""
    return {
        "models": [
            {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash (default)"},
            {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro"},
            {"id": "deepseek-v3-0324", "name": "DeepSeek V3"},
            {"id": "deepseek-r1-0528", "name": "DeepSeek R1"},
        ]
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")), log_config=None)
