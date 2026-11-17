import email.message
import traceback
import urllib.error

import pytest

from prinfo import __version__
from prinfo.copilot import CopilotApiClient, CopilotApiError, copilot_api_base_url

SENTINEL = "ghu_SENTINEL_TOKEN_123"
BASE = "https://api.githubcopilot.com"


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class FakeOpener:
    def __init__(self, *bodies: bytes | Exception) -> None:
        self.bodies = list(bodies)
        self.requests: list[dict[str, object]] = []

    def __call__(self, request, timeout=None):
        self.requests.append(
            {
                "url": request.full_url,
                "headers": {k.lower(): v for k, v in request.header_items()},
                "timeout": timeout,
            }
        )
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return FakeResponse(body)


def make_client(opener: FakeOpener, provider=None) -> CopilotApiClient:
    return CopilotApiClient(
        base_url=BASE,
        token_provider=provider or (lambda: SENTINEL),
        opener=opener,
    )


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        f"{BASE}/x", code, "msg", hdrs=email.message.Message(), fp=None
    )


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("github.com", "https://api.githubcopilot.com"),
        ("example.ghe.com", "https://copilot-api.example.ghe.com"),
        ("EXAMPLE.ghe.com", "https://copilot-api.example.ghe.com"),
        ("github.example.com", None),
        ("evil.ghe.com.attacker.com", None),
    ],
)
def test_copilot_api_base_url(host: str, expected: str | None) -> None:
    assert copilot_api_base_url(host) == expected


def test_list_pr_sessions_builds_request_and_returns_entries() -> None:
    opener = FakeOpener(b'{"sessions": [{"id": "a"}, "junk", {"id": "b"}]}')
    client = make_client(opener)

    sessions = client.list_pr_sessions(42)

    assert sessions == [{"id": "a"}, {"id": "b"}]
    request = opener.requests[0]
    assert request["url"] == f"{BASE}/agents/sessions/resource/pull/42"
    assert request["headers"]["authorization"] == f"Bearer {SENTINEL}"
    assert request["headers"]["user-agent"] == f"prinfo/{__version__}"
    assert request["headers"]["accept"] == "application/json"
    assert request["timeout"] == 60.0


def test_list_pr_sessions_missing_sessions_returns_empty() -> None:
    assert make_client(FakeOpener(b"{}")).list_pr_sessions(1) == []


def test_get_session_quotes_session_id() -> None:
    opener = FakeOpener(b'{"id": "a/b"}')

    assert make_client(opener).get_session("a/b") == {"id": "a/b"}
    assert opener.requests[0]["url"] == f"{BASE}/agents/sessions/a%2Fb"


def test_get_session_log_returns_bytes_unchanged() -> None:
    raw = b"data: {\"x\": 1}\n\n\xff\x00data: end\r\n"
    opener = FakeOpener(raw)

    assert make_client(opener).get_session_log("abc") == raw
    assert opener.requests[0]["url"] == f"{BASE}/agents/sessions/abc/logs"
    assert opener.requests[0]["headers"]["accept"] == "text/event-stream"


@pytest.mark.parametrize("code", [401, 403, 404, 500])
def test_http_errors_map_to_status(code: int) -> None:
    client = make_client(FakeOpener(http_error(code)))

    with pytest.raises(CopilotApiError) as excinfo:
        client.get_session("abc")

    assert excinfo.value.status == code
    assert excinfo.value.method == "GET"
    assert excinfo.value.path == "/agents/sessions/abc"
    assert str(excinfo.value) == f"Copilot API GET /agents/sessions/abc failed with HTTP {code}"


def test_url_error_maps_to_no_status() -> None:
    client = make_client(FakeOpener(urllib.error.URLError(TimeoutError("slow"))))

    with pytest.raises(CopilotApiError) as excinfo:
        client.get_session("abc")

    assert excinfo.value.status is None
    assert "TimeoutError" in str(excinfo.value)


def test_os_error_maps_to_no_status() -> None:
    client = make_client(FakeOpener(ConnectionResetError("reset")))

    with pytest.raises(CopilotApiError) as excinfo:
        client.get_session("abc")

    assert excinfo.value.status is None


def test_token_never_leaks_into_errors_or_repr() -> None:
    client = make_client(FakeOpener(http_error(401)))

    with pytest.raises(CopilotApiError) as excinfo:
        client.get_session("abc")

    error = excinfo.value
    assert SENTINEL not in str(error)
    assert SENTINEL not in repr(error)
    assert SENTINEL not in repr(client)
    assert SENTINEL not in "".join(traceback.format_exception(error))


def test_token_provider_called_once_across_requests() -> None:
    calls: list[int] = []

    def provider() -> str:
        calls.append(1)
        return SENTINEL

    client = make_client(FakeOpener(b'{"sessions": []}'), provider)
    client.list_pr_sessions(1)
    client.list_pr_sessions(2)
    client.list_pr_sessions(3)

    assert len(calls) == 1


def test_invalid_json_raises_copilot_error() -> None:
    client = make_client(FakeOpener(b"not json"))

    with pytest.raises(CopilotApiError, match="invalid JSON") as excinfo:
        client.get_session("abc")

    assert excinfo.value.status is None


def test_wrong_json_type_raises_copilot_error() -> None:
    client = make_client(FakeOpener(b"[1, 2]"))

    with pytest.raises(CopilotApiError, match="invalid JSON"):
        client.get_session("abc")
