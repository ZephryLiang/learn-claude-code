"""Lifecycle hook registry for agent runtime."""
from __future__ import annotations
from typing import Any, Callable
import logging

logger = logging.getLogger("resume-editor.hooks")


class HookRegistry:
    """Registry for lifecycle hooks at key runtime nodes."""

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {
            "on_plan_generated": [],
            "pre_subagent": [],
            "post_subagent": [],
            "on_intercept": [],
            "on_all_done": [],
            "on_error": [],
        }

    def register(self, hook_point: str, fn: Callable) -> None:
        if hook_point not in self._hooks:
            raise ValueError(f"Unknown hook point: {hook_point}, valid: {list(self._hooks.keys())}")
        self._hooks[hook_point].append(fn)
        logger.info("Hook registered: %s -> %s", hook_point, getattr(fn, '__qualname__', repr(fn)))

    def fire(self, hook_point: str, *args, **kwargs) -> Any:
        if hook_point not in self._hooks:
            return None

        result = None
        for fn in self._hooks[hook_point]:
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                fn_name = getattr(fn, '__qualname__', repr(fn))
                logger.warning("Hook %s handler %s failed: %s", hook_point, fn_name, e)
        return result


HOOKS = HookRegistry()
