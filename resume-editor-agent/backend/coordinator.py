"""Coordinator agent loop: plans execution, spawns subagents, emits events."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import time
from typing import AsyncIterator

from anthropic import AsyncAnthropic
from .subagent import SubagentRegistry, call_llm, PromptBundle
from .hooks import HOOKS
from .task_manager import TaskManager
from .memory_manager import MemoryManager

logger = logging.getLogger("resume-editor.coordinator")

_FALLBACK_PLAN_STEPS: list[dict] = [
    {"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []},
    {"id": "assessment", "name": "匹配评估", "icon": "🎯", "deps": []},
    {"id": "company_analysis", "name": "公司尽调", "icon": "🏢", "deps": []},
    {"id": "remediation", "name": "补足路线", "icon": "📋", "deps": ["gap_analysis"]},
    {"id": "rewrite", "name": "故事改写", "icon": "✏️", "deps": ["gap_analysis", "assessment"]},
]
_FALLBACK_REASONING = "根据简历和岗位要求，选择差距分析、匹配评估、公司尽调并行执行；补足路线基于差距分析；故事改写基于匹配评估和差距分析的结果进行。"


def _group_by_deps(steps: list[dict]) -> list[list[dict]]:
    """Topological sort: group steps by dependency depth for level-parallel execution.

    Returns list of levels, where each level's steps can run in parallel.
    """
    deps: dict[str, set] = {}
    for s in steps:
        raw = s.get("deps", []) or []
        deps[s["id"]] = set(raw)

    depths: dict[str, int] = {}

    def calc_depth(step_id: str) -> int:
        if step_id in depths:
            return depths[step_id]
        if not deps.get(step_id):
            depths[step_id] = 0
            return 0
        max_d = max((calc_depth(d) for d in deps[step_id]), default=-1) + 1
        depths[step_id] = max_d
        return max_d

    for s in steps:
        calc_depth(s["id"])

    max_depth = max(depths.values()) if depths else 0
    levels: list[list[dict]] = [[] for _ in range(max_depth + 1)]
    for s in steps:
        levels[depths[s["id"]]].append(s)
    return levels


class Coordinator:
    """Agent loop: plan -> compile prompts (parallel) -> infer LLM (parallel per deps level)."""

    def __init__(self, registry: SubagentRegistry):
        self.registry = registry
        self.task_manager = TaskManager()
        self.memory = MemoryManager()

    async def plan(self, resume_text: str, jd_text: str, goal: str = "") -> tuple[list[dict], str]:
        """Ask LLM to select and order subagents from registry.

        Returns (steps, reasoning).
        Steps have: id, name, icon, deps
        Each step's system prompt is compiled dynamically by the subagent's run().
        """
        model_id = os.getenv("MODEL_ID", "").strip()
        if not model_id:
            raise RuntimeError("MODEL_ID is not set in environment")

        user_context = self.memory.get_recent_context()

        available = self.registry.list_all()
        agent_descriptions = "\n".join(
            f"- `{a.id}` ({a.name}): {a.description} | inputs={a.inputs}"
            for a in available
        )

        system = f"""You are a resume analysis coordinator.

Available subagents (use these exact IDs — never make up IDs):
{agent_descriptions}

{user_context}

Analyze the user's resume, job description, and goal to decide:
1. Which subagents to run (ONLY relevant ones — skip unnecessary ones)
2. In what order (set "deps" to reflect dependencies)

Rules:
- gap_analysis and assessment are independent (no deps)
- company_analysis is independent (no deps)
- remediation depends on gap_analysis
- rewrite depends on gap_analysis + assessment

CRITICAL: Every "id" must be one of: {', '.join(a.id for a in available)}
Do NOT use invented IDs or numbers like "1", "2".

Respond with raw JSON only (no markdown):
{{"steps": [{{"id": "...", "name": "...", "icon": "...", "deps": []}}], "reasoning": "your analysis here"}}

