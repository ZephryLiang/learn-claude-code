"""Gap analysis subagent — compares resume against job description."""
from __future__ import annotations

from ..subagent import SubagentDef, StreamCallback


class GapAnalysisSubagent(SubagentDef):
    """Analyzes gaps between resume and job description."""

    def __init__(self) -> None:
        super().__init__(
            id="gap_analysis",
            name="差距分析",
            description="逐项对比 JD 要求与简历内容，标记匹配、可重包装、缺失项",
            icon="📊",
            inputs=["resume_text", "jd_text"],
            needed_skills=["gap_analysis"],
        )

    async def run(
        self,
        inputs: dict,
        emit: StreamCallback,
        feedback: str | None = None,
        previous_result: dict | None = None,
    ) -> dict:
        from anthropic import AsyncAnthropic
        import os

        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")

        system = "You are a professional resume consultant. Analyze gaps between resume and JD."
        if feedback:
            system += f"\n\nUser feedback (re-analyze with this context): {feedback}"
        if previous_result:
            system += f"\n\nPrevious result for reference: {previous_result.get('text', '')[:1000]}"

        prompt = f"""Analyze the gap between this resume and the job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Provide a structured analysis:
1. **Strong matches** (keywords/experience that directly align)
2. **Repackagable** (experience that can be positioned to fit)
3. **Genuine gaps** (missing skills/experience)
4. **Keywords to add** (specific JD keywords not in resume)
5. **Overall fit score** (1-10) with brief rationale"""

        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )

        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )

        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking

        return {
            "text": text,
            "thinking": thinking,
            "truncated": resp.stop_reason == "max_tokens",
        }
