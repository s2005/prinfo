from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable
from urllib.parse import quote

from prinfo import __version__

GHE_CLOUD_HOST_RE = re.compile(r"^[a-z0-9-]+\.ghe\.com$")


def copilot_api_base_url(gh_host: str) -> str | None:
    """Return the Copilot API base URL for a GitHub host, or None when unsupported."""
    host = gh_host.strip().lower()
    if host == "github.com":
        return "https://api.githubcopilot.com"
    if GHE_CLOUD_HOST_RE.match(host):
        return f"https://copilot-api.{host}"
    return None


class CopilotApiError(RuntimeError):
    """Raised when a Copilot API call fails.

    The message holds only the method, path and status; never headers, token or body.
    """

    def __init__(self, *, method: str, path: str, status: int | None, reason: str | None = None) -> None:
        if status is not None:
            message = f"Copilot API {method} {path} failed with HTTP {status}"
        else:
            message = f"Copilot API {method} {path} failed: {reason or 'unknown error'}"
        super().__init__(message)
        self.status = status
        self.method = method
        self.path = path


class CopilotApiClient:
    """Minimal client for the undocumented Copilot agent-sessions API."""

    def __init__(
        self,
        *,
        base_url: str,
        token_provider: Callable[[], str],
        opener: Callable | None = None,
        user_agent: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._token: str | None = None
        self._opener = opener or urllib.request.urlopen
        self._user_agent = user_agent or f"prinfo/{__version__}"
        self._timeout = timeout

    def __repr__(self) -> str:
        return f"CopilotApiClient(base_url={self.base_url!r})"

    def list_pr_sessions(self, pr_database_id: int) -> list[dict]:
        """Return the agent sessions linked to a pull request database id."""
        path = f"/agents/sessions/resource/pull/{pr_database_id}"
        data = self._get_json(path)
        if not isinstance(data, dict):
            raise CopilotApiError(
                method="GET", path=path, status=None, reason="returned invalid JSON (expected object)"
            )
        sessions = data.get("sessions")
        if not isinstance(sessions, list):
            return []
        return [entry for entry in sessions if isinstance(entry, dict)]

    def get_session(self, session_id: str) -> dict:
        """Return the metadata object of one agent session."""
        path = f"/agents/sessions/{quote(session_id, safe='')}"
        data = self._get_json(path)
        if not isinstance(data, dict):
            raise CopilotApiError(
                method="GET", path=path, status=None, reason="returned invalid JSON (expected object)"
            )
        return data

    def get_session_log(self, session_id: str) -> bytes:
        """Return the raw event-stream log of one agent session."""
        path = f"/agents/sessions/{quote(session_id, safe='')}/logs"
        return self._request(path, accept="text/event-stream")

    def _get_json(self, path: str) -> object:
        body = self._request(path, accept="application/json")
        try:
            return json.loads(body)
        except ValueError:
            raise CopilotApiError(
                method="GET", path=path, status=None, reason="returned invalid JSON"
            ) from None

    def _headers(self, accept: str) -> dict[str, str]:
        if self._token is None:
            self._token = self._token_provider()
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept,
            "User-Agent": self._user_agent,
        }

    def _request(self, path: str, *, accept: str) -> bytes:
        request = urllib.request.Request(
            f"{self.base_url}{path}", headers=self._headers(accept), method="GET"
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise CopilotApiError(method="GET", path=path, status=exc.code) from None
        except urllib.error.URLError as exc:
            reason = exc.reason
            reason_text = type(reason).__name__ if not isinstance(reason, str) else reason
            raise CopilotApiError(method="GET", path=path, status=None, reason=reason_text) from None
        except (OSError, TimeoutError) as exc:
            raise CopilotApiError(
                method="GET", path=path, status=None, reason=type(exc).__name__
            ) from None