Explain WHY you chose each subagent based on the user's specific input."""

        prompt = f"Resume length: {len(resume_text)} chars, JD length: {len(jd_text)} chars"
        if goal:
            prompt += f"\nUser goal: {goal}"

        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )

        try:
            resp = await client.messages.create(
                model=model_id,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
        except Exception as e:
            logger.error("Planning API call failed: %s", str(e)[:200])
            return _FALLBACK_PLAN_STEPS, _FALLBACK_REASONING

        text = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return _FALLBACK_PLAN_STEPS, _FALLBACK_REASONING

        try:
            data = json.loads(match.group())
            steps = data.get("steps", _FALLBACK_PLAN_STEPS)
            reasoning = data.get("reasoning", _FALLBACK_REASONING)
            return steps, reasoning
        except (json.JSONDecodeError, KeyError):
            return _FALLBACK_PLAN_STEPS, _FALLBACK_REASONING

    async def plan_stream(self, resume_text: str, jd_text: str, goal: str = "", model_id: str | None = None) -> AsyncIterator[dict]:
        """Stream planning phase. Yields events as the LLM thinks.

        Yields:
          plan_start       -> immediately, signals thinking has begun
          plan_thinking    -> each LLM token as it arrives
          plan_done        -> LLM finished thinking
          plan_reasoning   -> parsed reasoning text
          plan             -> final steps list (the last event)
        """
        if not model_id:
            model_id = os.getenv("MODEL_ID", "").strip()
        if not model_id:
            raise RuntimeError("MODEL_ID is not set in environment")

        user_context = self.memory.get_recent_context()
        available = self.registry.list_all()
        valid_ids = {a.id for a in available}
        agent_descriptions = "\n".join(
            f"- `{a.id}` ({a.name}): {a.description} | inputs={a.inputs}"
            for a in available
        )

        system = f"""You are a resume analysis coordinator.

Available subagents (use these exact IDs — never make up IDs):
{agent_descriptions}

{user_context}

Analyze the user's resume, job description, and goal to decide:
1. Which subagents to run (ONLY relevant ones — skip unnecessary ones)
2. In what order (set "deps" to reflect dependencies)

Rules:
- gap_analysis and assessment are independent (no deps)
- company_analysis is independent (no deps)
- remediation depends on gap_analysis
- rewrite depends on gap_analysis + assessment

CRITICAL: Every "id" must be one of: {', '.join(a.id for a in available)}
Do NOT use invented IDs or numbers like "1", "2".

Respond with raw JSON only (no markdown):
{{"steps": [{{"id": "...", "name": "...", "icon": "...", "deps": []}}], "reasoning": "your analysis here"}}

Explain WHY you chose each subagent based on the user's specific input."""

        prompt = f"Resume length: {len(resume_text)} chars, JD length: {len(jd_text)} chars"
        if goal:
            prompt += f"\nUser goal: {goal}"

        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )

        logger.info(
            "PLAN START | model=%s resume=%dchars jd=%dchars goal=%s",
            model_id, len(resume_text), len(jd_text), goal or "(none)",
        )

        yield {"type": "plan_start", "status": "analyzing"}

        full_text = ""
        plan_start = time.time()
        try:
            async with client.messages.stream(
                model=model_id,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            ) as stream:
                async for text_delta in stream.text_stream:
                    full_text += text_delta
                    # Yield on every delta so frontend shows per-token progress
                    yield {"type": "plan_thinking", "text": full_text}

        except Exception as e:
            logger.error("PLAN FAILED | model=%s error=%s", model_id, str(e)[:200])
            yield {"type": "plan_done"}
            yield {"type": "plan_reasoning", "reasoning": _FALLBACK_REASONING, "steps": _FALLBACK_PLAN_STEPS}
            yield {"type": "plan", "steps": _FALLBACK_PLAN_STEPS}
            return

        plan_elapsed = time.time() - plan_start
        logger.info("PLAN DONE | elapsed=%.1fs raw_output=%dchars", plan_elapsed, len(full_text))

        yield {"type": "plan_done"}

        # Parse JSON from LLM output
        match = re.search(r'\{.*\}', full_text, re.DOTALL)
        if not match:
            logger.warning("PLAN PARSE FAIL | no JSON found in raw output")
            yield {"type": "plan_reasoning", "reasoning": _FALLBACK_REASONING, "steps": _FALLBACK_PLAN_STEPS}
            yield {"type": "plan", "steps": _FALLBACK_PLAN_STEPS}
            return

        try:
            data = json.loads(match.group())
            raw_steps = data.get("steps", _FALLBACK_PLAN_STEPS)
            reasoning = data.get("reasoning", _FALLBACK_REASONING)

            logger.info("PLAN PARSED | raw_steps=%s reasoning=%dchars",
                        [s.get("id") for s in raw_steps], len(reasoning))

            # Validate step IDs against registry
            validated = [s for s in raw_steps if s.get("id") in valid_ids]
            if not validated:
                logger.warning(
                    "PLAN INVALID IDS | received=%s valid=%s — using fallback",
                    [s.get("id") for s in raw_steps],
                    sorted(valid_ids),
                )
                validated = _FALLBACK_PLAN_STEPS
                reasoning = _FALLBACK_REASONING
            elif len(validated) < len(raw_steps):
                bad = set(s.get("id") for s in raw_steps) - valid_ids
                logger.warning("PLAN PARTIAL INVALID | unknown IDs skipped: %s", bad)

            logger.info("PLAN FINAL | validated_steps=%s", [s["id"] for s in validated])

            yield {"type": "plan_reasoning", "reasoning": reasoning, "steps": validated}
            yield {"type": "plan", "steps": validated}
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("PLAN JSON ERROR | %s — using fallback", str(e)[:100])
            yield {"type": "plan_reasoning", "reasoning": _FALLBACK_REASONING, "steps": _FALLBACK_PLAN_STEPS}
            yield {"type": "plan", "steps": _FALLBACK_PLAN_STEPS}

    async def execute(self, steps: list[dict], resume_text: str, jd_text: str, goal: str = "", run_id: str = "", model_id: str | None = None) -> AsyncIterator[dict]:
        """Execute plan steps in dependency-level parallelism.

        Two-phase per level:
        1. Compile: each subagent prepares PromptBundle (<200ms, parallel)
        2. Infer: coordinator calls LLM with each bundle (parallel, streaming)

        Yields event dicts (type + data).
        """
        cache: dict = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "goal": goal,
        }
        levels = _group_by_deps(steps)

        yield {"type": "plan", "steps": steps}

        total_start = time.time()

        for level_idx, level in enumerate(levels):
            logger.info("EXEC LEVEL %d/%d | steps=%s",
                        level_idx + 1, len(levels), [s["id"] for s in level])

            # ── Phase 1: Compile all subagents in this level (parallel) ──────
            compile_start = time.time()
            bundles: dict[str, PromptBundle] = {}

            async def compile_one(step: dict) -> str:
                sid = step["id"]
                agent = self.registry.get(sid)
                if not agent:
                    logger.warning("COMPILE SKIP | unknown subagent: %s", sid)
                    return sid

                # Log what inputs are available for this step
                available_inputs = {k for k in cache.keys() if k in agent.inputs}
                logger.info("COMPILE %s | inputs=%s cache_keys=%s",
                            sid, agent.inputs, sorted(available_inputs))

                step_inputs = {k: v for k, v in cache.items() if k in agent.inputs}
                hook_result = HOOKS.fire("pre_subagent", step, step_inputs, cache)
                if hook_result:
                    step_inputs = hook_result

                t0 = time.time()
                bundle = await agent.run(inputs=step_inputs, emit=lambda d: None)
                elapsed = (time.time() - t0) * 1000
                logger.info("COMPILE %s DONE | elapsed=%.0fms system=%dchars prompt=%dchars",
                            sid, elapsed, len(bundle.system), len(bundle.prompt))
                bundles[sid] = bundle
                return sid

            compile_tasks = [asyncio.create_task(compile_one(s)) for s in level]
            for task in asyncio.as_completed(compile_tasks):
                sid = await task
                if sid in bundles:
                    yield {"type": "step_compiled", "step_id": sid}

            compile_duration = time.time() - compile_start
            logger.info("LEVEL %d COMPILE DONE | steps=%d total=%.0fms",
                        level_idx, len(level), compile_duration * 1000)

            # ── Phase 2: Infer — call LLM for each subagent (parallel) ────
            output_queue: asyncio.Queue = asyncio.Queue()
            valid_level = [s for s in level if s["id"] in bundles]

            if not valid_level:
                logger.warning("LEVEL %d INFER SKIP | no valid steps with bundles", level_idx)
                continue

            logger.info("LEVEL %d INFER START | steps=%s",
                        level_idx, [s["id"] for s in valid_level])

            # Emit step_start events
            for s in valid_level:
                yield {"type": "step_start", "step_id": s["id"]}

            async def infer_one(step: dict):
                sid = step["id"]
                bundle = bundles[sid]

                start = time.time()
                try:
                    result = await call_llm(
                        system=bundle.system,
                        prompt=bundle.prompt,
                        max_tokens=bundle.max_tokens,
                        emit=lambda data: output_queue.put_nowait(("chunk", sid, data)),
                        step_id=step["id"],
                        model_id=model_id,
                    )
                except Exception as e:
                    logger.error("Subagent %s failed: %s", sid, str(e)[:200])
                    HOOKS.fire("on_error", sid, str(e)[:200], cache)
                    await output_queue.put(("error", sid, str(e)[:200]))
                    return

                duration = time.time() - start
                text, thinking, truncated = result
                result_dict = {"text": text, "thinking": thinking, "truncated": truncated}
                cache[sid] = result_dict

                if run_id:
                    self.task_manager.save_result(run_id, sid, result_dict)

                hook_result = HOOKS.fire("post_subagent", step, result_dict, cache)
                if hook_result:
                    result_dict = hook_result

                await output_queue.put(("done", sid, duration))

            infer_tasks = [asyncio.create_task(infer_one(s)) for s in valid_level]
            pending = len(valid_level)

            while pending > 0:
                kind, sid, data = await output_queue.get()
                if kind == "chunk":
                    yield {"type": "step_output", "step_id": sid, "text": data.get("text", "")}
                elif kind == "error":
                    yield {"type": "step_error", "step_id": sid, "error": data}
                    pending -= 1
                elif kind == "done":
                    yield {"type": "step_done", "step_id": sid, "duration_ms": int(data * 1000)}
                    logger.info("INFER %s DONE | duration=%.1fs", sid, data)
                    pending -= 1

            # Cleanup any still-pending tasks
            for t in infer_tasks:
                if not t.done():
                    t.cancel()

            logger.info("LEVEL %d INFER DONE | steps=%d", level_idx, len(valid_level))

        total_duration = time.time() - total_start
        completed = [s["id"] for s in steps if s["id"] in cache and isinstance(cache[s["id"]], dict)]
        HOOKS.fire("on_all_done", cache, {"completed_steps": completed})
        logger.info("EXEC ALL DONE | steps=%d total=%.1fs", len(completed), total_duration)
        yield {"type": "all_done", "results": {k: v for k, v in cache.items() if isinstance(v, dict)}}
