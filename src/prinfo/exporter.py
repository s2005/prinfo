from __future__ import annotations

import dataclasses
import json
import logging
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from prinfo.config import AppConfig
from prinfo.gh import (
    CheckRun,
    CommitDetails,
    CommitFile,
    GhCli,
    GhCliError,
    IssueComment,
    PrCommit,
    PullRequestReview,
    ReviewComment,
    ReviewThread,
    parse_repo_ref,
)

LOGGER = logging.getLogger(__name__)
FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ExportError(RuntimeError):
    """Raised when PR export cannot complete."""


@dataclass(frozen=True)
class ExportResult:
    repo: str
    pr_number: int
    output_dir: Path
    manifest_path: Path
    exported_logs: int
    manifest_only_logs: int
    skipped_checks: int
    skipped_check_reasons: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CommitExportResult:
    repo: str
    pr_number: int
    output_dir: Path
    manifest_path: Path
    commit_count: int
    exported_files: int
    skipped_files: int
    skipped_file_reasons: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CommitLogExportResult:
    repo: str
    pr_number: int
    output_dir: Path
    manifest_path: Path
    commit_count: int


class PrCommitCache:
    """Holds the PR commit list so both commit export modes share one fetch."""

    def __init__(self) -> None:
        self._commits: list[PrCommit] | None = None

    def get(self, *, gh: GhCli, repo: str, pr_number: int) -> list[PrCommit]:
        if self._commits is None:
            self._commits = gh.list_pr_commits(repo, pr_number)
        return self._commits


def _fetch_pr_commits(
    *, gh: GhCli, repo: str, pr_number: int, cache: PrCommitCache | None
) -> list[PrCommit]:
    if cache is None:
        return gh.list_pr_commits(repo, pr_number)
    return cache.get(gh=gh, repo=repo, pr_number=pr_number)


@dataclass(frozen=True)
class CommentExportResult:
    repo: str
    pr_number: int
    output_dir: Path
    manifest_path: Path
    transcript_path: Path
    issue_comment_count: int
    review_comment_count: int
    review_count: int
    review_thread_count: int
    skipped_sources: int


