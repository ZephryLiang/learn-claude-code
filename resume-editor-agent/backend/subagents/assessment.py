"""Assessment subagent — scores resume against JD across multiple dimensions."""
from __future__ import annotations
import logging

from ..subagent import SubagentDef, StreamCallback, PromptBundle

logger = logging.getLogger("resume-editor.assessment")


class AssessmentSubagent(SubagentDef):
    """Scores resume effectiveness across 5 dimensions, with strengths, weaknesses, and recruiter summary."""

    def __init__(self) -> None:
        super().__init__(
            id="assessment",
            name="匹配评估",
            description="综合评分 + 面试竞争力分析",
            icon="🎯",
            inputs=["resume_text", "jd_text"],
            needed_skills=["assessment"],
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

        system = "You are a professional career coach. Provide honest assessment and interview chances."
        if skills:
            system += f"\n\n{skills}"
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        if previous_result:
            prev_text = (previous_result.get("text") or "")[:1000]
            system += f"\n\nPrevious result for reference: {prev_text}"

        prompt = f"""Evaluate this resume's effectiveness for getting an interview.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Score each dimension 1-10 with brief reasoning:
1. **ATS keyword match**
2. **First impression** (15-second scan)
3. **Narrative coherence** (story consistency)
4. **Impact evidence** (quantified results)
5. **Overall interview chance**

Then provide:
- Top 3 strengths
- Top 3 weaknesses
- One-paragraph summary of what a recruiter would think"""

        return PromptBundle(
            system=system,
            prompt=prompt,
            step_id=self.id,
            step_name=self.name,
        )
