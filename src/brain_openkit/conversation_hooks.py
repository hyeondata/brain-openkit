"""Local transcript adapters. Reading a transcript never invokes a model."""

import json
import os
from pathlib import Path
import stat
import sys
import time


MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024
MAX_HOOK_BYTES = 1024 * 1024


def read_jsonl(path: Path, *, max_bytes: int = MAX_TRANSCRIPT_BYTES,
               allow_partial: bool = False) -> list[dict]:
    """Read one bounded transcript, leaving an unfinished final record for retry."""
    records, partial = _read_jsonl(path, max_bytes=max_bytes)
    if partial and not allow_partial:
        raise ValueError("transcript_not_flushed")
    return records


def _read_regular(path: Path, max_bytes: int) -> bytes:
    from .changes import _Tree, _reject_link
    path = Path(os.path.abspath(path))
    # macOS publishes these fixed OS aliases; do not resolve arbitrary links.
    if sys.platform == "darwin" and len(path.parts) > 1 and path.parts[1] in {"var", "tmp"}:
        alias = Path("/") / path.parts[1]
        if alias.is_symlink() and os.readlink(alias) in {"private/" + path.parts[1], "/private/" + path.parts[1]}:
            path = Path("/private") / path.relative_to("/")
    tree = _Tree(Path(path.anchor))
    try:
        with tree.parent(path.relative_to(path.anchor).as_posix()) as (descriptor, parent, leaf):
            location, arguments = tree._at(descriptor, parent, leaf)
            metadata = os.stat(location, follow_symlinks=False, **arguments)
            _reject_link(metadata)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("invalid_transcript")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
            with os.fdopen(os.open(location, flags, **arguments), "rb") as source:
                opened = os.fstat(source.fileno())
                if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                        or not os.path.samestat(metadata, opened)):
                    raise ValueError("invalid_transcript")
                if opened.st_size > max_bytes:
                    raise ValueError("transcript_too_large")
                raw = source.read(max_bytes + 1)
    finally:
        tree.close()
    if len(raw) > max_bytes:
        raise ValueError("transcript_too_large")
    return raw


def _read_jsonl(path: Path, *, max_bytes: int = MAX_TRANSCRIPT_BYTES) -> tuple[list[dict], bool]:
    raw = _read_regular(path, max_bytes)
    lines = raw.splitlines(keepends=True)
    records = []
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError):
            if index == len(lines) - 1 and not line.endswith(b"\n"):
                return records, True
            raise ValueError("invalid_transcript") from None
        if not isinstance(record, dict):
            raise ValueError("invalid_transcript")
        records.append(record)
    return records, False


def _text_parts(content) -> list[str]:
    if isinstance(content, str):
        return [content] if content else []
    if not isinstance(content, list):
        return []
    return [block["text"] for block in content
            if isinstance(block, dict) and block.get("type") == "text"
            and isinstance(block.get("text"), str) and block["text"]]


def parse_claude_transcript(records: list[dict], *, include_tool_output: bool = False) -> list[dict]:
    """Extract original text records, not tool calls, thoughts or injected context."""
    messages = []
    seen = {}
    for record in records:
        role = record.get("type")
        if role not in {"user", "assistant"} or any(record.get(flag) for flag in (
                "isMeta", "isSynthetic", "isSidechain", "isCompactSummary", "isApiErrorMessage")):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        if not isinstance(blocks, list):
            continue
        normalized = []
        pending = []
        for block in [*blocks, None]:
            if (isinstance(block, dict) and block.get("type") == "text"
                    and isinstance(block.get("text"), str)):
                pending.append(block["text"])
                continue
            if pending:
                text = "".join(pending)
                if text:
                    normalized.append({"role": role, "text": text})
                pending = []
            if (include_tool_output and role == "user" and isinstance(block, dict)
                    and block.get("type") == "tool_result"):
                text = "".join(_text_parts(block.get("content")))
                if text:
                    normalized.append({"role": "tool", "text": text})
        identifier = record.get("uuid")
        if isinstance(identifier, str) and identifier:
            if identifier in seen:
                if seen[identifier] != normalized:
                    raise ValueError("conflicting_transcript_replay")
                continue
            seen[identifier] = normalized
        messages.extend(normalized)
    return messages


def _parse_records(host: str, records: list[dict], include_tool_output: bool) -> list[dict]:
    if host == "claude":
        return parse_claude_transcript(records, include_tool_output=include_tool_output)
    if host == "codex":
        from .codex_transcripts import parse_codex_transcript
        return parse_codex_transcript(records, include_tool_output=include_tool_output)
    raise ValueError("unsupported_host")


