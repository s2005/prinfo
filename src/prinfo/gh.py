from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

JOB_URL_RE = re.compile(
    r"^https://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/runs/(?P<run_id>\d+)(?:/job/(?P<job_id>\d+))?"
)


class GhCliError(RuntimeError):
    """Raised when gh CLI interaction fails."""


@dataclass(frozen=True)
class CheckRun:
    name: str
    workflow_name: str | None
    status: str | None
    conclusion: str | None
    details_url: str | None
    check_type: str
    run_id: int | None
    job_id: int | None


@dataclass(frozen=True)
class RepoRef:
    host: str
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        if self.host == "github.com":
            return f"{self.owner}/{self.name}"
        return f"{self.host}/{self.owner}/{self.name}"


class GhCli:
    def __init__(
        self,
        *,
        gh_host: str = "github.com",
        gh_token: str | None = None,
        gh_config_dir: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.gh_host = gh_host
        self.runner = runner or subprocess.run
        self.env_overrides: dict[str, str] = {}
        if gh_token:
            self.env_overrides["GH_TOKEN"] = gh_token
        if gh_config_dir:
            self.env_overrides["GH_CONFIG_DIR"] = gh_config_dir
        if gh_host:
            self.env_overrides["GH_HOST"] = gh_host

    def ensure_available(self) -> None:
        if shutil.which("gh") is None:
            raise GhCliError("GitHub CLI `gh` is not installed or not available on PATH.")

    def detect_repo(self) -> str:
        data = self._run_json(["repo", "view", "--json", "nameWithOwner"])
        name_with_owner = data.get("nameWithOwner")
        if not name_with_owner:
            raise GhCliError("Could not resolve repository from the current directory. Use --repo.")
        return str(name_with_owner)

    def list_pr_checks(self, repo: str, pr_number: int) -> list[CheckRun]:
        data = self._run_json(
            ["pr", "view", str(pr_number), "--repo", repo, "--json", "statusCheckRollup"]
        )
        status_checks = data.get("statusCheckRollup") or []
        checks: list[CheckRun] = []

        for raw_check in status_checks:
            check_type = raw_check.get("__typename", "Unknown")
            details_url = raw_check.get("detailsUrl") or raw_check.get("targetUrl")
            job_match = parse_actions_job_url(details_url)
            checks.append(
                CheckRun(
                    name=str(raw_check.get("name") or raw_check.get("context") or "unnamed-check"),
                    workflow_name=raw_check.get("workflowName"),
                    status=raw_check.get("status"),
                    conclusion=raw_check.get("conclusion"),
                    details_url=details_url,
                    check_type=check_type,
                    run_id=job_match.run_id if job_match else None,
                    job_id=job_match.job_id if job_match else None,
                )
            )

        return checks

    def download_job_log(self, repo: RepoRef, job_id: int) -> str:
        command = [
            "api",
            "--hostname",
            repo.host,
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repo.owner}/{repo.name}/actions/jobs/{job_id}/logs",
        ]
        return self._run_text(command).lstrip("\ufeff")

    def _run_json(self, args: Sequence[str]) -> dict:
        output = self._run_text(args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise GhCliError(f"Failed to parse JSON from gh output: {exc}") from exc

    def _run_text(self, args: Sequence[str]) -> str:
        command = ["gh", *args]
        env = os.environ.copy()
        env.update(self.env_overrides)

        completed = self.runner(
            command,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise GhCliError(stderr or f"`{' '.join(command)}` failed with exit code {completed.returncode}.")
        return completed.stdout


@dataclass(frozen=True)
class ActionsJobRef:
    host: str
    owner: str
    repo: str
    run_id: int
    job_id: int | None


def parse_repo_ref(repo: str, default_host: str) -> RepoRef:
    parts = repo.split("/")
    if len(parts) == 2:
        return RepoRef(host=default_host, owner=parts[0], name=parts[1])
    if len(parts) == 3:
        return RepoRef(host=parts[0], owner=parts[1], name=parts[2])
    raise GhCliError(f"Repository must look like OWNER/REPO or HOST/OWNER/REPO, got: {repo}")


def parse_actions_job_url(url: str | None) -> ActionsJobRef | None:
    if not url:
        return None
    match = JOB_URL_RE.match(url)
    if not match:
        return None

    return ActionsJobRef(
        host=match.group("host"),
        owner=match.group("owner"),
        repo=match.group("repo"),
        run_id=int(match.group("run_id")),
        job_id=int(match.group("job_id")) if match.group("job_id") else None,
    )
