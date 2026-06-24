"""Task system (s07): persistent task directories for agent runs."""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("resume-editor.task_manager")

TASKS_DIR = Path(__file__).parent / "tasks"


class TaskManager:
    """Persist agent run state to .tasks/{run_id}/ for recovery and inspection."""

    def __init__(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)

    def create_run(self) -> str:
        run_id = uuid.uuid4().hex[:12]
        (TASKS_DIR / run_id).mkdir(parents=True, exist_ok=True)
        logger.info("Task run created: %s", run_id)
        return run_id

    def save_plan(self, run_id: str, plan: dict):
        path = TASKS_DIR / run_id / "plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2))

    def save_result(self, run_id: str, step_id: str, result: dict):
        path = TASKS_DIR / run_id / step_id / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    def get_result(self, run_id: str, step_id: str) -> Optional[dict]:
        path = TASKS_DIR / run_id / step_id / "result.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def get_plan(self, run_id: str) -> Optional[dict]:
        path = TASKS_DIR / run_id / "plan.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_runs(self) -> list[str]:
        return sorted(
            [d.name for d in TASKS_DIR.iterdir() if d.is_dir()],
            reverse=True,
        )[:20]
