"""Gap analysis subagent — compares resume against job description."""
from __future__ import annotations
import logging

from ..subagent import SubagentDef, StreamCallback, PromptBundle

logger = logging.getLogger("resume-editor.gap_analysis")


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
    ) -> PromptBundle:
        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")

        if not resume.strip() or not jd.strip():
            raise ValueError("resume_text and jd_text are required and must not be empty")

        skills = self.load_skills()

        system = "You are a professional resume consultant. Analyze gaps between resume and JD."
        if skills:
            system += f"\n\n{skills}"
        if feedback:
            system += f"\n\nUser feedback (re-analyze with this context): {feedback}"
        if previous_result:
            prev_text = (previous_result.get("text") or "")[:1000]
            system += f"\n\nPrevious result for reference: {prev_text}"

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

        return PromptBundle(
            system=system,
            prompt=prompt,
            step_id=self.id,
            step_name=self.name,
        )
