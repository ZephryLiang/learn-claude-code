"""Remediation subagent — creates learning plans to close resume gaps."""
from __future__ import annotations
import logging

from ..subagent import SubagentDef, StreamCallback, PromptBundle

logger = logging.getLogger("resume-editor.remediation")


class RemediationSubagent(SubagentDef):
    """Creates structured learning plans from gap analysis, grouped by urgency."""

    def __init__(self) -> None:
        super().__init__(
            id="remediation",
            name="补足路线",
            description="针对差距生成学习路线和优先级",
            icon="📋",
            inputs=["resume_text", "jd_text", "gap_analysis"],
            needed_skills=["remediation"],
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
        gap = inputs.get("gap_analysis", {}).get("text", "")

        if not resume.strip() or not jd.strip():
            raise ValueError("resume_text and jd_text are required and must not be empty")

        skills = self.load_skills()

        system = "You are a learning path designer. Create concrete remediation plans."
        if skills:
            system += f"\n\n{skills}"
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        if previous_result:
            prev_text = (previous_result.get("text") or "")[:1000]
            system += f"\n\nPrevious result for reference: {prev_text}"

        prompt = f"""Create a concrete remediation plan for the gaps between this resume and job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

GAP ANALYSIS:
{gap[:2000]}

For each genuine gap (not repackagable), provide:
1. **Gap** - what's missing
2. **Priority** - High/Medium/Low
3. **Learning resource** - specific tutorial, course, or project idea
4. **Time estimate** - hours needed
5. **How to demonstrate** - how to show this skill on the resume after learning

Group into: Week 1 (urgent), Week 2-4, Month 2+"""

        return PromptBundle(
            system=system,
            prompt=prompt,
            step_id=self.id,
            step_name=self.name,
        )
