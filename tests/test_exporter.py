import json
import re
from pathlib import Path

import pytest

from prinfo.config import AppConfig
from prinfo.exporter import (
    ExportError,
    PrCommitCache,
    build_log_filename,
    export_pr_check_logs,
    export_pr_comments,
    export_pr_commit_files,
    export_pr_commit_log,
)
from prinfo.gh import (
    CheckRun,
    CommitDetails,
    CommitFile,
    GhCliError,
    IssueComment,
    PrCommit,
    PullRequestReview,
    ReviewComment,
    ReviewThread,
)


class FakeGhCli:
    def __init__(
        self,
        *,
        repo: str | None = None,
        checks: list[CheckRun] | None = None,
        commits: list[PrCommit] | None = None,
        commit_details: dict[str, CommitDetails] | None = None,
        job_outputs: dict[int, str] | None = None,
        commit_file_outputs: dict[tuple[str, str], bytes] | None = None,
        failing_jobs: dict[int, str] | None = None,
        failing_commit_files: dict[tuple[str, str], str] | None = None,
        issue_comments: list[IssueComment] | None = None,
        review_comments: list[ReviewComment] | None = None,
        reviews: list[PullRequestReview] | None = None,
        review_threads: list[ReviewThread] | None = None,
        failing_comment_sources: dict[str, str] | None = None,
    ) -> None:
        self.repo = repo
        self.checks = checks or []
        self.commits = commits or []
        self.commit_details = commit_details or {}
        self.job_outputs = job_outputs or {}
        self.commit_file_outputs = commit_file_outputs or {}
        self.failing_jobs = failing_jobs or {}
        self.failing_commit_files = failing_commit_files or {}
        self.issue_comments = issue_comments or []
        self.review_comments = review_comments or []
        self.reviews = reviews or []
        self.review_threads = review_threads or []
        self.failing_comment_sources = failing_comment_sources or {}
        self.downloaded_jobs: list[int] = []
        self.downloaded_commit_files: list[tuple[str, str]] = []
        self.comment_calls: list[str] = []
        self.available_checked = False
        self.list_pr_commits_calls = 0

    def ensure_available(self) -> None:
        self.available_checked = True

    def detect_repo(self) -> str:
        if self.repo is None:
            raise AssertionError("detect_repo should not be called without repo fixture")
        return self.repo

    def list_pr_checks(self, repo: str, pr_number: int) -> list[CheckRun]:
        assert pr_number > 0
        return self.checks

    def list_pr_commits(self, repo: str, pr_number: int) -> list[PrCommit]:
        assert pr_number > 0
        self.list_pr_commits_calls += 1
        return self.commits

    def get_commit_details(self, repo, sha: str) -> CommitDetails:
        return self.commit_details[sha]

    def download_job_log(self, repo, job_id: int) -> str:
        self.downloaded_jobs.append(job_id)
        if job_id in self.failing_jobs:
            raise GhCliError(self.failing_jobs[job_id])
        if job_id in self.job_outputs:
            return self.job_outputs[job_id]
        return f"log-output-{job_id}\n"

    def download_commit_file(self, repo, file_path: str, ref: str) -> bytes:
        self.downloaded_commit_files.append((ref, file_path))
        if (ref, file_path) in self.failing_commit_files:
            raise GhCliError(self.failing_commit_files[(ref, file_path)])
        return self.commit_file_outputs[(ref, file_path)]

    def list_pr_issue_comments(self, repo: str, pr_number: int) -> list[IssueComment]:
        self.comment_calls.append("issue_comments")
        if "issue_comments" in self.failing_comment_sources:
            raise GhCliError(self.failing_comment_sources["issue_comments"])
        return self.issue_comments

    def list_pr_review_comments(self, repo: str, pr_number: int) -> list[ReviewComment]:
        self.comment_calls.append("review_comments")
        if "review_comments" in self.failing_comment_sources:
            raise GhCliError(self.failing_comment_sources["review_comments"])
        return self.review_comments

    def list_pr_reviews(self, repo: str, pr_number: int) -> list[PullRequestReview]:
        self.comment_calls.append("reviews")
        if "reviews" in self.failing_comment_sources:
            raise GhCliError(self.failing_comment_sources["reviews"])
        return self.reviews

    def list_pr_review_threads(self, repo: str, pr_number: int) -> list[ReviewThread]:
        self.comment_calls.append("review_threads")
        if "review_threads" in self.failing_comment_sources:
            raise GhCliError(self.failing_comment_sources["review_threads"])
        return self.review_threads


