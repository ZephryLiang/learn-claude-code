"""Context compression (s06): summarize old messages to manage context window."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("resume-editor.compressor")

# Token estimation (rough: 4 chars ≈ 1 token)
_CHARS_PER_TOKEN = 4
_MAX_TOKENS = 80000  # Claude context limit safety margin


def estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def compress_messages(messages: list[dict], target_tokens: int = 40000) -> list[dict]:
    """Three-layer compression:
    1. Summarize oldest messages
    2. Retain recent verbatim
    3. Drop tool call internals if still over limit
    """
    total = sum(estimate_tokens(str(m.get("content", ""))) for m in messages)

    if total <= target_tokens:
        return messages

    logger.info("Compressing %d messages (%d tokens)", len(messages), total)

    # Layer 1: split into old + recent
    mid = len(messages) // 2
    old = messages[:mid]
    recent = messages[mid:]

    # Layer 2: summarize old messages
    compressed_old = _summarize_old(old)

    result = compressed_old + recent
    total_after = sum(estimate_tokens(str(m.get("content", ""))) for m in result)

    if total_after <= target_tokens:
        logger.info("Compressed to %d tokens (layer 1)", total_after)
        return result

    # Layer 3: truncate tool results in recent messages
    for msg in recent:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str) and len(content) > 500:
                        block["content"] = content[:500] + "\n...[truncated]"

    total_final = sum(estimate_tokens(str(m.get("content", ""))) for m in result)
    logger.info("Compressed to %d tokens (layer 2)", total_final)

    return result


def _summarize_old(old_messages: list[dict]) -> list[dict]:
    """Reduce old messages to a summary message."""
    text_parts = []
    for msg in old_messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            text_parts.append(f"{msg['role']}: {content[:200]}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(f"{msg['role']}: {block['text'][:200]}")

    summary = "\n".join(text_parts)
    if len(summary) > 3000:
        summary = summary[:3000] + "\n...[summarized]"

    return [{"role": "user", "content": f"[Previous conversation summary]:\n{summary}"}]
