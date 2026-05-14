"""Shared deterministic tools available to subagents."""

def read_resume(cache: dict) -> str:
    return cache.get("resume_text", "")

def read_jd(cache: dict) -> str:
    return cache.get("jd_text", "")