def test_build_log_filename_contains_job_id() -> None:
    check = CheckRun(
        name="Unit Tests / py311",
        workflow_name="CI",
        status="COMPLETED",
        conclusion="SUCCESS",
        details_url="https://github.com/octo/repo/actions/runs/1/job/2",
        check_type="CheckRun",
        run_id=1,
        job_id=2,
    )

    filename = build_log_filename(3, check)

    assert filename == "03-ci-unit-tests-py311-job-2.log"


def test_export_pr_check_logs_writes_logs_and_manifest(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        checks=[
            CheckRun(
                name="build / linux",
                workflow_name="CI",
                status="COMPLETED",
                conclusion="SUCCESS",
                details_url="https://github.com/octo/repo/actions/runs/11/job/22",
                check_type="CheckRun",
                run_id=11,
                job_id=22,
            ),
            CheckRun(
                name="external-ci",
                workflow_name=None,
                status="COMPLETED",
                conclusion="SUCCESS",
                details_url="https://ci.example.com/run/99",
                check_type="StatusContext",
                run_id=None,
                job_id=None,
            ),
        ]
    )

    result = export_pr_check_logs(config, gh)

    assert gh.available_checked is True
    assert gh.downloaded_jobs == [22]
    assert result.exported_logs == 1
    assert result.manifest_only_logs == 0
    assert result.skipped_checks == 1

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["repo"] == "octo/repo"
    assert manifest["pr_number"] == 42
    assert manifest["exported"][0]["path"].endswith(".log")
    assert manifest["exported"][0]["saved"] is True
    assert manifest["exported"][0]["has_log_content"] is True
    assert manifest["exported"][0]["empty_log_reason"] is None
    assert manifest["skipped"][0]["reason"] == "check is not a GitHub Actions job"
    assert manifest["skipped"][0]["reason_code"] == "unsupported_check_type"


def test_export_pr_check_logs_fails_when_nothing_is_exportable(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=99,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        checks=[
            CheckRun(
                name="external-ci",
                workflow_name=None,
                status="COMPLETED",
                conclusion="SUCCESS",
                details_url="https://ci.example.com/run/99",
                check_type="StatusContext",
                run_id=None,
                job_id=None,
            )
        ]
    )

    with pytest.raises(ExportError):
        export_pr_check_logs(config, gh)


def test_export_pr_check_logs_skips_missing_job_logs(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=77,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        checks=[
            CheckRun(
                name="build / linux",
                workflow_name="CI",
                status="COMPLETED",
                conclusion="SUCCESS",
                details_url="https://github.com/octo/repo/actions/runs/11/job/22",
                check_type="CheckRun",
                run_id=11,
                job_id=22,
            ),
            CheckRun(
                name="build / skipped",
                workflow_name="CI",
                status="COMPLETED",
                conclusion="SKIPPED",
                details_url="https://github.com/octo/repo/actions/runs/11/job/33",
                check_type="CheckRun",
                run_id=11,
                job_id=33,
            ),
        ],
        failing_jobs={33: "gh: Not Found (HTTP 404)"},
    )

    result = export_pr_check_logs(config, gh)

    assert result.exported_logs == 1
    assert result.manifest_only_logs == 0
    assert result.skipped_checks == 1


