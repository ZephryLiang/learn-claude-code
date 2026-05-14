"""Subagent base class and registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

StreamCallback = Callable[[dict], None]


@dataclass
class SubagentDef:
    """Definition of an analyzable capability."""
    id: str
    name: str
    description: str
    icon: str = "📄"
    inputs: list[str] = field(default_factory=list)
    needed_skills: list[str] = field(default_factory=list)

    async def run(
        self,
        inputs: dict[str, Any],
        emit: StreamCallback,
        feedback: Optional[str] = None,
        previous_result: Optional[dict] = None,
    ) -> dict[str, Any]:
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
