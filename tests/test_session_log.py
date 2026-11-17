"""Tests for the Copilot agent session log parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prinfo.session_log import (
    MAX_ARGUMENT_CHARS,
    ParsedSessionLog,
    TranscriptEvent,
    curate_session_metadata,
    parse_session_log,
    render_transcript,
)

FIXTURE = Path(__file__).parent / "fixtures" / "agent_session_log.sse"


def _chunk(delta: dict) -> str:
    return "data: " + json.dumps({"choices": [{"delta": delta}]})


def _tool_chunk(name: str, arguments: str) -> str:
    call = {
        "id": "c",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
    return _chunk({"tool_calls": [call]})


@pytest.fixture
def parsed() -> ParsedSessionLog:
    return parse_session_log(FIXTURE.read_bytes())


def test_fixture_event_order(parsed: ParsedSessionLog) -> None:
    summary = [(e.kind, e.tool_name) for e in parsed.events]
    assert summary == [
        ("assistant", None),
        ("tool_call", "view"),
        ("tool_call", "rg"),
        ("tool_call", "store_comment"),
        ("assistant", None),
        ("tool_call", "store_comment"),
    ]


def test_fixture_unparsed_count(parsed: ParsedSessionLog) -> None:
    assert parsed.unparsed_events == 1


def test_fixture_findings_with_suggested_fix(parsed: ParsedSessionLog) -> None:
    assert len(parsed.findings) == 2
    first = parsed.findings[0]
    assert list(first) == [
        "type",
        "path",
        "start_line",
        "end_line",
        "body",
        "suggested_fix",
        "fix_skip_reason",
        "fix_skip_note",
        "fixed",
        "extra",
    ]
    assert first["type"] == "bug"
    assert first["path"] == "src/app/example.py"
    assert first["start_line"] == 10
    assert first["end_line"] == 12
    assert first["body"] == "Division by zero when count is 0."
    assert first["suggested_fix"] == "if count == 0:\n    return 0"
    assert first["fix_skip_reason"] is None
    assert first["fix_skip_note"] is None
    assert first["fixed"] is True
    assert first["extra"] == {"confidence": "high"}


def test_fixture_finding_with_skip_reason(parsed: ParsedSessionLog) -> None:
    second = parsed.findings[1]
    assert second["type"] == "suggestion"
    assert second["suggested_fix"] is None
    assert second["fix_skip_reason"] == "needs_design"
    assert second["fix_skip_note"] == "Rename affects public API."
    assert second["fixed"] is False
    assert second["extra"] == {}


def test_no_store_comment_means_no_findings() -> None:
    raw = "\n\n".join(
        [_chunk({"content": "hello"}), _tool_chunk("view", "{}")]
    ).encode()
    result = parse_session_log(raw)
    assert result.findings == []
    assert result.unparsed_events == 0
    assert len(result.events) == 2


def test_store_comment_with_non_dict_arguments_is_unparsed() -> None:
    result = parse_session_log(_tool_chunk("store_comment", "[1, 2]").encode())
    assert result.findings == []
    assert result.unparsed_events == 1
    assert len(result.events) == 1


def test_non_dict_json_is_unparsed() -> None:
    result = parse_session_log(b"data: [1]\ndata: [DONE]\n: comment\n")
    assert result.unparsed_events == 1
    assert result.events == []


def test_non_utf8_bytes_do_not_raise() -> None:
    raw = _chunk({"content": "ok"}).encode() + b"\ndata: \xff\xfe\n"
    result = parse_session_log(raw)
    assert result.unparsed_events == 1
    assert result.events[0].text == "ok"


def test_render_transcript_order_and_unique_headings(parsed: ParsedSessionLog) -> None:
    text = render_transcript(parsed, session_id="abc-123")
    assert text.startswith("# Session abc-123\n")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert len(headings) == len(set(headings))
    assert headings == [
        "# Session abc-123",
        "## 1. Assistant",
        "## 2. Tool call: view",
        "## 3. Tool call: rg",
        "## 4. Tool call: store_comment",
        "## 5. Assistant",
        "## 6. Tool call: store_comment",
    ]
    assert "(1 unparsed event(s) skipped)" in text
    assert "arguments truncated" not in text


def test_render_truncates_long_arguments() -> None:
    long_args = "x" * (MAX_ARGUMENT_CHARS + 500)
    parsed = ParsedSessionLog(
        events=[TranscriptEvent("tool_call", None, "view", long_args)],
        findings=[],
        unparsed_events=0,
    )
    text = render_transcript(parsed, session_id="s")
    assert "x" * MAX_ARGUMENT_CHARS in text
    assert "x" * (MAX_ARGUMENT_CHARS + 1) not in text
    assert "(arguments truncated: showed 4000 of 4500 characters)" in text


def test_render_fence_longer_than_backtick_run() -> None:
    parsed = ParsedSessionLog(
        events=[TranscriptEvent("tool_call", None, "t", "a ```` b")],
        findings=[],
        unparsed_events=0,
    )
    assert "`````\na ```` b\n`````" in render_transcript(parsed, session_id="s")


def test_render_no_events() -> None:
    parsed = ParsedSessionLog(events=[], findings=[], unparsed_events=0)
    text = render_transcript(parsed, session_id="s")
    assert text == "# Session s\n\n(no events)\n"


def test_curate_drops_identifying_fields() -> None:
    raw = {
        "id": "sess-1",
        "name": "Review",
        "state": "completed",
        "user_login": "planted-login",
        "user_id": 987654,
        "request_id": "req-planted",
        "access_type": "planted-access",
        "settings": {"secret": "planted-setting"},
    }
    curated = curate_session_metadata(raw)
    assert list(curated) == [
        "id",
        "name",
        "agent_slug",
        "event_type",
        "state",
        "created_at",
        "completed_at",
        "last_updated_at",
        "model",
        "head_ref",
        "base_ref",
        "workflow_run_id",
        "error",
    ]
    assert curated["id"] == "sess-1"
    assert curated["agent_slug"] is None
    for key in ("user_login", "user_id", "request_id", "access_type", "settings"):
        assert key not in curated
    dumped = json.dumps(curated)
    for value in (
        "planted-login",
        "987654",
        "req-planted",
        "planted-access",
        "planted-setting",
    ):
        assert value not in dumped


def test_curate_decodes_event_identifiers() -> None:
    entry = (
        'review:{"review_pass": 2, "head_sha": "abc123", '
        '"user_login": "someone", "settings": {"x": 1}}'
    )
    for identifiers in ([entry], entry, json.dumps([entry])):
        curated = curate_session_metadata({"id": "s", "event_identifiers": identifiers})
        assert curated["review_pass"] == 2
        assert curated["head_sha"] == "abc123"
        assert "user_login" not in curated
        assert "settings" not in curated
        assert "event_identifiers" not in curated
        assert "someone" not in json.dumps(curated)


def test_curate_first_identifier_occurrence_wins() -> None:
    raw = {"event_identifiers": ['a:{"head_sha": "first"}', 'b:{"head_sha": "second"}']}
    assert curate_session_metadata(raw)["head_sha"] == "first"


def test_curate_ignores_malformed_identifiers() -> None:
    raw = {
        "id": "s",
        "event_identifiers": [
            "no-separator",
            "x:{not json",
            "y:[1]",
            5,
            'z:{"review_pass": 1}',
        ],
    }
    curated = curate_session_metadata(raw)
    assert curated["review_pass"] == 1
    assert "head_sha" not in curated