def test_export_pr_check_logs_keeps_zero_byte_skipped_job_log_in_manifest(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=88,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        checks=[
            CheckRun(
                name="build / skipped",
                workflow_name="CI",
                status="COMPLETED",
                conclusion="SKIPPED",
                details_url="https://github.com/octo/repo/actions/runs/11/job/33",
                check_type="CheckRun",
                run_id=11,
                job_id=33,
            )
        ],
        job_outputs={33: ""},
    )

    result = export_pr_check_logs(config, gh)

    assert result.exported_logs == 1
    assert result.manifest_only_logs == 0

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    exported_entry = manifest["exported"][0]

    assert exported_entry["saved"] is True
    assert exported_entry["bytes"] == 0
    assert exported_entry["has_log_content"] is False
    assert exported_entry["empty_log_reason"] == "job concluded skipped and produced no log output"
    assert (config.output_dir / exported_entry["path"]).exists()
    assert (config.output_dir / exported_entry["path"]).stat().st_size == 0


def test_export_pr_check_logs_can_skip_writing_empty_log_files(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=89,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=True,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        checks=[
            CheckRun(
                name="build / skipped",
                workflow_name="CI",
                status="COMPLETED",
                conclusion="SKIPPED",
                details_url="https://github.com/octo/repo/actions/runs/11/job/33",
                check_type="CheckRun",
                run_id=11,
                job_id=33,
            )
        ],
        job_outputs={33: ""},
    )

    result = export_pr_check_logs(config, gh)

    assert result.exported_logs == 0
    assert result.manifest_only_logs == 1

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    exported_entry = manifest["exported"][0]

    assert exported_entry["saved"] is False
    assert exported_entry["path"] is None
    assert exported_entry["bytes"] == 0
    assert exported_entry["has_log_content"] is False
    assert exported_entry["empty_log_reason"] == "job concluded skipped and produced no log output"
    assert list(config.output_dir.glob("*.log")) == []


def test_export_pr_commit_files_writes_commit_folders_and_manifests(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        commits=[commit],
        commit_details={
            commit.sha: CommitDetails(
                commit=commit,
                files=[
                    CommitFile(
                        path="src/app.py",
                        status="modified",
                        additions=3,
                        deletions=1,
                        changes=4,
                        previous_path=None,
                    ),
                    CommitFile(
                        path="README.md",
                        status="removed",
                        additions=0,
                        deletions=5,
                        changes=5,
                        previous_path=None,
                    ),
                ],
            )
        },
        commit_file_outputs={
            (commit.sha, "src/app.py"): b"print('hello')\n",
        },
    )

    result = export_pr_commit_files(config, gh)

    assert gh.available_checked is True
    assert result.commit_count == 1
    assert result.exported_files == 1
    assert result.skipped_files == 1

    exported_file = config.output_dir / "commits" / commit.sha / "src" / "app.py"
    assert exported_file.read_bytes() == b"print('hello')\n"

    commit_manifest = json.loads(
        (config.output_dir / "commits" / commit.sha / "_commit.json").read_text(encoding="utf-8")
    )
    assert commit_manifest["commit"]["sha"] == commit.sha
    assert commit_manifest["commit"]["author_name"] == "Alice Author"
    assert commit_manifest["commit"]["author_login"] == "alice-gh"
    assert commit_manifest["exported"][0]["path"] == f"commits/{commit.sha}/src/app.py"
    assert commit_manifest["skipped"][0]["reason_code"] == "removed"

    root_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert root_manifest["commit_count"] == 1
    assert root_manifest["exported_files"] == 1
    assert root_manifest["commits"][0]["folder"] == f"commits/{commit.sha}"
    assert root_manifest["commits"][0]["commit"]["author_name"] == "Alice Author"
    assert root_manifest["commits"][0]["commit"]["author_login"] == "alice-gh"


