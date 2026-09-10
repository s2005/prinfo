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
        b'"commit":{"message":"First commit\\n\\nBody",'
        b'"author":{"name":"Alice Author","email":"alice@example.com","date":"2024-01-01T00:00:00Z"},'
        b'"committer":{"name":"Alice Committer","email":"alice-c@example.com","date":"2024-01-01T00:00:01Z"}},'
        b'"author":{"login":"alice-gh"},"committer":{"login":"alice-gh-c"}}],'
        b'[{"sha":"fedcba9876","html_url":"https://github.com/octo/repo/commit/fedcba9876",'
        b'"commit":{"message":"Second commit",'
        b'"author":{"name":"Bob Author","email":"bob@example.com","date":"2024-01-02T00:00:00Z"},'
        b'"committer":{"name":"Bob Committer","email":"bob-c@example.com","date":"2024-01-02T00:00:01Z"}},'
        b'"author":{"login":"bob-gh"},"committer":{"login":"bob-gh-c"}}]]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    commits = client.list_pr_commits("octo/repo", 1)

    assert [commit.sha for commit in commits] == ["abc1234def", "fedcba9876"]
    assert commits[0].short_sha == "abc1234"
    assert commits[0].message_headline == "First commit"
    assert commits[1].message_headline == "Second commit"
    assert commits[0].author_name == "Alice Author"
    assert commits[0].author_email == "alice@example.com"
    assert commits[0].author_login == "alice-gh"
    assert commits[0].committer_name == "Alice Committer"
    assert commits[0].committer_email == "alice-c@example.com"
    assert commits[0].committer_login == "alice-gh-c"
    assert commits[1].author_name == "Bob Author"
    assert commits[1].author_email == "bob@example.com"
    assert commits[1].author_login == "bob-gh"
    assert commits[1].committer_name == "Bob Committer"
    assert commits[1].committer_email == "bob-c@example.com"
    assert commits[1].committer_login == "bob-gh-c"


