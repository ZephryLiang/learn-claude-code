"""Subagent base class and registry + shared LLM helper."""
from __future__ import annotations
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from anthropic import AsyncAnthropic

logger = logging.getLogger("resume-editor.subagent")

StreamCallback = Callable[[dict], None]

# Shared AsyncAnthropic client singleton — prevents connection-pool leaks
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")
        _client = AsyncAnthropic(
            api_key=api_key,
            base_url=os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com",
        )
    return _client


@dataclass
class PromptBundle:
    """Compiled prompt materials — the harness output for a subagent step.

    Returned by SubagentDef.run() in <200ms (no LLM call).
    The coordinator uses this to make the actual LLM inference call separately.
    """
    system: str
    prompt: str
    max_tokens: int = 8192
    step_id: str = ""
    step_name: str = ""


async def call_llm(
    *,
    system: str,
    prompt: str,
    model_id: str | None = None,
    max_tokens: int = 8192,
    emit: StreamCallback | None = None,
    step_id: str = "",
) -> tuple[str, str, bool]:
    """Shared LLM-call boilerplate. Returns (text, thinking, truncated).

    Used by the coordinator AFTER subagent compilation to perform inference.
    """
    if not model_id:
        model_id = os.getenv("MODEL_ID", "").strip()
    if not model_id:
        raise RuntimeError("MODEL_ID is not set in environment")

    client = _get_client()

    text = ""
    thinking = ""
    sys_len = len(system)
    prompt_len = len(prompt)
    t_start = time.time()
    first_token = None

    logger.info(
        "LLM call START | model=%s step_id=%s system=%dchars prompt=%dchars max_tokens=%d",
        model_id, step_id or "?",
        sys_len, prompt_len, max_tokens,
    )

    try:
        async with client.messages.stream(
            model=model_id,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ) as stream:
            async for text_delta in stream.text_stream:
                if first_token is None:
                    first_token = time.time()
                    logger.info(
                        "LLM first token received | step_id=%s ttft=%.1fs",
                        step_id or "?",
                        first_token - t_start,
                    )
                text += text_delta
                if emit:
                    emit({"type": "output", "text": text})

            final = await stream.get_final_message()
            truncated = final.stop_reason == "max_tokens"

    except Exception as e:
        elapsed = time.time() - t_start
        msg = str(e)[:200]
        logger.error("LLM call FAILED | model=%s error=%s elapsed=%.1fs", model_id, msg, elapsed)
        raise RuntimeError(f"Anthropic API call failed: {msg}") from e

    elapsed = time.time() - t_start
    ttft = (first_token - t_start) if first_token else 0
    logger.info(
        "LLM call END | model=%s step_id=%s elapsed=%.1fs ttft=%.1fs output=%dchars truncated=%s",
        model_id, step_id or "?",
        elapsed, ttft, len(text), truncated,
    )

    return text, thinking, truncated


@dataclass
class SubagentDef:
    """Definition of an analyzable capability."""
    id: str
    name: str
    description: str
    icon: str = "📄"
    inputs: list[str] = field(default_factory=list)
    needed_skills: list[str] = field(default_factory=list)

    def load_skills(self) -> str:
        """Load skill content from skills/{skill_id}/SKILL.md files."""
        from pathlib import Path
        base = Path(__file__).parent / "skills"
        parts = []
        for skill_id in self.needed_skills:
            skill_path = base / skill_id / "SKILL.md"
            if skill_path.exists():
                parts.append(f"=== {skill_id} ===\n{skill_path.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)

    async def run(
        self,
        inputs: dict[str, Any],
        emit: StreamCallback,
        feedback: Optional[str] = None,
        previous_result: Optional[dict] = None,
    ) -> PromptBundle:
        """Compile a PromptBundle (<200ms, no LLM call).

        The coordinator calls this to get the full system prompt + user prompt,
        then makes the LLM inference call separately.
        """
        raise NotImplementedError


class SubagentRegistry:
    """Registry of all available subagents."""

    def __init__(self):
        self._subagents: dict[str, SubagentDef] = {}

    def register(self, agent: SubagentDef) -> None:
        self._subagents[agent.id] = agent

    def get(self, agent_id: str) -> Optional[SubagentDef]:
        return self._subagents.get(agent_id)

    def list_all(self) -> list[SubagentDef]:
        return list(self._subagents.values())

    def describe(self) -> str:
        lines = []
        for a in self._subagents.values():
            lines.append(f"- `{a.id}`: {a.name} — {a.description}")
        return "\n".join(lines)
