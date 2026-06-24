"""Rewrite subagent — restructures resume with narrative story logic."""
from __future__ import annotations
import logging

from ..subagent import SubagentDef, StreamCallback, PromptBundle

logger = logging.getLogger("resume-editor.rewrite")


class RewriteSubagent(SubagentDef):
    """Rewrites resume using Background-Problem-Solution-Impact narrative structure."""

    def __init__(self) -> None:
        super().__init__(
            id="rewrite",
            name="故事改写",
            description="用叙事逻辑重构简历表述，背景-问题-方案-影响",
            icon="✏️",
            inputs=["resume_text", "jd_text", "gap_analysis", "assessment"],
            needed_skills=["rewrite"],
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
        assessment = inputs.get("assessment", {}).get("text", "")

        if not resume.strip() or not jd.strip():
            raise ValueError("resume_text and jd_text are required and must not be empty")

        skills = self.load_skills()

        system = "You are a professional resume writer. Rewrite using storytelling logic."
        if skills:
            system += f"\n\n{skills}"
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        if previous_result:
            prev_text = (previous_result.get("text") or "")[:1000]
            system += f"\n\nPrevious result for reference: {prev_text}"

        prompt = f"""Rewrite the resume to be more compelling.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

GAP ANALYSIS:
{gap[:2000]}

ASSESSMENT:
{assessment[:2000]}

Use the narrative structure:
- Project Background: what was the context
- Problem: what pain point existed
- Solution: what you designed and built
- Impact: quantified results and user value

Rules:
- Keep all factual claims truthful
- Chinese narrative with embedded English tech keywords (do NOT translate keywords like Tool Calling, Permission Gate, etc.)
- Each bullet should tell a mini-story
- Prioritize impact and results over descriptions"""

        return PromptBundle(
            system=system,
            prompt=prompt,
            max_tokens=16384,
            step_id=self.id,
            step_name=self.name,
        )
