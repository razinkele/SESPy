"""Unit tests for the Claude Code session-transcript importer."""
from __future__ import annotations

import json

import pytest

from sespy import claude_session_import as csi
from sespy.claude_session_import import (
    ClaudeSession,
    claude_projects_dir,
    decode_content,
    discover_session_files,
    load_sessions,
    parse_session_file,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers — synthesise a ~/.claude/projects tree on disk.
# ---------------------------------------------------------------------------

def _rec(**kw):
    return json.dumps(kw)


def _write_session(projects_dir, project, session_id, records):
    folder = projects_dir / project
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session_id}.jsonl"
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def projects_dir(tmp_path):
    return tmp_path / "projects"


# ---------------------------------------------------------------------------
# claude_projects_dir — resolution precedence
# ---------------------------------------------------------------------------

def test_projects_dir_explicit_base_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "ignored"))
    assert claude_projects_dir(tmp_path / "x") == tmp_path / "x"


def test_projects_dir_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert claude_projects_dir() == tmp_path / "cfg" / "projects"


def test_projects_dir_defaults_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(csi.Path, "home", classmethod(lambda cls: tmp_path))
    assert claude_projects_dir() == tmp_path / ".claude" / "projects"


# ---------------------------------------------------------------------------
# decode_content — string vs block-list flattening
# ---------------------------------------------------------------------------

def test_decode_plain_string():
    assert decode_content("hello world") == "hello world"


def test_decode_non_string_non_list_is_empty():
    assert decode_content(None) == ""
    assert decode_content(42) == ""


def test_decode_text_blocks_joined():
    content = [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
    ]
    assert decode_content(content) == "first\n\nsecond"


def test_decode_excludes_thinking_and_tools_by_default():
    content = [
        {"type": "thinking", "thinking": "secret reasoning"},
        {"type": "text", "text": "visible answer"},
        {"type": "tool_use", "name": "bash"},
    ]
    assert decode_content(content) == "visible answer"


def test_decode_keeps_thinking_when_asked():
    content = [
        {"type": "thinking", "thinking": "reasoning"},
        {"type": "text", "text": "answer"},
    ]
    assert decode_content(content, keep_thinking=True) == "reasoning\n\nanswer"


def test_decode_keeps_tool_calls_when_asked():
    content = [
        {"type": "tool_use", "name": "bash"},
        {"type": "tool_result", "content": "ok"},
    ]
    out = decode_content(content, keep_tool_calls=True)
    assert "[tool_use: bash]" in out
    assert "[tool_result]\nok" in out


def test_decode_nested_tool_result_blocks():
    content = [
        {"type": "tool_result", "content": [{"type": "text", "text": "nested"}]},
    ]
    out = decode_content(content, keep_tool_calls=True)
    assert "nested" in out


# ---------------------------------------------------------------------------
# iter_records — defensive line parsing
# ---------------------------------------------------------------------------

def test_iter_records_skips_blank_and_malformed(tmp_path):
    path = tmp_path / "s.jsonl"
    path.write_text(
        '{"type":"user"}\n\nnot json\n{"type":"assistant"}\n', encoding="utf-8"
    )
    types = [r.get("type") for r in csi.iter_records(path)]
    assert types == ["user", "assistant"]


def test_iter_records_missing_file_is_empty(tmp_path):
    assert list(csi.iter_records(tmp_path / "nope.jsonl")) == []


# ---------------------------------------------------------------------------
# parse_session_file — end-to-end record → session
# ---------------------------------------------------------------------------

def test_parse_basic_conversation(projects_dir):
    records = [
        _rec(type="summary", summary="Fixing the bug"),
        _rec(
            type="user",
            message={"role": "user", "content": "please help"},
            uuid="u1",
            timestamp="2026-06-01T10:00:00.000Z",
            cwd="C:\\work\\proj",
        ),
        _rec(
            type="assistant",
            message={"role": "assistant", "content": [
                {"type": "thinking", "thinking": "hmm"},
                {"type": "text", "text": "sure, here you go"},
            ]},
            uuid="a1",
            timestamp="2026-06-01T10:00:05.000Z",
        ),
    ]
    path = _write_session(projects_dir, "proj-slug", "sess-123", records)

    session = parse_session_file(path)

    assert isinstance(session, ClaudeSession)
    assert session.session_id == "sess-123"
    assert session.project == "proj-slug"
    assert session.cwd == "C:\\work\\proj"
    assert session.summary == "Fixing the bug"
    assert session.started_at == "2026-06-01T10:00:00.000Z"
    assert session.ended_at == "2026-06-01T10:00:05.000Z"
    assert session.message_count == 2
    assert session.user_count == 1
    assert session.assistant_count == 1
    assert session.messages[0].role == "user"
    assert session.messages[0].text == "please help"
    # thinking excluded by default
    assert session.messages[1].text == "sure, here you go"
    assert session.title == "Fixing the bug"