def export_pr_check_logs(config: AppConfig, gh: GhCli) -> ExportResult:
    gh.ensure_available()

    repo_name = config.repo or gh.detect_repo()
    repo_ref = parse_repo_ref(repo_name, config.gh_host)
    checks = gh.list_pr_checks(repo_ref.full_name, config.pr_number)
    if not checks:
        raise ExportError(f"No checks were found for PR #{config.pr_number} in {repo_ref.full_name}.")

    config.output_dir.mkdir(parents=True, exist_ok=True)

    exported: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    skipped_check_reasons: Counter[str] = Counter()
    saved_logs = 0
    manifest_only_logs = 0

    for index, check in enumerate(checks, start=1):
        if check.job_id is None:
            LOGGER.info("Skipping check without downloadable job log: %s", check.name)
            skipped.append(
                _skipped_record(
                    check=check,
                    reason="check is not a GitHub Actions job",
                    reason_code="unsupported_check_type",
                )
            )
            skipped_check_reasons["unsupported_check_type"] += 1
            continue

        LOGGER.info("Downloading log for check '%s' (job %s)", check.name, check.job_id)
        try:
            log_text = gh.download_job_log(repo_ref, check.job_id)
        except GhCliError as exc:
            if not _is_missing_log_error(exc):
                raise
            LOGGER.warning(
                "Skipping check '%s' (job %s) because no downloadable log content is available.",
                check.name,
                check.job_id,
            )
            skipped.append(
                _skipped_record(
                    check=check,
                    reason=str(exc),
                    reason_code="missing_log_content",
                )
            )
            skipped_check_reasons["missing_log_content"] += 1
            continue

        has_log_content = log_text != ""
        empty_log_reason = _empty_log_reason(check=check) if not has_log_content else None
        log_path: str | None = None
        log_size_bytes = 0
        save_log_file = has_log_content or not config.skip_empty_logs

        if save_log_file:
            log_file = config.output_dir / build_log_filename(index, check)
            log_file.write_text(log_text, encoding="utf-8")
            log_path = str(log_file.name)
            log_size_bytes = log_file.stat().st_size
            saved_logs += 1
            if not has_log_content:
                LOGGER.info(
                    "Check '%s' produced no log content; wrote a zero-byte file and recorded the reason in the manifest.",
                    check.name,
                )
        else:
            manifest_only_logs += 1
            LOGGER.info(
                "Check '%s' produced no log content; recorded it in the manifest without writing a file.",
                check.name,
            )

        exported.append(
            _exported_record(
                check=check,
                path=log_path,
                bytes_written=log_size_bytes,
                has_log_content=has_log_content,
                empty_log_reason=empty_log_reason,
                saved=save_log_file,
            )
        )

    if not exported:
        raise ExportError(
            f"PR #{config.pr_number} in {repo_ref.full_name} has checks, but none exposed downloadable job logs."
        )

    manifest_path = config.output_dir / "manifest.json"
    manifest = {
        "repo": repo_ref.full_name,
        "pr_number": config.pr_number,
        "exported": exported,
        "skipped": skipped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return ExportResult(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        output_dir=config.output_dir,
        manifest_path=manifest_path,
        exported_logs=saved_logs,
        manifest_only_logs=manifest_only_logs,
        skipped_checks=len(skipped),
        skipped_check_reasons=dict(skipped_check_reasons),
    )


def export_pr_comments(config: AppConfig, gh: GhCli) -> CommentExportResult:
    gh.ensure_available()

    repo_name = config.repo or gh.detect_repo()
    repo_ref = parse_repo_ref(repo_name, config.gh_host)

    skipped_sources: list[dict[str, object]] = []

    issue_comments: list[IssueComment] = []
    try:
        issue_comments = gh.list_pr_issue_comments(repo_ref.full_name, config.pr_number)
    except GhCliError as exc:
        LOGGER.warning("Skipping issue comments for PR #%s: %s", config.pr_number, exc)
        skipped_sources.append(
            _skipped_source_record(source="issue_comments", reason=str(exc), reason_code="source_unavailable")
        )

    review_comments: list[ReviewComment] = []
    try:
        review_comments = gh.list_pr_review_comments(repo_ref.full_name, config.pr_number)
    except GhCliError as exc:
        LOGGER.warning("Skipping review comments for PR #%s: %s", config.pr_number, exc)
        skipped_sources.append(
            _skipped_source_record(source="review_comments", reason=str(exc), reason_code="source_unavailable")
        )

    reviews: list[PullRequestReview] = []
    try:
        reviews = gh.list_pr_reviews(repo_ref.full_name, config.pr_number)
    except GhCliError as exc:
        LOGGER.warning("Skipping reviews for PR #%s: %s", config.pr_number, exc)
        skipped_sources.append(
            _skipped_source_record(source="reviews", reason=str(exc), reason_code="source_unavailable")
        )

    review_threads: list[ReviewThread] = []
    try:
        review_threads = gh.list_pr_review_threads(repo_ref.full_name, config.pr_number)
    except GhCliError as exc:
        LOGGER.warning("Skipping review threads for PR #%s: %s", config.pr_number, exc)
        skipped_sources.append(
            _skipped_source_record(source="review_threads", reason=str(exc), reason_code="source_unavailable")
        )

    if len(skipped_sources) == 4:
        raise ExportError(f"No comment data could be exported for PR #{config.pr_number} in {repo_ref.full_name}.")

    config.output_dir.mkdir(parents=True, exist_ok=True)

    threads_by_comment_id: dict[int, ReviewThread] = {}
    for thread in review_threads:
        for comment_id in thread.comment_ids:
            threads_by_comment_id[comment_id] = thread

    resolved_review_comments: list[ReviewComment] = []
    for comment in review_comments:
        thread = threads_by_comment_id.get(comment.comment_id)
        if thread is not None:
            resolved_review_comments.append(
                dataclasses.replace(comment, is_resolved=thread.is_resolved, thread_id=thread.thread_id)
            )
        else:
            resolved_review_comments.append(comment)
    review_comments = resolved_review_comments

    counts = {
        "issue_comments": len(issue_comments),
        "review_comments": len(review_comments),
        "reviews": len(reviews),
        "review_threads": len(review_threads),
    }

    comments_payload = {
        "repo": repo_ref.full_name,
        "pr_number": config.pr_number,
        "issue_comments": [asdict(comment) for comment in issue_comments],
        "review_comments": [asdict(comment) for comment in review_comments],
        "reviews": [asdict(review) for review in reviews],
        "review_threads": [asdict(thread) for thread in review_threads],
        "counts": counts,
        "skipped_sources": skipped_sources,
    }
    manifest_path = config.output_dir / "comments.json"
    manifest_path.write_text(json.dumps(comments_payload, indent=2), encoding="utf-8")

    transcript = _render_comments_markdown(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        issue_comments=issue_comments,
        review_comments=review_comments,
        reviews=reviews,
    )
    transcript_path = config.output_dir / "comments.md"
    transcript_path.write_text(transcript, encoding="utf-8")

    return CommentExportResult(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        output_dir=config.output_dir,
        manifest_path=manifest_path,
        transcript_path=transcript_path,
        issue_comment_count=len(issue_comments),
        review_comment_count=len(review_comments),
        review_count=len(reviews),
        review_thread_count=len(review_threads),
        skipped_sources=len(skipped_sources),
    )


def export_pr_commit_files(
    config: AppConfig, gh: GhCli, commits_cache: PrCommitCache | None = None
) -> CommitExportResult:
    gh.ensure_available()

    repo_name = config.repo or gh.detect_repo()
    repo_ref = parse_repo_ref(repo_name, config.gh_host)
    commits = _fetch_pr_commits(
        gh=gh, repo=repo_ref.full_name, pr_number=config.pr_number, cache=commits_cache
    )
    if not commits:
        raise ExportError(f"No commits were found for PR #{config.pr_number} in {repo_ref.full_name}.")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    commits_dir = config.output_dir / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)

    commit_records: list[dict[str, object]] = []
    exported_files = 0
    skipped_files = 0
    skipped_file_reasons: Counter[str] = Counter()

    for commit in commits:
        LOGGER.info("Exporting files for commit %s (%s)", commit.short_sha, commit.message_headline)
        details = gh.get_commit_details(repo_ref, commit.sha)
        commit_result = _export_commit_folder(
            output_dir=config.output_dir,
            commits_dir=commits_dir,
            details=details,
            gh=gh,
            repo_ref=repo_ref,
        )
        exported_files += commit_result.exported_files
        skipped_files += commit_result.skipped_files
        commit_records.append(commit_result.record)
        for entry in commit_result.skipped:
            skipped_file_reasons[str(entry["reason_code"])] += 1

    manifest_path = config.output_dir / "commits-manifest.json"
    manifest = {
        "repo": repo_ref.full_name,
        "pr_number": config.pr_number,
        "commit_count": len(commits),
        "exported_files": exported_files,
        "skipped_files": skipped_files,
        "commits": commit_records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return CommitExportResult(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        output_dir=config.output_dir,
        manifest_path=manifest_path,
        commit_count=len(commits),
        exported_files=exported_files,
        skipped_files=skipped_files,
        skipped_file_reasons=dict(skipped_file_reasons),
    )


def export_pr_commit_log(
    config: AppConfig, gh: GhCli, commits_cache: PrCommitCache | None = None
) -> CommitLogExportResult:
    gh.ensure_available()

    repo_name = config.repo or gh.detect_repo()
    repo_ref = parse_repo_ref(repo_name, config.gh_host)
    commits = _fetch_pr_commits(
        gh=gh, repo=repo_ref.full_name, pr_number=config.pr_number, cache=commits_cache
    )
    if not commits:
        raise ExportError(f"No commits were found for PR #{config.pr_number} in {repo_ref.full_name}.")

    config.output_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Writing commit log metadata for %d commits", len(commits))

    manifest_path = config.output_dir / "commit-log.json"
    manifest = {
        "repo": repo_ref.full_name,
        "pr_number": config.pr_number,
        "commit_count": len(commits),
        "commits": [asdict(commit) for commit in commits],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return CommitLogExportResult(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        output_dir=config.output_dir,
        manifest_path=manifest_path,
        commit_count=len(commits),
    )


def build_log_filename(index: int, check: CheckRun) -> str:
    workflow = slugify(check.workflow_name or "workflow")
    check_name = slugify(check.name)
    suffix = f"job-{check.job_id}" if check.job_id is not None else "no-job"
    return f"{index:02d}-{workflow}-{check_name}-{suffix}.log"


def slugify(value: str) -> str:
    sanitized = FILENAME_SANITIZE_RE.sub("-", value.strip()).strip("-")
    return sanitized.lower() or "check"


# Reason codes a caller should act on. "removed" and "missing_path" describe files
# that cannot exist at the requested revision and need no action; "download_failed"
# means gh errored while fetching a file that should have been retrievable.
ACTIONABLE_COMMIT_SKIP_REASONS = frozenset({"download_failed"})

# Reason codes a caller should act on. "unsupported_check_type" describes a check
# that is not a GitHub Actions job, so it never had a log to download and needs no
# action; "missing_log_content" means a real Actions job did not return the log it
# should have.
ACTIONABLE_CHECK_SKIP_REASONS = frozenset({"missing_log_content"})


@dataclass(frozen=True)
class _CommitFolderResult:
    exported_files: int
    skipped_files: int
    skipped: list[dict[str, object]]
    record: dict[str, object]


def _export_commit_folder(
    *,
    output_dir: Path,
    commits_dir: Path,
    details: CommitDetails,
    gh: GhCli,
    repo_ref,
) -> _CommitFolderResult:
    commit_dir = commits_dir / details.commit.sha
    commit_dir.mkdir(parents=True, exist_ok=True)

    exported: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for file in details.files:
        if not file.path:
            skipped.append(
                _skipped_commit_file_record(
                    file=file,
                    reason="file path missing from commit payload",
                    reason_code="missing_path",
                )
            )
            continue

        if file.status == "removed":
            LOGGER.info(
                "Skipping removed file '%s' for commit %s because it cannot be downloaded at that revision.",
                file.path,
                details.commit.short_sha,
            )
            skipped.append(
                _skipped_commit_file_record(
                    file=file,
                    reason="file was removed in this commit",
                    reason_code="removed",
                )
            )
            continue

        try:
            file_bytes = gh.download_commit_file(repo_ref, file.path, details.commit.sha)
        except GhCliError as exc:
            LOGGER.warning(
                "Skipping file '%s' for commit %s: %s",
                file.path,
                details.commit.short_sha,
                exc,
            )
            skipped.append(
                _skipped_commit_file_record(
                    file=file,
                    reason=str(exc),
                    reason_code="download_failed",
                )
            )
            continue

        target_path = commit_dir / _sanitize_repo_relative_path(file.path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_bytes)
        exported.append(
            _exported_commit_file_record(
                output_dir=output_dir,
                file=file,
                path=target_path,
                bytes_written=len(file_bytes),
            )
        )

    commit_manifest_path = commit_dir / "_commit.json"
    commit_manifest = {
        "commit": asdict(details.commit),
        "exported": exported,
        "skipped": skipped,
    }
    commit_manifest_path.write_text(json.dumps(commit_manifest, indent=2), encoding="utf-8")

    return _CommitFolderResult(
        exported_files=len(exported),
        skipped_files=len(skipped),
        skipped=skipped,
        record={
            "commit": asdict(details.commit),
            "folder": _relative_manifest_path(output_dir=output_dir, path=commit_dir),
            "manifest_path": _relative_manifest_path(output_dir=output_dir, path=commit_manifest_path),
            "exported_files": len(exported),
            "skipped_files": len(skipped),
            "skipped": skipped,
        },
    )


def _sanitize_repo_relative_path(repo_path: str) -> Path:
    raw_path = PurePosixPath(repo_path)
    safe_parts: list[str] = []
    for part in raw_path.parts:
        if part in {"", ".", "/"}:
            continue
        if part == "..":
            safe_parts.append("_parent")
            continue
        safe_parts.append(part)

    if not safe_parts:
        safe_parts.append("file")
    return Path(*safe_parts)


def _relative_manifest_path(*, output_dir: Path, path: Path) -> str:
    return path.relative_to(output_dir).as_posix()


def _exported_record(
    *,
    check: CheckRun,
    path: str | None,
    bytes_written: int,
    has_log_content: bool,
    empty_log_reason: str | None,
    saved: bool,
) -> dict[str, object]:
    return {
        "check": asdict(check),
        "path": path,
        "saved": saved,
        "bytes": bytes_written,
        "status": check.status,
        "conclusion": check.conclusion,
        "has_log_content": has_log_content,
        "empty_log_reason": empty_log_reason,
    }


def _skipped_record(*, check: CheckRun, reason: str, reason_code: str) -> dict[str, object]:
    return {
        "check": asdict(check),
        "status": check.status,
        "conclusion": check.conclusion,
        "has_log_content": False,
        "reason_code": reason_code,
        "reason": reason,
    }


def _skipped_source_record(*, source: str, reason: str, reason_code: str) -> dict[str, object]:
    return {
        "source": source,
        "reason_code": reason_code,
        "reason": reason,
    }


def _render_comments_markdown(
    *,
    repo: str,
    pr_number: int,
    issue_comments: list[IssueComment],
    review_comments: list[ReviewComment],
    reviews: list[PullRequestReview],
) -> str:
    entries: list[tuple[tuple[bool, str], str]] = []

    for comment in issue_comments:
        heading = _comment_heading(author=comment.author, kind="issue comment", timestamp=comment.created_at)
        body = _comment_body(comment.body)
        entries.append((_sort_key(comment.created_at), f"## {heading}\n\n{body}"))

    for comment in review_comments:
        kind = "review comment"
        if comment.path:
            line = comment.line if comment.line is not None else comment.original_line
            if line is not None:
                kind = f"{kind} on {comment.path}:{line}"
            else:
                kind = f"{kind} on {comment.path}"
        if comment.is_resolved is True:
            kind = f"{kind} (resolved)"
        elif comment.is_resolved is False:
            kind = f"{kind} (unresolved)"
        heading = _comment_heading(author=comment.author, kind=kind, timestamp=comment.created_at)
        body = _comment_body(comment.body)
        entries.append((_sort_key(comment.created_at), f"## {heading}\n\n{body}"))

    for review in reviews:
        kind = f"review ({review.state})" if review.state is not None else "review"
        heading = _comment_heading(author=review.author, kind=kind, timestamp=review.submitted_at)
        body = _comment_body(review.body)
        entries.append((_sort_key(review.submitted_at), f"## {heading}\n\n{body}"))

    entries.sort(key=lambda entry: entry[0])

    sections = [f"# Comments for {repo} PR #{pr_number}"]
    sections.extend(entry[1] for entry in entries)
    return "\n\n".join(sections) + "\n"


def _sort_key(timestamp: str | None) -> tuple[bool, str]:
    return (timestamp is None, timestamp or "")


def _comment_heading(*, author: str | None, kind: str, timestamp: str | None) -> str:
    author_text = author or "unknown author"
    timestamp_text = timestamp or "unknown time"
    return f"{author_text} - {kind} - {timestamp_text}"


def _comment_body(body: str | None) -> str:
    if body is None:
        return "(no body)"
    return body


def _exported_commit_file_record(
    *,
    output_dir: Path,
    file: CommitFile,
    path: Path,
    bytes_written: int,
) -> dict[str, object]:
    return {
        "path": _relative_manifest_path(output_dir=output_dir, path=path),
        "bytes": bytes_written,
        "status": file.status,
        "additions": file.additions,
        "deletions": file.deletions,
        "changes": file.changes,
        "previous_path": file.previous_path,
        "source_path": file.path,
    }


def _skipped_commit_file_record(
    *,
    file: CommitFile,
    reason: str,
    reason_code: str,
) -> dict[str, object]:
    return {
        "path": file.path,
        "status": file.status,
        "additions": file.additions,
        "deletions": file.deletions,
        "changes": file.changes,
        "previous_path": file.previous_path,
        "reason_code": reason_code,
        "reason": reason,
    }


def _is_missing_log_error(error: GhCliError) -> bool:
    message = str(error)
    return "HTTP 404" in message or "Not Found" in message


def _empty_log_reason(*, check: CheckRun) -> str:
    if (check.conclusion or "").lower() == "skipped":
        return "job concluded skipped and produced no log output"
    return "job log endpoint returned no content"
