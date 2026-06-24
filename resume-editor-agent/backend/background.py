"""Background task system (s08): async execution with completion callback."""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger("resume-editor.background")


class BackgroundTask:
    id: str
    coro: Any
    result: Optional[Any] = None
    error: Optional[str] = None
    done: bool = False
    start_time: float = 0.0

    def __init__(self, coro, on_complete: Optional[Callable] = None):
        self.id = uuid.uuid4().hex[:8]
        self.coro = coro
        self.on_complete = on_complete

    async def run(self):
        self.start_time = time.time()
        try:
            self.result = await self.coro
        except Exception as e:
            self.error = str(e)[:500]
            logger.error("Background task %s failed: %s", self.id, self.error)
        finally:
            self.done = True
            if self.on_complete and self.result:
                await self.on_complete(self.result)
            logger.info("Background task %s done in %.2fs", self.id, time.time() - self.start_time)


class BackgroundTaskManager:
    """Manages concurrent background tasks."""

    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}

    def submit(self, coro, on_complete: Optional[Callable] = None) -> str:
        task = BackgroundTask(coro, on_complete)
        self._tasks[task.id] = task
        asyncio.create_task(task.run())
        logger.info("Background task submitted: %s", task.id)
        return task.id

    def get_status(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "done": task.done,
            "error": task.error,
            "duration_ms": int((time.time() - task.start_time) * 1000) if task.start_time else 0,
        }

    def get_result(self, task_id: str) -> Any:
        task = self._tasks.get(task_id)
        return task.result if task and task.done else None


background_manager = BackgroundTaskManager()