def test_export_pr_commit_files_continues_when_a_file_download_fails(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        commits=[commit],
        commit_details={
            commit.sha: CommitDetails(
                commit=commit,
                files=[
                    CommitFile(
                        path="src/app.py",
                        status="modified",
                        additions=3,
                        deletions=1,
                        changes=4,
                        previous_path=None,
                    ),
                    CommitFile(
                        path="src/missing.py",
                        status="modified",
                        additions=1,
                        deletions=0,
                        changes=1,
                        previous_path=None,
                    ),
                ],
            )
        },
        commit_file_outputs={
            (commit.sha, "src/app.py"): b"print('hello')\n",
        },
        failing_commit_files={
            (commit.sha, "src/missing.py"): "gh: Not Found (HTTP 404)",
        },
    )

    result = export_pr_commit_files(config, gh)

    assert result.exported_files == 1
    assert result.skipped_files == 1

    commit_manifest = json.loads(
        (config.output_dir / "commits" / commit.sha / "_commit.json").read_text(encoding="utf-8")
    )
    assert commit_manifest["skipped"][0]["path"] == "src/missing.py"
    assert commit_manifest["skipped"][0]["reason_code"] == "download_failed"


def _commit_log_config(*, tmp_path: Path) -> AppConfig:
    return AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=False,
        export_commit_log=True,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )


def test_export_pr_commit_log_writes_commit_metadata_only(tmp_path: Path) -> None:
    commit_one = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature\n\nLonger body.",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    commit_two = PrCommit(
        sha="def5678abc1234",
        short_sha="def5678",
        message_headline="Fix bug",
        message="Fix bug",
        author_name="Bob Author",
        author_email="bob@example.com",
        author_login="bob-gh",
        authored_date="2024-01-02T00:00:00Z",
        committer_name="Bob Committer",
        committer_email="bob-c@example.com",
        committer_login="bob-gh-c",
        committed_date="2024-01-02T00:00:01Z",
        url="https://github.com/octo/repo/commit/def5678abc1234",
    )
    config = _commit_log_config(tmp_path=tmp_path)
    gh = FakeGhCli(commits=[commit_one, commit_two])

    result = export_pr_commit_log(config, gh)

    assert gh.available_checked is True
    assert result.commit_count == 2
    assert gh.downloaded_commit_files == []
    assert not (config.output_dir / "commits").exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["repo"] == "octo/repo"
    assert manifest["pr_number"] == 42
    assert manifest["commit_count"] == 2
    assert len(manifest["commits"]) == 2
    first = manifest["commits"][0]
    assert first["sha"] == commit_one.sha
    assert first["short_sha"] == commit_one.short_sha
    assert first["message_headline"] == commit_one.message_headline
    assert first["message"] == commit_one.message
    assert first["author_name"] == commit_one.author_name
    assert first["author_email"] == commit_one.author_email
    assert first["author_login"] == commit_one.author_login
    assert first["authored_date"] == commit_one.authored_date
    assert first["committer_name"] == commit_one.committer_name
    assert first["committer_email"] == commit_one.committer_email
    assert first["committer_login"] == commit_one.committer_login
    assert first["committed_date"] == commit_one.committed_date
    assert first["url"] == commit_one.url


def test_export_pr_commit_log_and_files_share_one_commit_fetch(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
        export_comments=False,
        export_commit_log=True,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        commits=[commit],
        commit_details={
            commit.sha: CommitDetails(
                commit=commit,
                files=[
                    CommitFile(
                        path="src/app.py",
                        status="modified",
                        additions=3,
                        deletions=1,
                        changes=4,
                        previous_path=None,
                    ),
                ],
            )
        },
        commit_file_outputs={
            (commit.sha, "src/app.py"): b"print('hello')\n",
        },
    )

    cache = PrCommitCache()
    export_pr_commit_files(config, gh, cache)
    export_pr_commit_log(config, gh, cache)

    assert gh.list_pr_commits_calls == 1
    assert (config.output_dir / "commit-log.json").exists()
    assert (config.output_dir / "commits-manifest.json").exists()


def test_export_pr_commit_log_raises_when_pr_has_no_commits(tmp_path: Path) -> None:
    config = _commit_log_config(tmp_path=tmp_path)
    gh = FakeGhCli(commits=[])

    with pytest.raises(ExportError):
        export_pr_commit_log(config, gh)


