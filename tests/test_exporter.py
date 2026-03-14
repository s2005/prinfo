import json
from pathlib import Path

import pytest

from prinfo.config import AppConfig
from prinfo.exporter import (
    ExportError,
    build_log_filename,
    export_pr_check_logs,
    export_pr_commit_files,
)
from prinfo.gh import CheckRun, CommitDetails, CommitFile, GhCliError, PrCommit


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
    ) -> None:
        self.repo = repo
        self.checks = checks or []
        self.commits = commits or []
        self.commit_details = commit_details or {}
        self.job_outputs = job_outputs or {}
        self.commit_file_outputs = commit_file_outputs or {}
        self.failing_jobs = failing_jobs or {}
        self.failing_commit_files = failing_commit_files or {}
        self.downloaded_jobs: list[int] = []
        self.downloaded_commit_files: list[tuple[str, str]] = []
        self.available_checked = False

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
        authored_date="2024-01-01T00:00:00Z",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
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
    assert commit_manifest["exported"][0]["path"] == f"commits/{commit.sha}/src/app.py"
    assert commit_manifest["skipped"][0]["reason_code"] == "removed"

    root_manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert root_manifest["commit_count"] == 1
    assert root_manifest["exported_files"] == 1
    assert root_manifest["commits"][0]["folder"] == f"commits/{commit.sha}"


def test_export_pr_commit_files_continues_when_a_file_download_fails(tmp_path: Path) -> None:
    commit = PrCommit(
        sha="abc1234def5678",
        short_sha="abc1234",
        message_headline="Add feature",
        message="Add feature",
        authored_date="2024-01-01T00:00:00Z",
        committed_date="2024-01-01T00:00:01Z",
        url="https://github.com/octo/repo/commit/abc1234def5678",
    )
    config = AppConfig(
        pr_number=42,
        repo="octo/repo",
        output_dir=tmp_path / "output",
        skip_empty_logs=False,
        export_commit_files=True,
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
