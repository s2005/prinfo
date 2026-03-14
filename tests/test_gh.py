import subprocess

import pytest

from prinfo.gh import (
    GhCli,
    GhCliError,
    RepoRef,
    parse_actions_job_url,
    parse_repo_ref,
)


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


def test_list_pr_commits_flattens_paginated_response() -> None:
    payload = (
        b'[[{"sha":"abc1234def","html_url":"https://github.com/octo/repo/commit/abc1234def",'
        b'"commit":{"message":"First commit\\n\\nBody","author":{"date":"2024-01-01T00:00:00Z"},'
        b'"committer":{"date":"2024-01-01T00:00:01Z"}}}],'
        b'[{"sha":"fedcba9876","html_url":"https://github.com/octo/repo/commit/fedcba9876",'
        b'"commit":{"message":"Second commit","author":{"date":"2024-01-02T00:00:00Z"},'
        b'"committer":{"date":"2024-01-02T00:00:01Z"}}}]]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    commits = client.list_pr_commits("octo/repo", 1)

    assert [commit.sha for commit in commits] == ["abc1234def", "fedcba9876"]
    assert commits[0].short_sha == "abc1234"
    assert commits[0].message_headline == "First commit"
    assert commits[1].message_headline == "Second commit"


def test_get_commit_details_collects_files_from_all_pages() -> None:
    payload = (
        b'[{"sha":"abc1234def","html_url":"https://github.com/octo/repo/commit/abc1234def",'
        b'"commit":{"message":"First commit","author":{"date":"2024-01-01T00:00:00Z"},'
        b'"committer":{"date":"2024-01-01T00:00:01Z"}},'
        b'"files":[{"filename":"src/app.py","status":"modified","additions":2,"deletions":1,"changes":3}]},'
        b'{"sha":"abc1234def","html_url":"https://github.com/octo/repo/commit/abc1234def",'
        b'"commit":{"message":"First commit","author":{"date":"2024-01-01T00:00:00Z"},'
        b'"committer":{"date":"2024-01-01T00:00:01Z"}},'
        b'"files":[{"filename":"README.md","status":"added","additions":5,"deletions":0,"changes":5}]}]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    details = client.get_commit_details(
        repo=RepoRef(host="github.com", owner="octo", name="repo"),
        sha="abc1234def",
    )

    assert details.commit.sha == "abc1234def"
    assert [file.path for file in details.files] == ["src/app.py", "README.md"]


def test_download_commit_file_returns_raw_bytes() -> None:
    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"\x00\xffdata", stderr=b"")

    client = GhCli(runner=bytes_runner)

    output = client.download_commit_file(
        repo=RepoRef(host="github.com", owner="octo", name="repo"),
        file_path="src/data.bin",
        ref="abc123",
    )

    assert output == b"\x00\xffdata"
