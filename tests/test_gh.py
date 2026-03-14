import subprocess

import pytest

from prinfo.gh import GhCli, GhCliError, RepoRef, parse_actions_job_url, parse_repo_ref


def test_parse_actions_job_url_extracts_identifiers() -> None:
    job = parse_actions_job_url("https://github.com/octo/repo/actions/runs/123/job/456")

    assert job is not None
    assert job.host == "github.com"
    assert job.owner == "octo"
    assert job.repo == "repo"
    assert job.run_id == 123
    assert job.job_id == 456


def test_parse_repo_ref_supports_default_host() -> None:
    repo = parse_repo_ref("octo/repo", "github.com")

    assert repo.full_name == "octo/repo"


def test_parse_repo_ref_supports_explicit_host() -> None:
    repo = parse_repo_ref("git.example.com/octo/repo", "github.com")

    assert repo.full_name == "git.example.com/octo/repo"


def test_gh_cli_raises_when_command_fails() -> None:
    def failing_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="boom")

    client = GhCli(runner=failing_runner)

    with pytest.raises(GhCliError, match="boom"):
        client.list_pr_checks("octo/repo", 1)


def test_download_job_log_decodes_problematic_bytes_with_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"\xfflog-output\n", stderr=b"")

    client = GhCli(runner=bytes_runner)

    with caplog.at_level("DEBUG"):
        output = client.download_job_log(
            repo=RepoRef(host="github.com", owner="octo", name="repo"),
            job_id=123,
        )

    assert output == b"\xfflog-output\n".decode("cp1252")
    assert "fallback encoding cp1252" in caplog.text


def test_run_text_returns_empty_string_when_subprocess_stdout_is_none() -> None:
    def none_stdout_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=None, stderr=b"")

    client = GhCli(runner=none_stdout_runner)

    assert client._run_text(["api"]) == ""
