"""Coordinator agent loop: plans execution, spawns subagents, emits events."""
from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import AsyncIterator

from anthropic import AsyncAnthropic
from .subagent import SubagentRegistry
from .hooks import HOOKS

logger = logging.getLogger("resume-editor.coordinator")

_FALLBACK_PLAN: list[dict] = [{"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []}]


class Coordinator:
    """Agent loop: plan -> execute subagents -> emit events."""

    def __init__(self, registry: SubagentRegistry):
        self.registry = registry

    async def plan(self, resume_text: str, jd_text: str, goal: str = "") -> list[dict]:
        """Ask LLM to select and order subagents from registry."""
        model_id = os.getenv("MODEL_ID", "").strip()
        if not model_id:
            raise RuntimeError("MODEL_ID is not set in environment")

        system = f"""You are a resume analysis coordinator. Available subagents:
{self.registry.describe()}

Given the user's resume, job description, and goal, select which subagents to run and in what order. Only include relevant ones.

Respond with JSON only:
{{"steps": [{{"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []}}], "reasoning": "..."}}"""

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
            # Fallback: default plan with gap_analysis
            return _FALLBACK_PLAN

        text = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text

        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return _FALLBACK_PLAN

        try:
            data = json.loads(match.group())
            return data.get("steps", [{"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []}])
        except (json.JSONDecodeError, KeyError):
            return _FALLBACK_PLAN

    async def execute(self, steps: list[dict], resume_text: str, jd_text: str, goal: str = "") -> AsyncIterator[dict]:
        """Execute plan steps, yielding events. Run this as an async generator."""
        cache = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "goal": goal,
        }

        yield {"type": "plan", "steps": steps}

        for step in steps:
            agent = self.registry.get(step["id"])
            if not agent:
                logger.warning("Unknown subagent in plan: %s", step["id"])
                continue

            step_inputs = {k: v for k, v in cache.items() if k in agent.inputs}

            # Fire pre_subagent hook
            hook_result = HOOKS.fire("pre_subagent", step, step_inputs, cache)
            if hook_result:
                step_inputs = hook_result

            yield {"type": "step_start", "step_id": step["id"]}

            start = time.time()
            output_chunks = []

            # StreamCallback is Callable[[dict], None] (sync), matching subagent.py
            def streaming_emit(data: dict):
                output_chunks.append(data)

            try:
                result = await agent.run(inputs=step_inputs, emit=streaming_emit)
            except Exception as e:
                logger.error("Subagent %s failed: %s", step["id"], str(e)[:200])
                HOOKS.fire("on_error", step["id"], str(e)[:200], cache)
                yield {"type": "step_error", "step_id": step["id"], "error": str(e)[:200]}
                continue

            duration = time.time() - start

            # Replay collected chunks
            for chunk in output_chunks:
                chunk["step_id"] = step["id"]
                yield {"type": "step_output", "step_id": step["id"], **chunk}

            cache[step["id"]] = result

            # Fire post_subagent hook
            hook_result = HOOKS.fire("post_subagent", step, result, cache)
            if hook_result:
                result = hook_result

            yield {"type": "step_done", "step_id": step["id"], "duration_ms": int(duration * 1000)}

        completed = [s["id"] for s in steps]
        HOOKS.fire("on_all_done", cache, {"completed_steps": completed})
        yield {"type": "all_done", "results": {k: v for k, v in cache.items() if isinstance(v, dict)}}
