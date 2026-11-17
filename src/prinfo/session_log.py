"""Pure parser for Copilot agent session logs (server-sent events).

The log is a stream of ``data: {json}`` lines, each shaped like an OpenAI
chat-completions chunk. This module turns it into transcript events and
review findings, renders a Markdown transcript, and curates session metadata.
It performs no I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

MAX_ARGUMENT_CHARS = 4000

_STORE_COMMENT = "store_comment"
_IDENTIFIER_KEYS = (
    "review_pass",
    "head_sha",
    "last_reviewed_head_revision",
    "review_effort_level",
)
_METADATA_KEYS = (
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
)
# Finding key -> store_comment argument key, in finding order.
_FINDING_KEYS = (
    ("type", "comment_type"),
    ("path", "file_location"),
    ("start_line", "start_line"),
    ("end_line", "end_line"),
    ("body", "comment_content"),
    ("suggested_fix", "suggested_fix"),
    ("fix_skip_reason", "fix_skip_reason"),
    ("fix_skip_note", "fix_skip_note"),
    ("fixed", "fixed"),
)


@dataclass(frozen=True)
class TranscriptEvent:
    """One transcript block: assistant text or a tool call."""

    kind: str
    text: str | None
    tool_name: str | None
    arguments: str | None


@dataclass(frozen=True)
class ParsedSessionLog:
    """Result of parsing a session log."""

    events: list[TranscriptEvent]
    findings: list[dict[str, Any]]
    unparsed_events: int


def _build_finding(arguments: dict[str, Any]) -> dict[str, Any]:
    """Map store_comment arguments to a finding, keeping unknown keys in extra."""
    finding: dict[str, Any] = {}
    consumed = set()
    for out_key, in_key in _FINDING_KEYS:
        finding[out_key] = arguments.get(in_key)
        consumed.add(in_key)
    finding["extra"] = {k: v for k, v in arguments.items() if k not in consumed}
    return finding


def parse_session_log(raw: bytes) -> ParsedSessionLog:
    """Parse raw SSE log bytes into events, findings and an unparsed count."""
    text = raw.decode("utf-8", errors="replace")
    events: list[TranscriptEvent] = []
    findings: list[dict[str, Any]] = []
    unparsed = 0
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            continue
        try:
            chunk = json.loads(payload)
        except ValueError:
            unparsed += 1
            continue
        if not isinstance(chunk, dict):
            unparsed += 1
            continue
        choices = chunk.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            if not isinstance(delta, dict):
                continue
            content = delta.get("content")
            if isinstance(content, str) and content:
                events.append(TranscriptEvent("assistant", content, None, None))
            tool_calls = delta.get("tool_calls")
            if not isinstance(tool_calls, list):
                continue
            for call in tool_calls:
                function = call.get("function") if isinstance(call, dict) else None
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                arguments = function.get("arguments")
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments)
                events.append(TranscriptEvent("tool_call", None, name, arguments))
                if name == _STORE_COMMENT:
                    try:
                        decoded = json.loads(arguments)
                    except ValueError:
                        decoded = None
                    if isinstance(decoded, dict):
                        findings.append(_build_finding(decoded))
                    else:
                        unparsed += 1
    return ParsedSessionLog(events=events, findings=findings, unparsed_events=unparsed)


def _fence_for(text: str) -> str:
    """Return a backtick fence longer than any backtick run in text (min 3)."""
    longest = 0
    run = 0
    for char in text:
        if char == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return "`" * max(3, longest + 1)


def render_transcript(parsed: ParsedSessionLog, *, session_id: str) -> str:
    """Render the parsed log as a Markdown transcript with numbered headings."""
    lines = [f"# Session {session_id}", ""]
    if not parsed.events:
        lines += ["(no events)", ""]
    for number, event in enumerate(parsed.events, start=1):
        if event.kind == "assistant":
            lines += [f"## {number}. Assistant", "", event.text or "", ""]
            continue
        lines += [f"## {number}. Tool call: {event.tool_name}", ""]
        arguments = event.arguments or ""
        shown = arguments[:MAX_ARGUMENT_CHARS]
        fence = _fence_for(shown)
        lines += [fence, shown, fence, ""]
        if len(arguments) > MAX_ARGUMENT_CHARS:
            lines += [
                f"(arguments truncated: showed {MAX_ARGUMENT_CHARS} of "
                f"{len(arguments)} characters)",
                "",
            ]
    if parsed.unparsed_events > 0:
        lines += [f"({parsed.unparsed_events} unparsed event(s) skipped)", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _identifier_entries(value: Any) -> list[str]:
    """Normalise event_identifiers into a list of strings."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return [value]
        if isinstance(decoded, list):
            return [item for item in decoded if isinstance(item, str)]
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def curate_session_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only allow-listed session metadata plus decoded identifier keys."""
    curated: dict[str, Any] = {key: raw.get(key) for key in _METADATA_KEYS}
    for entry in _identifier_entries(raw.get("event_identifiers")):
        _scheme, sep, rest = entry.partition(":")
        if not sep:
            continue
        try:
            decoded = json.loads(rest)
        except ValueError:
            continue
        if not isinstance(decoded, dict):
            continue
        for key in _IDENTIFIER_KEYS:
            if key in decoded and key not in curated:
                curated[key] = decoded[key]
    return curated
