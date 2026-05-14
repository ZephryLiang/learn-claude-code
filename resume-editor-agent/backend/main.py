"""Resume Editor Agent — FastAPI server with agent loop + SSE streaming."""
import json
import logging
import os
import sys
import uuid
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
from .subagents import GapAnalysisSubagent
from .coordinator import Coordinator
from .hooks import HOOKS

registry = SubagentRegistry()
registry.register(GapAnalysisSubagent())
coordinator = Coordinator(registry)
task_manager = None  # Will be set when task_manager module is ready

# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="Resume Editor Agent")

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
):
    """Start an agent run. Returns SSE stream with plan + execution events."""
    run_id = uuid.uuid4().hex[:12]
    logger.info("Agent run started: run_id=%s goal=%s", run_id, goal[:100])

    async def event_stream():
        try:
            # 1. Plan
            steps = await coordinator.plan(resume_text, jd_text, goal)

            # Save plan if task manager available
            if task_manager:
                task_manager.save_plan(run_id, {"steps": steps})

            yield f"event: plan\ndata: {json.dumps({'run_id': run_id, 'steps': steps})}\n\n"

            # 2. Execute
            async for event in coordinator.execute(steps, resume_text, jd_text, goal):
                event["run_id"] = run_id
                event_type = event.pop("type", "event")

                if event_type in ("step_output", "step_error"):
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception("Agent run failed: run_id=%s", run_id)
            yield f"event: error\ndata: {json.dumps({'run_id': run_id, 'error': str(e)[:500]})}\n\n"

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

            result = await agent.run(
                inputs={},
                emit=lambda data: None,
                feedback=feedback,
                previous_result=previous,
            )

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


@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("Resume Editor Agent starting")
    logger.info("Registry: %s", [a.id for a in registry.list_all()])
    logger.info("Models: %s", os.getenv("MODEL_ID", "NOT SET"))
    logger.info("Log file: %s", log_file)
    logger.info("Listening on http://0.0.0.0:8001")
    logger.info("=" * 50)


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_config=None)
