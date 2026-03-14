import subprocess

import pytest

from prinfo.gh import GhCli, GhCliError, parse_actions_job_url, parse_repo_ref


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
