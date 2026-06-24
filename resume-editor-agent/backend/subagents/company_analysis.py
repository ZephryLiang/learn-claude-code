"""Company analysis subagent: researches company health, products, team."""
from __future__ import annotations
import logging
import re

from ..subagent import SubagentDef, StreamCallback, PromptBundle

logger = logging.getLogger("resume-editor.company_analysis")


class CompanyAnalysisSubagent(SubagentDef):

    def __init__(self):
        super().__init__(
            id="company_analysis",
            name="公司尽调",
            description="分析目标公司的业务健康度、融资阶段、团队背景、市场位置",
            icon="🏢",
            inputs=["jd_text"],
            needed_skills=["company_analysis"],
        )

    async def run(
        self,
        inputs: dict,
        emit: StreamCallback,
        feedback: str | None = None,
        previous_result: dict | None = None,
    ) -> PromptBundle:
        jd = inputs.get("jd_text", "")

        if not jd.strip():
            raise ValueError("jd_text is required and must not be empty")

        skills = self.load_skills()

        # Extract company name from JD (simplified)
        company_match = re.search(r'(?:公司|企业|@|at)\s*[:：]?\s*(\S+)', jd[:500])
        company_name = company_match.group(1) if company_match else ""

        system = "You are a business analyst. Analyze companies from a job seeker's perspective."
        if skills:
            system += f"\n\n{skills}"
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        if previous_result:
            prev_text = (previous_result.get("text") or "")[:1000]
            system += f"\n\nPrevious result for reference: {prev_text}"

        prompt = f"""Analyze the company behind this job description.

JOB DESCRIPTION:
{jd}

{f'Company name identified: {company_name}' if company_name else 'No company name identified from the JD.'}

Provide analysis covering:
1. **Company overview** — What does this company do? Size, stage, reputation
2. **Product/Service** — Core offerings relevant to the role
3. **Team context** — What the team culture might be like (from JD signals)
4. **Career implications** — Growth potential, stability, exit opportunities
5. **Interview tips** — What to emphasize based on company positioning"""

        return PromptBundle(
            system=system,
            prompt=prompt,
            step_id=self.id,
            step_name=self.name,
        )