def test_parse_drops_empty_assistant_turns(projects_dir):
    # An assistant turn that is pure thinking/tool-use decodes to "" -> dropped.
    records = [
        _rec(type="user", message={"role": "user", "content": "hi"}),
        _rec(type="assistant", message={"role": "assistant", "content": [
            {"type": "thinking", "thinking": "only reasoning"},
        ]}),
    ]
    path = _write_session(projects_dir, "p", "s", records)
    session = parse_session_file(path)
    assert session.message_count == 1
    assert session.messages[0].role == "user"


def test_parse_keep_thinking_retains_turn(projects_dir):
    records = [
        _rec(type="assistant", message={"role": "assistant", "content": [
            {"type": "thinking", "thinking": "reasoning kept"},
        ]}),
    ]
    path = _write_session(projects_dir, "p", "s", records)
    session = parse_session_file(path, keep_thinking=True)
    assert session.message_count == 1
    assert "reasoning kept" in session.messages[0].text


def test_parse_ignores_non_conversation_types(projects_dir):
    records = [
        _rec(type="queue-operation", operation="enqueue"),
        _rec(type="attachment", uuid="x"),
        _rec(type="file-history-snapshot"),
        _rec(type="user", message={"role": "user", "content": "real turn"}),
    ]
    path = _write_session(projects_dir, "p", "s", records)
    session = parse_session_file(path)
    assert session.message_count == 1


def test_title_falls_back_to_first_user_message(projects_dir):
    long_msg = "x" * 200
    records = [_rec(type="user", message={"role": "user", "content": long_msg})]
    path = _write_session(projects_dir, "p", "s", records)
    session = parse_session_file(path)
    assert session.summary == ""
    assert session.title.endswith("…")
    assert len(session.title) == 81  # 80 chars + ellipsis


def test_title_falls_back_to_session_id(projects_dir):
    records = [_rec(type="assistant", message={"role": "assistant", "content": [
        {"type": "thinking", "thinking": "x"},
    ]})]
    path = _write_session(projects_dir, "p", "only-id", records)
    session = parse_session_file(path)
    assert session.title == "only-id"


# ---------------------------------------------------------------------------
# discover_session_files / load_sessions — directory traversal
# ---------------------------------------------------------------------------

def test_discover_missing_dir_returns_empty(tmp_path):
    assert discover_session_files(tmp_path / "absent") == []


def test_discover_finds_nested_sessions(projects_dir):
    _write_session(projects_dir, "p1", "a", [_rec(type="user",
                   message={"role": "user", "content": "hi"})])
    _write_session(projects_dir, "p2", "b", [_rec(type="user",
                   message={"role": "user", "content": "yo"})])
    found = discover_session_files(projects_dir)
    assert {p.stem for p in found} == {"a", "b"}


def test_discover_orders_newest_first(projects_dir):
    old = _write_session(projects_dir, "p", "old", [_rec(type="user",
                         message={"role": "user", "content": "x"})])
    new = _write_session(projects_dir, "p", "new", [_rec(type="user",
                         message={"role": "user", "content": "y"})])
    import os
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))
    found = discover_session_files(projects_dir)
    assert [p.stem for p in found] == ["new", "old"]


def test_load_sessions_skips_empty_by_default(projects_dir):
    _write_session(projects_dir, "p", "has-msgs", [_rec(type="user",
                   message={"role": "user", "content": "hi"})])
    _write_session(projects_dir, "p", "empty", [
        _rec(type="queue-operation", operation="enqueue")])
    sessions = load_sessions(projects_dir)
    assert [s.session_id for s in sessions] == ["has-msgs"]


def test_load_sessions_include_empty(projects_dir):
    _write_session(projects_dir, "p", "empty", [
        _rec(type="queue-operation", operation="enqueue")])
    sessions = load_sessions(projects_dir, skip_empty=False)
    assert [s.session_id for s in sessions] == ["empty"]
