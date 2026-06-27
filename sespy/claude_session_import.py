"""Claude Code session-transcript importer — companion to excel_import.py /
qsem_import.py, but for *conversation logs* rather than SES model data.

Claude Code (the Anthropic CLI) records each session as a JSON Lines file at::

    ~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl

One JSON object per line. Lines come in many `type`s — `queue-operation`,
`attachment`, `system`, `file-history-snapshot`, `summary`, `user`,
`assistant`, … — but for a plain conversation log we only care about `user`
and `assistant` turns, plus the optional `summary` record that carries a
human-readable title.

This module is pure Python (no Shiny imports) so it stays unit-testable and
importable in any environment. It is deliberately defensive: a Claude
transcript is an append-only log written by a different program and version,
so every field access is `.get`-safe and malformed lines are skipped rather
than raising.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Record `type` values that represent a turn in the conversation.
_USER = "user"
_ASSISTANT = "assistant"
_SUMMARY = "summary"


@dataclass(frozen=True)
class ClaudeMessage:
    """A single conversation turn, flattened to plain text.

    `role` is "user" or "assistant". `text` is the decoded human-readable
    content (thinking / tool blocks excluded by default — see
    `parse_session_file`). `timestamp` is the raw ISO-8601 string from the
    transcript (kept as text — Claude writes it as UTC `...Z`), or "" if the
    record had none. `uuid` is the record's own id, useful for de-duping or
    threading.
    """

    role: str
    text: str
    timestamp: str = ""
    uuid: str = ""


@dataclass(frozen=True)
class ClaudeSession:
    """A parsed Claude Code session transcript.

    `session_id` comes from the file stem (the session UUID). `project` is the
    encoded project-directory name (Claude's lossy slug of the original cwd);
    `cwd` is the *real* working directory recovered from inside the records.
    `summary` is the session's title if Claude wrote a `summary` record, else
    "". `started_at` / `ended_at` are the first / last timestamps seen across
    *all* records (not just kept turns), so they bound the whole session.
    """

    session_id: str
    project: str
    cwd: str
    summary: str
    file_path: str
    started_at: str
    ended_at: str
    messages: tuple[ClaudeMessage, ...] = field(default_factory=tuple)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_count(self) -> int:
        return sum(1 for m in self.messages if m.role == _USER)

    @property
    def assistant_count(self) -> int:
        return sum(1 for m in self.messages if m.role == _ASSISTANT)

    @property
    def title(self) -> str:
        """A display label: the summary if present, else the first user
        message clipped, else the bare session id."""
        if self.summary:
            return self.summary
        for m in self.messages:
            if m.role == _USER and m.text:
                line = m.text.strip().splitlines()[0]
                return line[:80] + ("…" if len(line) > 80 else "")
        return self.session_id


def claude_projects_dir(base: Path | str | None = None) -> Path:
    """Resolve the directory that holds per-project session folders.

    Precedence: explicit `base` arg → `$CLAUDE_CONFIG_DIR/projects` →
    `~/.claude/projects`. The path is returned whether or not it exists; call
    `.exists()` at the use-site.
    """
    if base is not None:
        return Path(base)
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    root = Path(env) if env else Path.home() / ".claude"
    return root / "projects"


def decode_content(
    content: Any,
    *,
    keep_thinking: bool = False,
    keep_tool_calls: bool = False,
) -> str:
    """Flatten a Claude `message.content` value to plain text.

    Claude stores content either as a plain string (simple user turns) or as a
    list of typed blocks (`text`, `thinking`, `tool_use`, `tool_result`, …).
    By default only `text` blocks contribute, so the result is the human-
    readable conversation. Set `keep_thinking` to fold in assistant reasoning
    and `keep_tool_calls` to fold in tool invocations + their results.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            if isinstance(block, str):
                parts.append(block)
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        elif btype == "thinking":
            if keep_thinking:
                text = block.get("thinking")
                if isinstance(text, str) and text:
                    parts.append(text)
        elif btype == "tool_use":
            if keep_tool_calls:
                name = block.get("name", "tool")
                parts.append(f"[tool_use: {name}]")
        elif btype == "tool_result":
            if keep_tool_calls:
                inner = decode_content(
                    block.get("content"),
                    keep_thinking=keep_thinking,
                    keep_tool_calls=keep_tool_calls,
                )
                if inner:
                    parts.append(f"[tool_result]\n{inner}")
    return "\n\n".join(parts)


def iter_records(path: Path | str) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a `.jsonl` transcript, one per line.

    Blank lines and lines that aren't valid JSON objects are skipped — a
    truncated final line (common while a session is still being written) won't
    abort the parse.
    """
    p = Path(path)
    try:
        handle = p.open("r", encoding="utf-8")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                yield obj


def parse_session_file(
    path: Path | str,
    *,
    keep_thinking: bool = False,
    keep_tool_calls: bool = False,
) -> ClaudeSession:
    """Parse one `.jsonl` transcript into a `ClaudeSession`.

    Only `user` and `assistant` records become messages, and only if they
    decode to non-empty text (so an assistant turn that is pure thinking /
    tool-use is dropped unless the matching `keep_*` flag is set). `summary`,
    `cwd`, and the session timestamp bounds are harvested from whichever
    records carry them.
    """
    path = Path(path)
    messages: list[ClaudeMessage] = []
    summary = ""
    cwd = ""
    started_at = ""
    ended_at = ""

    for rec in iter_records(path):
        rtype = rec.get("type")

        ts = rec.get("timestamp")
        if isinstance(ts, str) and ts:
            if not started_at or ts < started_at:
                started_at = ts
            if ts > ended_at:
                ended_at = ts

        if rtype == _SUMMARY:
            s = rec.get("summary")
            if isinstance(s, str) and s and not summary:
                summary = s
            continue

        if rtype not in (_USER, _ASSISTANT):
            continue

        if not cwd:
            rcwd = rec.get("cwd")
            if isinstance(rcwd, str) and rcwd:
                cwd = rcwd

        message = rec.get("message")
        if not isinstance(message, dict):
            continue
        text = decode_content(
            message.get("content"),
            keep_thinking=keep_thinking,
            keep_tool_calls=keep_tool_calls,
        ).strip()
        if not text:
            continue

        messages.append(
            ClaudeMessage(
                role=rtype,
                text=text,
                timestamp=ts if isinstance(ts, str) else "",
                uuid=rec.get("uuid", "") if isinstance(rec.get("uuid"), str) else "",
            )
        )

    return ClaudeSession(
        session_id=path.stem,
        project=path.parent.name,
        cwd=cwd,
        summary=summary,
        file_path=str(path),
        started_at=started_at,
        ended_at=ended_at,
        messages=tuple(messages),
    )


def discover_session_files(base: Path | str | None = None) -> list[Path]:
    """List every session `.jsonl` under the Claude projects dir, newest-first
    by modification time. Returns [] if the directory is absent."""
    root = claude_projects_dir(base)
    if not root.is_dir():
        return []
    files = [p for p in root.glob("*/*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def load_sessions(
    base: Path | str | None = None,
    *,
    keep_thinking: bool = False,
    keep_tool_calls: bool = False,
    skip_empty: bool = True,
) -> list[ClaudeSession]:
    """Discover and parse every Claude Code session, newest-first.

    `skip_empty` drops sessions with no conversation turns (pure tool / agent
    transcripts), which is usually what a human browsing their chat history
    wants. Set it False to get every transcript on disk.
    """
    sessions: list[ClaudeSession] = []
    for path in discover_session_files(base):
        session = parse_session_file(
            path,
            keep_thinking=keep_thinking,
            keep_tool_calls=keep_tool_calls,
        )
        if skip_empty and not session.messages:
            continue
        sessions.append(session)
    return sessions