def parse_transcript(host: str, path: Path, include_tool_output: bool = False) -> list[dict]:
    """Parse an explicitly supplied transcript; this lower-level function reads it."""
    return _parse_records(host, read_jsonl(path), include_tool_output)


def _validate_session(records: list[dict], host: str, session_id: str) -> None:
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("invalid_session")
    for record in records:
        identities = [record[key] for key in ("sessionId", "session_id") if key in record]
        if host == "codex" and isinstance(record.get("payload"), dict):
            payload = record["payload"]
            keys = ("id", "session_id") if record.get("type") == "session_meta" else ("thread_id",)
            identities.extend(payload[key] for key in keys if key in payload)
        if any(identity != session_id for identity in identities):
            raise ValueError("session_mismatch")


def capture_transcript(vault: Path, host: str, session_id: str, path: Path,
                       last_assistant_message: str | None = None, *,
                       retry_delays=(0.05, 0.1, 0.2)) -> dict:
    """Check opt-in before reading and defer snapshots whose final text is unflushed."""
    from . import conversations
    info = conversations.status(vault)
    if not info["enabled"]:
        return {"status": "disabled"}
    if host not in {"claude", "codex", "auto"}:
        return {"status": "blocked", "reason": "unsupported_host"}
    for delay in (0, *retry_delays):
        if delay:
            time.sleep(delay)
        try:
            records, partial = _read_jsonl(path)
            selected_host = ("codex" if records and records[0].get("type") == "session_meta" else "claude") if host == "auto" else host
            _validate_session(records, selected_host, session_id)
            messages = _parse_records(selected_host, records, info["config"]["include_tool_output"])
        except FileNotFoundError:
            continue
        except (ValueError, TypeError, OSError):
            return {"status": "blocked", "reason": "invalid_transcript"}
        if partial:
            continue
        if last_assistant_message:
            final = next((message["text"] for message in reversed(messages)
                          if message["role"] == "assistant"), None)
            if final != last_assistant_message:
                continue
        return conversations.capture(vault, selected_host, session_id, messages)
    return {"status": "pending_transcript", "reason": "transcript_not_flushed"}


def handle_hook(payload: dict, *, environ: dict | None = None) -> dict:
    """Route only the current hook's transcript to its explicitly selected vault."""
    if payload.get("hook_event_name") not in {"Stop", "SessionEnd"}:
        return {"status": "ignored"}
    environment = os.environ if environ is None else environ
    selected = environment.get("BRAIN_OPENKIT_VAULT")
    if not selected:
        selected = payload.get("cwd")
        if not isinstance(selected, str) or not (Path(selected) / ".brain-openkit/conversations.json").is_file():
            return {"status": "disabled"}
    session_id = payload.get("session_id")
    path = payload.get("transcript_path")
    # Do not discover a transcript by searching history directories.
    host = "codex" if "turn_id" in payload else "auto"
    return capture_transcript(Path(selected), host, session_id, path,
                              last_assistant_message=payload.get("last_assistant_message"))


def _warning(result: dict) -> dict | None:
    if result.get("status") not in {"blocked", "pending_transcript"}:
        return None
    reasons = {
        "size_limit": "archive size limit reached",
        "session_limit": "session size limit reached",
        "history_conflict": "transcript history changed",
        "edited": "the saved conversation was edited",
        "transcript_not_flushed": "transcript is not ready; retry on the next turn or with explicit capture",
        "invalid_transcript": "transcript is unavailable or invalid",
    }
    reason = reasons.get(result.get("reason"), "capture could not complete")
    return {"systemMessage": "Brain OpenKit conversation auto-save paused: " + reason + "."}


def main() -> int:
    """Never block the host turn or ask its model to repair a capture failure."""
    try:
        raw = sys.stdin.buffer.read(MAX_HOOK_BYTES + 1)
        if len(raw) > MAX_HOOK_BYTES:
            result = {"status": "blocked", "reason": "invalid_transcript"}
        else:
            payload = json.loads(raw)
            result = handle_hook(payload) if isinstance(payload, dict) else {"status": "ignored"}
        warning = _warning(result)
    except Exception:
        # Hook errors must not expose transcript paths, text or exception details.
        warning = _warning({"status": "blocked"})
    if warning:
        print(json.dumps(warning))
    return 0
