import json
from pathlib import Path

import pytest

from prinfo.config import AppConfig
from prinfo.exporter import ExportError, build_log_filename, export_pr_check_logs
from prinfo.gh import CheckRun, GhCliError


class FakeGhCli:
    def __init__(
        self,
        *,
        repo: str | None = None,
        checks: list[CheckRun] | None = None,
        failing_jobs: dict[int, str] | None = None,
    ) -> None:
        self.repo = repo
        self.checks = checks or []
        self.failing_jobs = failing_jobs or {}
        self.downloaded_jobs: list[int] = []
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

    def download_job_log(self, repo, job_id: int) -> str:
        self.downloaded_jobs.append(job_id)
        if job_id in self.failing_jobs:
            raise GhCliError(self.failing_jobs[job_id])
        return f"log-output-{job_id}\n"


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
    assert result.skipped_checks == 1

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["repo"] == "octo/repo"
    assert manifest["pr_number"] == 42
    assert manifest["exported"][0]["path"].endswith(".log")
    assert manifest["skipped"][0]["reason"] == "check is not a GitHub Actions job"


def test_export_pr_check_logs_fails_when_nothing_is_exportable(tmp_path: Path) -> None:
    config = AppConfig(
        pr_number=99,
        repo="octo/repo",
        output_dir=tmp_path / "output",
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
    assert result.skipped_checks == 1
