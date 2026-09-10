from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence
from urllib.parse import quote

JOB_URL_RE = re.compile(
    r"^https://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/runs/(?P<run_id>\d+)(?:/job/(?P<job_id>\d+))?"
)
LOGGER = logging.getLogger(__name__)

REVIEW_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 100) { nodes { databaseId } }
        }
      }
    }
  }
}
"""


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
class PrCommit:
    sha: str
    short_sha: str
    message_headline: str
    message: str
    authored_date: str | None
    committed_date: str | None
    url: str | None


@dataclass(frozen=True)
class IssueComment:
    comment_id: int
    author: str | None
    author_type: str | None
    body: str | None
    created_at: str | None
    updated_at: str | None
    url: str | None


@dataclass(frozen=True)
class ReviewComment:
    comment_id: int
    author: str | None
    author_type: str | None
    body: str | None
    created_at: str | None
    updated_at: str | None
    url: str | None
    path: str | None
    line: int | None
    original_line: int | None
    side: str | None
    commit_id: str | None
    in_reply_to_id: int | None
    diff_hunk: str | None
    pull_request_review_id: int | None
    is_resolved: bool | None = None
    thread_id: str | None = None


@dataclass(frozen=True)
class PullRequestReview:
    review_id: int
    author: str | None
    author_type: str | None
    body: str | None
    state: str | None
    submitted_at: str | None
    url: str | None
    commit_id: str | None


@dataclass(frozen=True)
class ReviewThread:
    thread_id: str
    is_resolved: bool | None
    is_outdated: bool | None
    comment_ids: list[int]


@dataclass(frozen=True)
class CommitFile:
    path: str
    status: str
    additions: int
    deletions: int
    changes: int
    previous_path: str | None


@dataclass(frozen=True)
class CommitDetails:
    commit: PrCommit
    files: list[CommitFile]


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
        runner: Callable[..., subprocess.CompletedProcess[object]] | None = None,
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

    def list_pr_commits(self, repo: str, pr_number: int) -> list[PrCommit]:
        repo_ref = parse_repo_ref(repo, self.gh_host)
        endpoint = f"repos/{repo_ref.owner}/{repo_ref.name}/pulls/{pr_number}/commits"
        commit_pages = self._run_paginated_json(host=repo_ref.host, endpoint=endpoint)

        commits: list[PrCommit] = []
        for raw_commit in commit_pages:
            commits.append(_parse_pr_commit(raw_commit))
        return commits

    def list_pr_issue_comments(self, repo: str, pr_number: int) -> list[IssueComment]:
        repo_ref = parse_repo_ref(repo, self.gh_host)
        endpoint = f"repos/{repo_ref.owner}/{repo_ref.name}/issues/{pr_number}/comments"
        comment_pages = self._run_paginated_json(host=repo_ref.host, endpoint=endpoint)

        comments: list[IssueComment] = []
        for raw_comment in comment_pages:
            comments.append(_parse_issue_comment(raw_comment, endpoint=endpoint))
        return comments

    def list_pr_review_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        repo_ref = parse_repo_ref(repo, self.gh_host)
        endpoint = f"repos/{repo_ref.owner}/{repo_ref.name}/pulls/{pr_number}/comments"
        comment_pages = self._run_paginated_json(host=repo_ref.host, endpoint=endpoint)

        comments: list[ReviewComment] = []
        for raw_comment in comment_pages:
            comments.append(_parse_review_comment(raw_comment, endpoint=endpoint))
        return comments

    def list_pr_reviews(self, repo: str, pr_number: int) -> list[PullRequestReview]:
        repo_ref = parse_repo_ref(repo, self.gh_host)
        endpoint = f"repos/{repo_ref.owner}/{repo_ref.name}/pulls/{pr_number}/reviews"
        review_pages = self._run_paginated_json(host=repo_ref.host, endpoint=endpoint)

        reviews: list[PullRequestReview] = []
        for raw_review in review_pages:
            reviews.append(_parse_review(raw_review, endpoint=endpoint))
        return reviews

    def list_pr_review_threads(self, repo: str, pr_number: int) -> list[ReviewThread]:
        repo_ref = parse_repo_ref(repo, self.gh_host)
        documents = self._run_graphql_paginated(
            host=repo_ref.host,
            query=REVIEW_THREADS_QUERY,
            variables={
                "owner": repo_ref.owner,
                "name": repo_ref.name,
                "number": pr_number,
            },
        )

        threads: list[ReviewThread] = []
        for document in documents:
            nodes = _extract_review_thread_nodes(document)
            for raw_node in nodes:
                threads.append(_parse_review_thread(raw_node))
        return threads

    def get_commit_details(self, repo: RepoRef, sha: str) -> CommitDetails:
        endpoint = f"repos/{repo.owner}/{repo.name}/commits/{sha}"
        detail_pages = self._run_paginated_json(host=repo.host, endpoint=endpoint)
        if not detail_pages:
            raise GhCliError(f"No commit details were returned for {repo.full_name}@{sha}.")

        commit = _parse_pr_commit(detail_pages[0])
        files: list[CommitFile] = []
        for raw_page in detail_pages:
            for raw_file in raw_page.get("files") or []:
                files.append(
                    CommitFile(
                        path=str(raw_file.get("filename") or ""),
                        status=str(raw_file.get("status") or "unknown"),
                        additions=int(raw_file.get("additions") or 0),
                        deletions=int(raw_file.get("deletions") or 0),
                        changes=int(raw_file.get("changes") or 0),
                        previous_path=raw_file.get("previous_filename"),
                    )
                )

        return CommitDetails(commit=commit, files=files)

    def download_job_log(self, repo: RepoRef, job_id: int) -> str:
        command = [
            "api",
            "--hostname",
            repo.host,
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repo.owner}/{repo.name}/actions/jobs/{job_id}/logs",
        ]
        return self._run_text(command)

    def download_commit_file(self, repo: RepoRef, file_path: str, ref: str) -> bytes:
        encoded_path = quote(file_path, safe="/")
        encoded_ref = quote(ref, safe="")
        command = [
            "api",
            "--hostname",
            repo.host,
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{repo.owner}/{repo.name}/contents/{encoded_path}?ref={encoded_ref}",
        ]
        return self._run_bytes(command)

    def _run_paginated_json(self, *, host: str, endpoint: str) -> list[dict[str, object]]:
        data = self._run_json_value(
            [
                "api",
                "--hostname",
                host,
                "--paginate",
                "--slurp",
                "-H",
                "Accept: application/vnd.github+json",
                endpoint,
            ]
        )
        if not isinstance(data, list):
            raise GhCliError(
                f"Expected paginated JSON array from gh for endpoint {endpoint!r}, got {type(data).__name__}."
            )

        items: list[dict[str, object]] = []
        for page in data:
            if isinstance(page, dict):
                items.append(page)
                continue
            if not isinstance(page, list):
                raise GhCliError(
                    f"Expected gh page data to be an object or array for endpoint {endpoint!r}, "
                    f"got {type(page).__name__}."
                )
            for entry in page:
                if not isinstance(entry, dict):
                    raise GhCliError(
                        f"Expected gh page entry to be an object for endpoint {endpoint!r}, "
                        f"got {type(entry).__name__}."
                    )
                items.append(entry)
        return items

    def _run_graphql_paginated(
        self, *, host: str, query: str, variables: dict[str, object]
    ) -> list[dict[str, object]]:
        command = ["api", "graphql", "--hostname", host, "--paginate", "-f", f"query={query}"]
        for key in sorted(variables):
            command.extend(["-F", f"{key}={variables[key]}"])

        output = self._run_text(command)
        stripped_output = output.strip()
        if not stripped_output:
            return []

        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return _decode_graphql_documents(stripped_output)

        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            documents: list[dict[str, object]] = []
            for entry in parsed:
                if not isinstance(entry, dict):
                    raise GhCliError(
                        f"Expected a GraphQL document object, got {type(entry).__name__}."
                    )
                documents.append(entry)
            return documents

        raise GhCliError(f"Expected a GraphQL document object, got {type(parsed).__name__}.")

    def _run_json(self, args: Sequence[str]) -> dict[str, object]:
        data = self._run_json_value(args)
        if not isinstance(data, dict):
            raise GhCliError(
                f"Failed to parse JSON object from gh output. Received {type(data).__name__} instead."
            )
        return data

    def _run_json_value(self, args: Sequence[str]) -> object:
        output = self._run_text(args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise GhCliError(f"Failed to parse JSON from gh output: {exc}") from exc

    def _run_bytes(self, args: Sequence[str]) -> bytes:
        completed, command = self._run_command(args)
        return _coerce_subprocess_bytes(value=completed.stdout, command=command)

    def _run_text(self, args: Sequence[str]) -> str:
        completed, command = self._run_command(args)
        return _decode_subprocess_text(
            value=completed.stdout,
            stream_name="stdout",
            command=command,
        )

    def _run_command(
        self, args: Sequence[str]
    ) -> tuple[subprocess.CompletedProcess[object], list[str]]:
        command = ["gh", *args]
        env = os.environ.copy()
        env.update(self.env_overrides)

        completed = self.runner(
            command,
            env=env,
            check=False,
            capture_output=True,
            text=False,
        )
        stderr = _decode_subprocess_text(
            value=completed.stderr,
            stream_name="stderr",
            command=command,
        )
        if completed.returncode != 0:
            raise GhCliError(stderr or f"`{' '.join(command)}` failed with exit code {completed.returncode}.")
        return completed, command


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


def _parse_pr_commit(raw_commit: dict[str, object]) -> PrCommit:
    sha = str(raw_commit.get("sha") or "")
    if not sha:
        raise GhCliError("GitHub did not return a commit SHA for a PR commit.")

    commit_data = raw_commit.get("commit") or {}
    if not isinstance(commit_data, dict):
        raise GhCliError(f"Unexpected commit payload for {sha}: {type(commit_data).__name__}.")

    message = str(commit_data.get("message") or "")
    message_headline = message.splitlines()[0] if message else sha[:7]

    author_data = commit_data.get("author") or {}
    if not isinstance(author_data, dict):
        author_data = {}
    committer_data = commit_data.get("committer") or {}
    if not isinstance(committer_data, dict):
        committer_data = {}

    return PrCommit(
        sha=sha,
        short_sha=sha[:7],
        message_headline=message_headline,
        message=message,
        authored_date=author_data.get("date"),
        committed_date=committer_data.get("date"),
        url=raw_commit.get("html_url"),
    )


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _author_fields(raw: dict[str, object]) -> tuple[str | None, str | None]:
    user_data = raw.get("user")
    if not isinstance(user_data, dict):
        return None, None
    return _optional_str(user_data.get("login")), _optional_str(user_data.get("type"))


def _require_id(raw: dict[str, object], *, endpoint: str) -> int:
    comment_id = _optional_int(raw.get("id"))
    if comment_id is None:
        raise GhCliError(f"GitHub did not return an id for an entry from endpoint {endpoint!r}.")
    return comment_id


def _parse_issue_comment(raw: object, *, endpoint: str) -> IssueComment:
    if not isinstance(raw, dict):
        raise GhCliError(f"Expected an object entry for endpoint {endpoint!r}, got {type(raw).__name__}.")

    author, author_type = _author_fields(raw)
    return IssueComment(
        comment_id=_require_id(raw, endpoint=endpoint),
        author=author,
        author_type=author_type,
        body=_optional_str(raw.get("body")),
        created_at=_optional_str(raw.get("created_at")),
        updated_at=_optional_str(raw.get("updated_at")),
        url=_optional_str(raw.get("html_url")),
    )


def _parse_review_comment(raw: object, *, endpoint: str) -> ReviewComment:
    if not isinstance(raw, dict):
        raise GhCliError(f"Expected an object entry for endpoint {endpoint!r}, got {type(raw).__name__}.")

    author, author_type = _author_fields(raw)
    return ReviewComment(
        comment_id=_require_id(raw, endpoint=endpoint),
        author=author,
        author_type=author_type,
        body=_optional_str(raw.get("body")),
        created_at=_optional_str(raw.get("created_at")),
        updated_at=_optional_str(raw.get("updated_at")),
        url=_optional_str(raw.get("html_url")),
        path=_optional_str(raw.get("path")),
        line=_optional_int(raw.get("line")),
        original_line=_optional_int(raw.get("original_line")),
        side=_optional_str(raw.get("side")),
        commit_id=_optional_str(raw.get("commit_id")),
        in_reply_to_id=_optional_int(raw.get("in_reply_to_id")),
        diff_hunk=_optional_str(raw.get("diff_hunk")),
        pull_request_review_id=_optional_int(raw.get("pull_request_review_id")),
    )


def _parse_review(raw: object, *, endpoint: str) -> PullRequestReview:
    if not isinstance(raw, dict):
        raise GhCliError(f"Expected an object entry for endpoint {endpoint!r}, got {type(raw).__name__}.")

    author, author_type = _author_fields(raw)
    return PullRequestReview(
        review_id=_require_id(raw, endpoint=endpoint),
        author=author,
        author_type=author_type,
        body=_optional_str(raw.get("body")),
        state=_optional_str(raw.get("state")),
        submitted_at=_optional_str(raw.get("submitted_at")),
        url=_optional_str(raw.get("html_url")),
        commit_id=_optional_str(raw.get("commit_id")),
    )


def _decode_graphql_documents(stripped_output: str) -> list[dict[str, object]]:
    decoder = json.JSONDecoder()
    documents: list[dict[str, object]] = []
    position = 0
    length = len(stripped_output)

    while position < length:
        while position < length and stripped_output[position].isspace():
            position += 1
        if position >= length:
            break
        try:
            document, end_position = decoder.raw_decode(stripped_output, position)
        except json.JSONDecodeError as exc:
            raise GhCliError(f"Failed to parse GraphQL response from gh: {exc}") from exc
        if not isinstance(document, dict):
            raise GhCliError(f"Expected a GraphQL document object, got {type(document).__name__}.")
        documents.append(document)
        position = end_position

    return documents


def _extract_review_thread_nodes(document: dict[str, object]) -> list[object]:
    data = document.get("data")
    if not isinstance(data, dict):
        return []
    repository = data.get("repository")
    if not isinstance(repository, dict):
        return []
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        return []
    review_threads = pull_request.get("reviewThreads")
    if not isinstance(review_threads, dict):
        return []
    nodes = review_threads.get("nodes")
    if not isinstance(nodes, list):
        return []
    return nodes


def _parse_review_thread(raw: object) -> ReviewThread:
    if not isinstance(raw, dict):
        raise GhCliError(f"Expected a GraphQL review thread object, got {type(raw).__name__}.")

    thread_id = raw.get("id")
    if thread_id is None:
        raise GhCliError("GitHub GraphQL did not return an id for a review thread.")

    is_resolved = raw.get("isResolved")
    is_outdated = raw.get("isOutdated")

    comment_ids: list[int] = []
    comments_data = raw.get("comments")
    if isinstance(comments_data, dict):
        comment_nodes = comments_data.get("nodes")
        if isinstance(comment_nodes, list):
            for comment_node in comment_nodes:
                if not isinstance(comment_node, dict):
                    continue
                database_id = _optional_int(comment_node.get("databaseId"))
                if database_id is not None:
                    comment_ids.append(database_id)

    return ReviewThread(
        thread_id=str(thread_id),
        is_resolved=is_resolved if isinstance(is_resolved, bool) else None,
        is_outdated=is_outdated if isinstance(is_outdated, bool) else None,
        comment_ids=comment_ids,
    )


def _decode_subprocess_text(*, value: object, stream_name: str, command: Sequence[str]) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.removeprefix("\ufeff")
    if not isinstance(value, bytes):
        raise GhCliError(
            f"Unexpected gh {stream_name} type {type(value).__name__!r} for `{' '.join(command)}`."
        )

    try:
        return value.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    for fallback_encoding in ("cp1252", "latin-1"):
        try:
            decoded_value = value.decode(fallback_encoding)
        except UnicodeDecodeError:
            continue
        LOGGER.debug(
            "Decoded gh %s with fallback encoding %s for command `%s`.",
            stream_name,
            fallback_encoding,
            " ".join(command),
        )
        return decoded_value

    raise GhCliError(
        f"Failed to decode gh {stream_name} for `{' '.join(command)}`. "
        "Tried UTF-8 and fallback single-byte decoders."
    )


def _coerce_subprocess_bytes(*, value: object, command: Sequence[str]) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise GhCliError(
        f"Unexpected gh stdout type {type(value).__name__!r} for `{' '.join(command)}`."
    )
