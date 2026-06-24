"""
Structured tool result normalization layer.

Sits at the harness seam between tool execution and message injection.
Tool returns raw output; Normalizer wraps it so the model gets machine-readable
results it can reason about without NLP-parsing error strings.

Key principle: the model should be a DECISION MAKER, not a parser.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ── Error taxonomy ───────────────────────────────────────────────────────────

class ErrorType(str, Enum):
    """Classification that tells the model what KIND of failure occurred.

    The model uses this to decide its next action without parsing error text.
    """
    TRANSIENT = "transient"        # Temporary — retry makes sense
    PERMANENT = "permanent"        # Won't fix itself — change strategy
    PERMISSION = "permission"      # Not allowed — escalate to user
    NOT_FOUND = "not_found"        # Resource missing — check path/reference
    INVALID_INPUT = "invalid_input"  # Bad arguments from the model — fix params
    TIMEOUT = "timeout"            # Took too long — retry or split work
    UNKNOWN = "unknown"            # Cannot classify — model decides


# ── Structured result types ──────────────────────────────────────────────────

@dataclass
class ToolError:
    """Machine-readable error that the model can act on directly."""
    type: ErrorType
    message: str
    retryable: bool = False
    suggested_action: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class ToolResult:
    """The envelope every tool result gets wrapped in.

    Always valid JSON.  On success, ``data`` holds the output.
    On failure, ``error`` tells the model what happened and what to do.
    """
    tool_name: str
    success: bool
    data: str | None = None
    error: ToolError | None = None
    duration_ms: float = 0.0
    # How many bytes of raw output were truncated (0 = full output returned)
    truncated_bytes: int = 0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "tool": self.tool_name,
            "success": self.success,
        }
        if self.data is not None:
            d["data"] = self.data
        if self.error is not None:
            d["error"] = self.error.to_dict()
        d["duration_ms"] = round(self.duration_ms, 1)
        if self.truncated_bytes > 0:
            d["truncated_bytes"] = self.truncated_bytes
        return d

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ── Error classifiers (per-tool-type) ────────────────────────────────────────

def _classify_bash_error(stderr: str, exit_code: int, stdout: str = "") -> ToolError:
    """Classify shell command failures from stderr + exit code.

    Searches both stderr and stdout because shell redirects (2>&1)
    can merge error messages into stdout.
    """
    combined = (stderr + "\n" + stdout).lower()

    # Permission patterns
    permission_patterns = [
        "permission denied", "operation not permitted",
        "not permitted", "eacces", "cannot access.*denied",
    ]
    for pat in permission_patterns:
        if re.search(pat, combined):
            return ToolError(
                type=ErrorType.PERMISSION,
                message=stderr[:500],
                retryable=False,
                suggested_action="escalate_to_user",
            )

    # Not-found patterns
    not_found_patterns = [
        "no such file", "not found", "cannot find",
        "does not exist", "not a directory",
    ]
    for pat in not_found_patterns:
        if re.search(pat, combined):
            return ToolError(
                type=ErrorType.NOT_FOUND,
                message=stderr[:500],
                retryable=False,
                suggested_action="verify_path_or_reference",
            )

    # Timeout patterns (subprocess-level timeout)
    timeout_patterns = ["timed out", "timeout", "connection timed out"]
    for pat in timeout_patterns:
        if re.search(pat, combined):
            return ToolError(
                type=ErrorType.TIMEOUT,
                message=stderr[:500],
                retryable=True,
                suggested_action="retry_or_split_work",
            )

    # Transient patterns (network, lock, resource temporarily unavailable)
    transient_patterns = [
        "connection refused", "temporary failure", "try again",
        "resource temporarily unavailable", "network is unreachable",
        "could not resolve host", "rate limit",
        "tls connect error", "ssl.*error", "certificate.*expired",
        "couldn't connect to", "connection reset",
        "name resolution", "no route to host",
    ]
    for pat in transient_patterns:
        if re.search(pat, combined):
            return ToolError(
                type=ErrorType.TRANSIENT,
                message=stderr[:500],
                retryable=True,
                suggested_action="retry_with_backoff",
            )

    # ── Exit-code-based classification (catches errors with silent stderr) ──

    # curl exit codes (man curl: EXIT CODES section)
    CURL_TRANSIENT_CODES = {
        6: "Could not resolve host (DNS failure)",
        7: "Failed to connect to host",
        28: "Operation timed out",
        35: "SSL connect error",
    }
    if "curl" in combined or exit_code in CURL_TRANSIENT_CODES:
        reason = CURL_TRANSIENT_CODES.get(exit_code)
        if reason:
            return ToolError(
                type=ErrorType.TRANSIENT,
                message=stderr[:500] or reason,
                retryable=True,
                suggested_action="retry_with_backoff",
            )

    # git exit codes
    if exit_code == 128 and ("tls" in combined or "connect" in combined
                             or "unable to access" in combined):
        return ToolError(
            type=ErrorType.TRANSIENT,
            message=stderr[:500] or "Git remote connection failed",
            retryable=True,
            suggested_action="retry_with_backoff",
        )

    # Standard exit codes
    if exit_code == 127:
        return ToolError(
            type=ErrorType.NOT_FOUND,
            message=f"Command not found: {stderr[:500]}",
            retryable=False,
            suggested_action="install_or_fix_command",
        )
    if exit_code == 1:
        return ToolError(
            type=ErrorType.PERMANENT,
            message=stderr[:500] or "(exit code 1, no stderr)",
            retryable=False,
            suggested_action="fix_parameters",
        )

    # Default: permanent error
    return ToolError(
        type=ErrorType.PERMANENT,
        message=stderr[:500] or f"(exit code {exit_code})",
        retryable=False,
        suggested_action="investigate_and_fix",
    )


def _classify_file_error(exception: Exception) -> ToolError:
    """Classify file-operation exceptions."""
    ex_name = type(exception).__name__
    ex_msg = str(exception)

    if ex_name == "FileNotFoundError":
        return ToolError(
            type=ErrorType.NOT_FOUND,
            message=ex_msg,
            retryable=False,
            suggested_action="check_file_path",
        )
    if ex_name == "PermissionError":
        return ToolError(
            type=ErrorType.PERMISSION,
            message=ex_msg,
            retryable=False,
            suggested_action="escalate_to_user",
        )
    if ex_name == "TimeoutError":
        return ToolError(
            type=ErrorType.TIMEOUT,
            message=ex_msg,
            retryable=True,
            suggested_action="retry_or_reduce_scope",
        )

    return ToolError(
        type=ErrorType.UNKNOWN,
        message=f"{ex_name}: {ex_msg}",
        retryable=False,
        suggested_action="analyze_and_decide",
    )


# ── Normalizer ───────────────────────────────────────────────────────────────

class ResultNormalizer:
    """Wraps raw tool output into structured ToolResult before injection.

    Each tool type gets its own classifier.  The normalizer is tool-type-aware
    because a bash failure means something different from a read_file failure.
    """

    MAX_CONTENT_LENGTH = 50000   # characters, before truncation

    def __init__(self):
        self._tool_error_count: dict[str, int] = {}

    # ── Per-tool wrapping ───────────────────────────────────────────────────

    def wrap_bash(
        self,
        command: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_ms: float,
    ) -> ToolResult:
        """Wrap a bash execution result."""
        if exit_code == 0:
            content = stdout or "(no output)"
            full_len = len(content)
            truncated = content[:self.MAX_CONTENT_LENGTH]
            return ToolResult(
                tool_name="bash",
                success=True,
                data=truncated,
                duration_ms=duration_ms,
                truncated_bytes=full_len - len(truncated) if full_len > self.MAX_CONTENT_LENGTH else 0,
            )
        # Failure
        error = _classify_bash_error(stderr, exit_code, stdout)
        self._record_error("bash", error)
        return ToolResult(
            tool_name="bash",
            success=False,
            data=stdout[:5000] if stdout else None,   # partial stdout may help diagnosis
            error=error,
            duration_ms=duration_ms,
        )

    def wrap_bash_timeout(self, command: str, duration_ms: float) -> ToolResult:
        """Wrap a bash timeout."""
        error = ToolError(
            type=ErrorType.TIMEOUT,
            message=f"Command timed out after {duration_ms / 1000:.0f}s",
            retryable=True,
            suggested_action="retry_with_shorter_timeout_or_split_work",
        )
        self._record_error("bash", error)
        return ToolResult(
            tool_name="bash",
            success=False,
            error=error,
            duration_ms=duration_ms,
        )

    def wrap_bash_blocked(self, command: str, reason: str) -> ToolResult:
        """Wrap a blocked (dangerous) command."""
        error = ToolError(
            type=ErrorType.PERMISSION,
            message=f"Command blocked: {reason}",
            retryable=False,
            suggested_action="use_safer_alternative_or_escalate",
        )
        self._record_error("bash", error)
        return ToolResult(
            tool_name="bash",
            success=False,
            error=error,
            duration_ms=0,
        )

    def wrap_read(
        self,
        path: str,
        content: str | None,
        exception: Exception | None,
        duration_ms: float,
    ) -> ToolResult:
        """Wrap a file read result."""
        if exception is None and content is not None:
            full_len = len(content)
            truncated = content[:self.MAX_CONTENT_LENGTH]
            return ToolResult(
                tool_name="read_file",
                success=True,
                data=truncated,
                duration_ms=duration_ms,
                truncated_bytes=full_len - len(truncated) if full_len > self.MAX_CONTENT_LENGTH else 0,
            )
        error = _classify_file_error(exception) if exception else ToolError(
            type=ErrorType.UNKNOWN, message="Unknown read error",
            retryable=False, suggested_action="investigate",
        )
        self._record_error("read_file", error)
        return ToolResult(
            tool_name="read_file",
            success=False,
            error=error,
            duration_ms=duration_ms,
        )

    def wrap_write(
        self,
        path: str,
        bytes_written: int,
        exception: Exception | None,
        duration_ms: float,
    ) -> ToolResult:
        """Wrap a file write result."""
        if exception is None:
            return ToolResult(
                tool_name="write_file",
                success=True,
                data=f"Wrote {bytes_written} bytes to {path}",
                duration_ms=duration_ms,
            )
        error = _classify_file_error(exception)
        self._record_error("write_file", error)
        return ToolResult(
            tool_name="write_file",
            success=False,
            error=error,
            duration_ms=duration_ms,
        )

    def wrap_edit(
        self,
        path: str,
        old_text: str,
        exception: Exception | None,
        duration_ms: float,
    ) -> ToolResult:
        """Wrap a file edit result."""
        if exception is None:
            return ToolResult(
                tool_name="edit_file",
                success=True,
                data=f"Edited {path}",
                duration_ms=duration_ms,
            )
        error = _classify_file_error(exception)
        self._record_error("edit_file", error)
        return ToolResult(
            tool_name="edit_file",
            success=False,
            error=error,
            duration_ms=duration_ms,
        )

    def wrap_edit_not_found(self, path: str, duration_ms: float) -> ToolResult:
        """Wrap a failed edit where old_text was not found in file."""
        error = ToolError(
            type=ErrorType.INVALID_INPUT,
            message=f"Replace text not found in {path}. The file may have changed.",
            retryable=False,
            suggested_action="re_read_file_and_retry",
        )
        self._record_error("edit_file", error)
        return ToolResult(
            tool_name="edit_file",
            success=False,
            error=error,
            duration_ms=duration_ms,
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _record_error(self, tool_name: str, error: ToolError):
        key = f"{tool_name}:{error.type.value}"
        self._tool_error_count[key] = self._tool_error_count.get(key, 0) + 1

    def error_summary(self) -> dict:
        """Return per-tool per-error-type counts for diagnostics."""
        return dict(self._tool_error_count)


# ── Convenience: inject into agent loop ─────────────────────────────────────

def normalize_result(
    normalizer: ResultNormalizer,
    tool_name: str,
    raw: Any,
    duration_ms: float,
    **kwargs,
) -> ToolResult:
    """Single dispatch point: call the right wrap method by tool_name.

    This is the function you call at the harness seam — after tool execution,
    before appending to messages.
    """
    dispatch = {
        "bash": lambda: _normalize_bash(normalizer, raw, duration_ms, **kwargs),
        "read_file": lambda: _normalize_read(normalizer, raw, duration_ms, **kwargs),
        "write_file": lambda: _normalize_write(normalizer, raw, duration_ms, **kwargs),
        "edit_file": lambda: _normalize_edit(normalizer, raw, duration_ms, **kwargs),
    }
    handler = dispatch.get(tool_name)
    if handler:
        return handler()
    # Unknown tool: pass through as success
    return ToolResult(
        tool_name=tool_name,
        success=True,
        data=str(raw),
        duration_ms=duration_ms,
    )


def _normalize_bash(normalizer, raw, duration_ms, **kwargs):
    """Raw is (stdout, stderr, exit_code) or special sentinel string."""
    if isinstance(raw, tuple) and len(raw) == 3:
        return normalizer.wrap_bash(
            command=kwargs.get("command", ""),
            stdout=raw[0], stderr=raw[1], exit_code=raw[2],
            duration_ms=duration_ms,
        )
    if isinstance(raw, str) and raw.startswith("TIMEOUT:"):
        return normalizer.wrap_bash_timeout(kwargs.get("command", ""), duration_ms)
    if isinstance(raw, str) and raw.startswith("BLOCKED:"):
        return normalizer.wrap_bash_blocked(kwargs.get("command", ""), raw.replace("BLOCKED:", ""))
    return normalizer.wrap_bash(kwargs.get("command", ""), str(raw), "", 0, duration_ms)


def _normalize_read(normalizer, raw, duration_ms, **kwargs):
    if isinstance(raw, Exception):
        return normalizer.wrap_read(kwargs.get("path", ""), None, raw, duration_ms)
    return normalizer.wrap_read(kwargs.get("path", ""), str(raw), None, duration_ms)


def _normalize_write(normalizer, raw, duration_ms, **kwargs):
    if isinstance(raw, Exception):
        return normalizer.wrap_write(kwargs.get("path", ""), 0, raw, duration_ms)
    return normalizer.wrap_write(kwargs.get("path", ""), len(str(raw)), None, duration_ms)


def _normalize_edit(normalizer, raw, duration_ms, **kwargs):
    if isinstance(raw, Exception):
        return normalizer.wrap_edit(kwargs.get("path", ""), kwargs.get("old_text", ""), raw, duration_ms)
    if isinstance(raw, str) and raw.startswith("NOT_FOUND:"):
        return normalizer.wrap_edit_not_found(kwargs.get("path", ""), duration_ms)
    return normalizer.wrap_edit(kwargs.get("path", ""), kwargs.get("old_text", ""), None, duration_ms)
