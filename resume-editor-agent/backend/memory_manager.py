"""Cross-session memory (user profile + analysis history)."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("resume-editor.memory")

MEMORY_DIR = Path(__file__).parent / "memory"


class MemoryManager:
    """Manages user profile and analysis history across sessions."""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._profile_path = MEMORY_DIR / "user_profile.md"
        self._history_path = MEMORY_DIR / "analysis_history.json"

    def get_profile(self) -> str:
        """Load user profile text for injection into agent prompts."""
        if self._profile_path.exists():
            return self._profile_path.read_text(encoding="utf-8")
        return ""

    def update_profile(self, key: str, value: str):
        """Update a profile field."""
        profile = self._load_profile_dict()
        profile[key] = value
        profile["last_updated"] = datetime.now().isoformat()
        self._save_profile_dict(profile)

    def _load_profile_dict(self) -> dict:
        profile = {}
        if self._profile_path.exists():
            text = self._profile_path.read_text(encoding="utf-8")
            for line in text.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    profile[k.strip()] = v.strip()
        return profile

    def _save_profile_dict(self, profile: dict):
        lines = [f"{k}: {v}" for k, v in profile.items()]
        self._profile_path.write_text("\n".join(lines), encoding="utf-8")

    def add_history(self, run_id: str, summary: str):
        """Record an analysis run in history."""
        history = []
        if self._history_path.exists():
            history = json.loads(self._history_path.read_text())
        history.append({
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
        })
        history = history[-20:]
        self._history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    def get_recent_context(self) -> str:
        """Get recent context for injection."""
        parts = []
        profile = self.get_profile()
        if profile:
            parts.append(f"用户信息：\n{profile}")
        if self._history_path.exists():
            history = json.loads(self._history_path.read_text())
            if history:
                last = history[-1]
                parts.append(f"最近分析（{last['timestamp']}）：{last['summary']}")
        return "\n\n".join(parts)