def test_export_pr_commit_files_without_cache_still_fetches_commits(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
        export_comments=False,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )
    gh = FakeGhCli(
        commits=[commit],
        commit_details={
            commit.sha: CommitDetails(
                commit=commit,
                files=[
                    CommitFile(
                        path="src/app.py",
                        status="modified",
                        additions=3,
                        deletions=1,
                        changes=4,
                        previous_path=None,
                    ),
                ],
            )
        },
        commit_file_outputs={
            (commit.sha, "src/app.py"): b"print('hello')\n",
        },
    )

    export_pr_commit_files(config, gh)

    assert gh.list_pr_commits_calls == 1


def test_export_pr_commit_log_records_commit_authorship(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        author_name="Alice Author",
        author_email="alice@example.com",
        author_login="alice-gh",
        authored_date="2024-01-01T00:00:00Z",
        committer_name="Alice Committer",
        committer_email="alice-c@example.com",
        committer_login="alice-gh-c",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = _commit_log_config(tmp_path=tmp_path)
    gh = FakeGhCli(commits=[commit])

    result = export_pr_commit_log(config, gh)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    first = manifest["commits"][0]
    assert first["author_name"] == "Alice Author"
    assert first["author_email"] == "alice@example.com"
    assert first["author_login"] == "alice-gh"
    assert first["committer_name"] == "Alice Committer"
    assert first["committer_email"] == "alice-c@example.com"
    assert first["committer_login"] == "alice-gh-c"


def _comments_config(*, tmp_path: Path, pr_number: int = 42) -> AppConfig:
    return AppConfig(
        pr_number=pr_number,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=False,
        export_comments=True,
        export_commit_log=False,
        skip_check_logs=False,
        env_file=None,
        gh_host="github.com",
        gh_token=None,
        gh_config_dir=None,
        log_level="INFO",
    )


def test_export_pr_comments_writes_all_sources_to_json(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    issue_comment = IssueComment(
        comment_id=1,
        author="alice",
        author_type="User",
        body="looks good",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        url="https://github.com/octo/repo/issues/42#issuecomment-1",
    )
    review_comment = ReviewComment(
        comment_id=10,
        author="bob",
        author_type="User",
        body="please fix this",
        created_at="2024-01-02T00:00:00Z",
        updated_at="2024-01-02T00:00:00Z",
        url="https://github.com/octo/repo/pull/42#discussion_r10",
        path="src/app.py",
        line=5,
        original_line=5,
        side="RIGHT",
        commit_id="abc123",
        in_reply_to_id=None,
        diff_hunk="@@ -1,2 +1,2 @@",
        pull_request_review_id=100,
    )
    review = PullRequestReview(
        review_id=100,
        author="bob",
        author_type="User",
        body="overall fine",
        state="APPROVED",
        submitted_at="2024-01-02T00:00:01Z",
        url="https://github.com/octo/repo/pull/42#pullrequestreview-100",
        commit_id="abc123",
    )
    review_thread = ReviewThread(
        thread_id="thread-1",
        is_resolved=True,
        is_outdated=False,
        comment_ids=[10],
    )
    gh = FakeGhCli(
        issue_comments=[issue_comment],
        review_comments=[review_comment],
        reviews=[review],
        review_threads=[review_thread],
    )

    result = export_pr_comments(config, gh)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["repo"] == "octo/repo"
    assert payload["pr_number"] == 42
    assert len(payload["issue_comments"]) == 1
    assert payload["issue_comments"][0]["author"] == "alice"
    assert payload["issue_comments"][0]["author_type"] == "User"
    assert len(payload["review_comments"]) == 1
    assert payload["review_comments"][0]["author"] == "bob"
    assert payload["review_comments"][0]["author_type"] == "User"
    assert len(payload["reviews"]) == 1
    assert payload["reviews"][0]["author"] == "bob"
    assert payload["reviews"][0]["author_type"] == "User"
    assert len(payload["review_threads"]) == 1
    assert payload["counts"] == {
        "issue_comments": 1,
        "review_comments": 1,
        "reviews": 1,
        "review_threads": 1,
    }
    assert payload["skipped_sources"] == []


def test_export_pr_comments_writes_transcript_in_timestamp_order(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    issue_comments = [
        IssueComment(
            comment_id=1,
            author="alice",
            author_type="User",
            body="second in time",
            created_at="2024-02-01T00:00:00Z",
            updated_at=None,
            url=None,
        ),
        IssueComment(
            comment_id=2,
            author="carol",
            author_type="User",
            body="first in time",
            created_at="2024-01-01T00:00:00Z",
            updated_at=None,
            url=None,
        ),
        IssueComment(
            comment_id=3,
            author="dave",
            author_type="User",
            body="no timestamp here",
            created_at=None,
            updated_at=None,
            url=None,
        ),
    ]
    gh = FakeGhCli(issue_comments=issue_comments)

    export_pr_comments(config, gh)

    transcript = (config.output_dir / "comments.md").read_text(encoding="utf-8")
    first_position = transcript.index("first in time")
    second_position = transcript.index("second in time")
    no_timestamp_position = transcript.index("no timestamp here")
    assert first_position < second_position < no_timestamp_position


def test_export_pr_comments_transcript_preserves_an_empty_body(tmp_path: Path) -> None:
    """P2: an empty body must stay empty instead of becoming the (no body) placeholder."""
    config = _comments_config(tmp_path=tmp_path)
    reviews = [
        PullRequestReview(
            review_id=100,
            author="bob",
            author_type="User",
            body="",
            state="COMMENTED",
            submitted_at="2024-01-02T00:00:01Z",
            url=None,
            commit_id="abc123",
        ),
    ]
    issue_comments = [
        IssueComment(
            comment_id=1,
            author="alice",
            author_type="User",
            body=None,
            created_at="2024-01-01T00:00:00Z",
            updated_at=None,
            url=None,
        ),
    ]
    gh = FakeGhCli(issue_comments=issue_comments, reviews=reviews)

    export_pr_comments(config, gh)

    transcript = (config.output_dir / "comments.md").read_text(encoding="utf-8")
    lines = transcript.splitlines()
    review_index = lines.index("## bob - review (COMMENTED) - 2024-01-02T00:00:01Z")
    assert lines[review_index + 1] == ""
    assert lines[review_index + 2] == ""
    comment_index = lines.index("## alice - issue comment - 2024-01-01T00:00:00Z")
    assert lines[comment_index + 2] == "(no body)"
    assert transcript.count("(no body)") == 1


def test_export_pr_comments_records_a_failing_source_and_exports_the_rest(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    issue_comment = IssueComment(
        comment_id=1,
        author="alice",
        author_type="User",
        body="hello",
        created_at="2024-01-01T00:00:00Z",
        updated_at=None,
        url=None,
    )
    review_comment = ReviewComment(
        comment_id=10,
        author="bob",
        author_type="User",
        body="hello there",
        created_at="2024-01-02T00:00:00Z",
        updated_at=None,
        url=None,
        path="src/app.py",
        line=5,
        original_line=5,
        side="RIGHT",
        commit_id="abc123",
        in_reply_to_id=None,
        diff_hunk="@@ -1,2 +1,2 @@",
        pull_request_review_id=100,
    )
    gh = FakeGhCli(
        issue_comments=[issue_comment],
        review_comments=[review_comment],
        failing_comment_sources={"reviews": "gh: Not Found (HTTP 404)"},
    )

    result = export_pr_comments(config, gh)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert len(payload["issue_comments"]) == 1
    assert len(payload["review_comments"]) == 1
    assert payload["counts"]["reviews"] == 0
    assert len(payload["skipped_sources"]) == 1
    skipped_entry = payload["skipped_sources"][0]
    assert skipped_entry["source"] == "reviews"
    assert skipped_entry["reason_code"]
    assert skipped_entry["reason"]


def test_export_pr_comments_raises_when_every_source_fails(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    gh = FakeGhCli(
        failing_comment_sources={
            "issue_comments": "gh: Not Found (HTTP 404)",
            "review_comments": "gh: Not Found (HTTP 404)",
            "reviews": "gh: Not Found (HTTP 404)",
            "review_threads": "gh: GraphQL error",
        }
    )

    with pytest.raises(ExportError):
        export_pr_comments(config, gh)


def test_export_pr_comments_maps_thread_state_onto_review_comments(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    matched_comment = ReviewComment(
        comment_id=10,
        author="bob",
        author_type="User",
        body="matched",
        created_at="2024-01-02T00:00:00Z",
        updated_at=None,
        url=None,
        path="src/app.py",
        line=5,
        original_line=5,
        side="RIGHT",
        commit_id="abc123",
        in_reply_to_id=None,
        diff_hunk="@@ -1,2 +1,2 @@",
        pull_request_review_id=100,
    )
    unmatched_comment = ReviewComment(
        comment_id=11,
        author="carol",
        author_type="User",
        body="unmatched",
        created_at="2024-01-03T00:00:00Z",
        updated_at=None,
        url=None,
        path="src/app.py",
        line=6,
        original_line=6,
        side="RIGHT",
        commit_id="abc123",
        in_reply_to_id=None,
        diff_hunk="@@ -1,2 +1,2 @@",
        pull_request_review_id=100,
    )
    review_thread = ReviewThread(
        thread_id="thread-1",
        is_resolved=True,
        is_outdated=False,
        comment_ids=[10],
    )
    gh = FakeGhCli(
        review_comments=[matched_comment, unmatched_comment],
        review_threads=[review_thread],
    )

    result = export_pr_comments(config, gh)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    first_entry, second_entry = payload["review_comments"]
    assert first_entry["is_resolved"] is True
    assert first_entry["thread_id"] == "thread-1"
    assert second_entry["is_resolved"] is None
    assert second_entry["thread_id"] is None


def test_export_pr_comments_isolates_a_review_thread_failure(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    issue_comment = IssueComment(
        comment_id=1,
        author="alice",
        author_type="User",
        body="hello",
        created_at="2024-01-01T00:00:00Z",
        updated_at=None,
        url=None,
    )
    review_comment = ReviewComment(
        comment_id=10,
        author="bob",
        author_type="User",
        body="hello there",
        created_at="2024-01-02T00:00:00Z",
        updated_at=None,
        url=None,
        path="src/app.py",
        line=5,
        original_line=5,
        side="RIGHT",
        commit_id="abc123",
        in_reply_to_id=None,
        diff_hunk="@@ -1,2 +1,2 @@",
        pull_request_review_id=100,
    )
    review = PullRequestReview(
        review_id=100,
        author="bob",
        author_type="User",
        body="overall fine",
        state="APPROVED",
        submitted_at="2024-01-02T00:00:01Z",
        url=None,
        commit_id="abc123",
    )
    gh = FakeGhCli(
        issue_comments=[issue_comment],
        review_comments=[review_comment],
        reviews=[review],
        failing_comment_sources={"review_threads": "gh: GraphQL error"},
    )

    result = export_pr_comments(config, gh)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert len(payload["issue_comments"]) == 1
    assert len(payload["review_comments"]) == 1
    assert len(payload["reviews"]) == 1
    assert all(entry["is_resolved"] is None for entry in payload["review_comments"])
    skipped_sources = payload["skipped_sources"]
    assert len(skipped_sources) == 1
    assert skipped_sources[0]["source"] == "review_threads"


def test_export_pr_comments_transcript_has_no_absolute_path(tmp_path: Path) -> None:
    config = _comments_config(tmp_path=tmp_path)
    issue_comment = IssueComment(
        comment_id=1,
        author="alice",
        author_type="User",
        body="plain ascii body",
        created_at="2024-01-01T00:00:00Z",
        updated_at=None,
        url=None,
    )
    gh = FakeGhCli(issue_comments=[issue_comment])

    export_pr_comments(config, gh)

    text = (config.output_dir / "comments.md").read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert not re.search(r"[A-Za-z]:[\\/]", text)
    assert text.isascii()
