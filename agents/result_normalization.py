#!/usr/bin/env python3
# Harness: structured results — when the model stops parsing errors and starts making decisions.
"""
s13_result_normalization.py — Structured Tool Result Normalization

Sits at the harness seam between tool execution and message injection:
tool executes → normalizer wraps → model gets structured JSON

Demonstrates the difference between:

    BEFORE (s01):  "Error: Permission denied: /etc/shadow"
    AFTER  (s13):  {"tool":"bash","success":false,"error":{"type":"permission",...}}

Key insight: "The model is a decision maker, not a parser."
"""

import json
import os
import subprocess
import sys
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.lib.result_normalizer import (
    ResultNormalizer,
    ToolResult,
    ToolError,
    ErrorType,
    normalize_result,
)


# ── BEFORE: the s01 way ──────────────────────────────────────────────────────

def s01_style_bash(command: str) -> str:
    """s01 raw string return — the model has to PARSE this."""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (10s)"


# ── AFTER: the s13 way ───────────────────────────────────────────────────────

_normalizer = ResultNormalizer()


def s13_style_bash(command: str) -> tuple[str, float, str, str, int]:
    """Returns raw execution details — normalizer wraps them afterward."""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        # Return sentinel: normalizer wraps into structured error
        return ("", f"BLOCKED:{command}", 126)

    start = time.monotonic()
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        return (r.stdout, r.stderr, r.returncode)

    except subprocess.TimeoutExpired:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ("", f"TIMEOUT:Command timed out after 10s", -1)


# ── Demo ─────────────────────────────────────────────────────────────────────

SCENARIOS = [
    # (label, command, expected_error_type)
    ("File not found", "cat /nonexistent/path/file.txt", ErrorType.NOT_FOUND),
    ("Permission denied", "cat /etc/master.passwd", ErrorType.PERMISSION),
    ("DNS resolution failure", "curl -s http://this-domain-does-not-exist-12345.com", ErrorType.TRANSIENT),
    ("Command not found", "this_command_does_not_exist_xyz", ErrorType.NOT_FOUND),
    ("Normal success", "echo 'hello world'", None),
    ("Git status (transient net)", "git ls-remote https://invalid.git.server/repo.git 2>&1", ErrorType.TRANSIENT),
]


def format_s01_output(raw: str) -> str:
    """Simulate what the model sees in its context with s01 style."""
    return f"""
┌─────────────────────────────────────────────────────────────┐
│  WHAT THE MODEL SEES (s01 — raw string)                     │
│                                                             │
│  The model must NLP-parse this to figure out what happened. │
│  Is this error transient? Permanent? Should it retry?        │
│  The model has to GUESS.                                    │
├─────────────────────────────────────────────────────────────┤
{textwrap.indent(raw, '│  ')}
└─────────────────────────────────────────────────────────────┘
"""


def format_s13_output(result: ToolResult) -> str:
    """Simulate what the model sees in its context with s13 style."""
    formatted = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    action_map = {
        "retry_with_backoff": "→ Model knows: retry after waiting",
        "retry_or_split_work": "→ Model knows: retry or subdivide",
        "verify_path_or_reference": "→ Model knows: check the path/name, don't retry blindly",
        "escalate_to_user": "→ Model knows: ask user for permission",
        "install_or_fix_command": "→ Model knows: install the tool",
        "investigate_and_fix": "→ Model knows: investigate root cause",
    }
    suggestion = result.error.suggested_action if result.error else ""
    hint = action_map.get(suggestion, "")

    return f"""
┌─────────────────────────────────────────────────────────────┐
│  WHAT THE MODEL SEES (s13 — structured JSON)                │
│                                                             │
│  No parsing needed. The model reads `error.type` and        │
│  `retryable` and makes a decision directly.                 │
│  {hint}                                  │
├─────────────────────────────────────────────────────────────┤
{textwrap.indent(formatted, '│  ')}
└─────────────────────────────────────────────────────────────┘
"""


def main():
    print("=" * 65)
    print("  Structured vs Raw: What the Model Actually Sees")
    print("=" * 65)

    for label, command, expected_type in SCENARIOS:
        print(f"\n{'─' * 65}")
        print(f"  SCENARIO: {label}")
        print(f"  COMMAND:  {command}")
        print(f"{'─' * 65}")

        # ── s01 way ──
        raw = s01_style_bash(command)
        print(format_s01_output(raw))

        # ── s13 way ──
        raw_tuple = s13_style_bash(command)
        if isinstance(raw_tuple, tuple) and len(raw_tuple) == 3:
            stdout, stderr, exit_code = raw_tuple
            result = _normalizer.wrap_bash(
                command=command, stdout=stdout, stderr=stderr,
                exit_code=exit_code, duration_ms=0,
            )
            print(format_s13_output(result))
        else:
            # s13_style_bash can also return a raw tuple from blocked/timeout
            if isinstance(raw_tuple, tuple):
                stdout, stderr, exit_code = raw_tuple
                result = _normalizer.wrap_bash(
                    command=command, stdout=stdout, stderr=stderr,
                    exit_code=exit_code if exit_code > 0 else -1,
                    duration_ms=0,
                )
            else:
                result = _normalizer.wrap_bash(command, str(raw_tuple), "", 0, 0)
            print(format_s13_output(result))

        # Verify classification
        if expected_type and result.error:
            match = "✓" if result.error.type == expected_type else f"✗ (got {result.error.type.value})"
            print(f"  Classification check: expected={expected_type.value} → actual={result.error.type.value} {match}")

    # ── Error summary (observability) ──
    print(f"\n{'═' * 65}")
    print("  ERROR SUMMARY (what the observability layer would report)")
    print(f"{'═' * 65}")
    summary = _normalizer.error_summary()
    if summary:
        for key, count in sorted(summary.items()):
            tool, err_type = key.split(":", 1)
            print(f"  {tool}: {err_type} — {count} occurrence(s)")
    else:
        print("  No errors encountered.")

    print(f"\n{'─' * 65}")
    print("  Takeaway:")
    print("  s01 model behavior: read error text → guess → maybe retry, maybe not")
    print("  s13 model behavior: read error.type → if transient: retry;")
    print("                       if permission: escalate; if permanent: switch")
    print(f"{'─' * 65}")


if __name__ == "__main__":
    main()