def test_list_pr_commits_tolerates_missing_github_author() -> None:
    payload = (
        b'[{"sha":"abc1234def","html_url":"https://github.com/octo/repo/commit/abc1234def",'
        b'"commit":{"message":"First commit",'
        b'"author":{"name":"Alice Author","email":"alice@example.com","date":"2024-01-01T00:00:00Z"},'
        b'"committer":{"name":"Alice Committer","email":"alice-c@example.com","date":"2024-01-01T00:00:01Z"}},'
        b'"author":null,"committer":null}]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    commits = client.list_pr_commits("octo/repo", 1)

    assert commits[0].author_login is None
    assert commits[0].committer_login is None
    assert commits[0].author_name == "Alice Author"
    assert commits[0].author_email == "alice@example.com"


def test_list_pr_commits_resolves_absent_author_fields_to_none() -> None:
    payload = b'[{"sha":"abc1234def","commit":{"message":"First commit"}}]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    commits = client.list_pr_commits("octo/repo", 1)

    commit = commits[0]
    assert commit.author_name is None
    assert commit.author_email is None
    assert commit.author_login is None
    assert commit.authored_date is None
    assert commit.committer_name is None
    assert commit.committer_email is None
    assert commit.committer_login is None
    assert commit.committed_date is None


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


def test_list_pr_issue_comments_parses_paginated_payload() -> None:
    payload = (
        b'[[{"id":1,"user":{"login":"alice","type":"User"},"body":"first",'
        b'"created_at":"2024-01-01T00:00:00Z","updated_at":"2024-01-01T00:00:01Z",'
        b'"html_url":"https://github.com/octo/repo/issues/1#issuecomment-1"}],'
        b'[{"id":2,"user":{"login":"bob","type":"User"},"body":"second",'
        b'"created_at":"2024-01-02T00:00:00Z","updated_at":"2024-01-02T00:00:01Z",'
        b'"html_url":"https://github.com/octo/repo/issues/1#issuecomment-2"}]]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    comments = client.list_pr_issue_comments("octo/repo", 1)

    assert len(comments) == 2
    assert comments[0].comment_id == 1
    assert comments[0].author == "alice"
    assert comments[0].author_type == "User"
    assert comments[0].body == "first"
    assert comments[0].created_at == "2024-01-01T00:00:00Z"
    assert comments[0].updated_at == "2024-01-01T00:00:01Z"
    assert comments[0].url == "https://github.com/octo/repo/issues/1#issuecomment-1"
    assert comments[1].comment_id == 2
    assert comments[1].author == "bob"
    assert comments[1].author_type == "User"
    assert comments[1].body == "second"
    assert comments[1].created_at == "2024-01-02T00:00:00Z"
    assert comments[1].updated_at == "2024-01-02T00:00:01Z"
    assert comments[1].url == "https://github.com/octo/repo/issues/1#issuecomment-2"


def test_list_pr_review_comments_parses_inline_fields() -> None:
    payload = (
        b'[{"id":10,"user":{"login":"carol","type":"User"},"body":"nit",'
        b'"created_at":"2024-01-01T00:00:00Z","updated_at":"2024-01-01T00:00:01Z",'
        b'"html_url":"https://github.com/octo/repo/pull/1#discussion_r10",'
        b'"path":"src/app.py","line":12,"original_line":10,"side":"RIGHT",'
        b'"commit_id":"abc1234","in_reply_to_id":5,"diff_hunk":"@@ -1 +1 @@",'
        b'"pull_request_review_id":99}]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    comments = client.list_pr_review_comments("octo/repo", 1)

    assert len(comments) == 1
    comment = comments[0]
    assert comment.comment_id == 10
    assert comment.author == "carol"
    assert comment.author_type == "User"
    assert comment.body == "nit"
    assert comment.created_at == "2024-01-01T00:00:00Z"
    assert comment.updated_at == "2024-01-01T00:00:01Z"
    assert comment.url == "https://github.com/octo/repo/pull/1#discussion_r10"
    assert comment.path == "src/app.py"
    assert comment.line == 12
    assert comment.original_line == 10
    assert comment.side == "RIGHT"
    assert comment.commit_id == "abc1234"
    assert comment.in_reply_to_id == 5
    assert comment.diff_hunk == "@@ -1 +1 @@"
    assert comment.pull_request_review_id == 99
    assert comment.is_resolved is None
    assert comment.thread_id is None


def test_list_pr_reviews_parses_review_state() -> None:
    payload = (
        b'[{"id":42,"user":{"login":"dave","type":"User"},"body":"looks good",'
        b'"state":"APPROVED","submitted_at":"2024-01-03T00:00:00Z",'
        b'"html_url":"https://github.com/octo/repo/pull/1#pullrequestreview-42",'
        b'"commit_id":"def5678"}]'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    reviews = client.list_pr_reviews("octo/repo", 1)

    assert len(reviews) == 1
    review = reviews[0]
    assert review.review_id == 42
    assert review.author == "dave"
    assert review.state == "APPROVED"
    assert review.submitted_at == "2024-01-03T00:00:00Z"
    assert review.body == "looks good"
    assert review.url == "https://github.com/octo/repo/pull/1#pullrequestreview-42"
    assert review.commit_id == "def5678"


def test_list_pr_issue_comments_raises_when_entry_is_not_an_object() -> None:
    payload = b'["not-an-object"]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    with pytest.raises(GhCliError, match="issues/1/comments"):
        client.list_pr_issue_comments("octo/repo", 1)


def test_list_pr_review_comments_raises_when_entry_is_not_an_object() -> None:
    payload = b'["not-an-object"]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    with pytest.raises(GhCliError, match="pulls/1/comments"):
        client.list_pr_review_comments("octo/repo", 1)


def test_list_pr_reviews_raises_when_entry_is_not_an_object() -> None:
    payload = b'["not-an-object"]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    with pytest.raises(GhCliError, match="pulls/1/reviews"):
        client.list_pr_reviews("octo/repo", 1)


def test_list_pr_issue_comments_tolerates_missing_user() -> None:
    payload = b'[{"id":1,"body":"no user here"}]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    comments = client.list_pr_issue_comments("octo/repo", 1)

    assert comments[0].author is None
    assert comments[0].author_type is None


def test_list_pr_review_comments_resolves_absent_optional_fields_to_none() -> None:
    payload = b'[{"id":1,"body":"minimal"}]'

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    comments = client.list_pr_review_comments("octo/repo", 1)

    comment = comments[0]
    assert comment.path is None
    assert comment.line is None
    assert comment.side is None
    assert comment.in_reply_to_id is None
    assert comment.diff_hunk is None


def test_list_pr_review_threads_parses_paginated_graphql_documents() -> None:
    page_one = (
        b'{"data":{"repository":{"pullRequest":{"reviewThreads":{'
        b'"pageInfo":{"hasNextPage":true,"endCursor":"cursor-1"},'
        b'"nodes":[{"id":"thread-1","isResolved":true,"isOutdated":false,'
        b'"comments":{"nodes":[{"databaseId":10},{"databaseId":11}]}}]}}}}}'
    )
    page_two = (
        b'{"data":{"repository":{"pullRequest":{"reviewThreads":{'
        b'"pageInfo":{"hasNextPage":false,"endCursor":null},'
        b'"nodes":[{"id":"thread-2","isResolved":false,"isOutdated":true,'
        b'"comments":{"nodes":[{"databaseId":20}]}}]}}}}}'
    )
    payload = page_one + page_two

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    threads = client.list_pr_review_threads("octo/repo", 1)

    assert len(threads) == 2
    assert threads[0].thread_id == "thread-1"
    assert threads[0].is_resolved is True
    assert threads[0].is_outdated is False
    assert threads[0].comment_ids == [10, 11]
    assert threads[1].thread_id == "thread-2"
    assert threads[1].is_resolved is False
    assert threads[1].is_outdated is True
    assert threads[1].comment_ids == [20]


def test_list_pr_review_threads_parses_single_json_document() -> None:
    payload = (
        b'{"data":{"repository":{"pullRequest":{"reviewThreads":{'
        b'"pageInfo":{"hasNextPage":false,"endCursor":null},'
        b'"nodes":[{"id":"thread-1","isResolved":true,"isOutdated":false,'
        b'"comments":{"nodes":[{"databaseId":10}]}}]}}}}}'
    )

    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    client = GhCli(runner=bytes_runner)

    threads = client.list_pr_review_threads("octo/repo", 1)

    assert len(threads) == 1
    assert threads[0].thread_id == "thread-1"


def test_list_pr_review_threads_passes_enterprise_hostname() -> None:
    captured_commands: list[list[str]] = []

    def bytes_runner(*args, **kwargs):
        captured_commands.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0, stdout=b"", stderr=b"")

    client = GhCli(runner=bytes_runner)

    threads = client.list_pr_review_threads("git.example.com/octo/repo", 7)

    assert threads == []
    assert len(captured_commands) == 1
    command = captured_commands[0]
    assert "graphql" in command
    hostname_index = command.index("--hostname")
    assert command[hostname_index + 1] == "git.example.com"
    f_flag_indices = [index for index, value in enumerate(command) if value == "-F"]
    assert any(command[index + 1] == "number=7" for index in f_flag_indices)


def test_list_pr_review_threads_returns_empty_list_for_blank_output() -> None:
    def bytes_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"", stderr=b"")

    client = GhCli(runner=bytes_runner)

    threads = client.list_pr_review_threads("octo/repo", 1)

    assert threads == []
