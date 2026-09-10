import logging

import pytest

from prinfo import __version__
from prinfo.cli import build_parser, main
from prinfo.exporter import ExportError
from prinfo.gh import GhCliError


def test_build_parser_supports_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit, match="0"):
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert captured.out.strip() == f"prinfo {__version__}"


def test_build_parser_supports_commit_export_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pr", "123", "--export-commit-files"])

    assert args.pr == 123
    assert args.export_commit_files is True


def test_build_parser_supports_comment_export_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pr", "123", "--export-comments"])

    assert args.export_comments is True


def test_build_parser_supports_commit_log_export_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pr", "123", "--export-commit-log"])

    assert args.export_commit_log is True


def test_build_parser_supports_both_new_export_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--pr",
            "123",
            "--export-comments",
            "--export-commit-log",
            "--skip-check-logs",
        ]
    )

    assert args.export_comments is True
    assert args.export_commit_log is True
    assert args.skip_check_logs is True


def test_build_parser_supports_skip_check_logs_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pr", "123", "--export-commit-files", "--skip-check-logs"])

    assert args.skip_check_logs is True


def test_main_skips_check_log_export_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    export_calls: list[str] = []

    class DummyGhCli:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    config = type(
        "Config",
        (),
        {
            "log_level": "INFO",
            "gh_host": "github.com",
            "gh_token": None,
            "gh_config_dir": None,
            "export_commit_files": True,
            "export_comments": False,
            "export_commit_log": False,
            "skip_check_logs": True,
        },
    )()

    def fake_resolve_config(args):
        return config

    def fake_export_pr_check_logs(config_arg, gh_arg):
        export_calls.append("logs")
        raise AssertionError("check log export should not run")

    def fake_export_pr_commit_files(config_arg, gh_arg, commits_cache_arg=None):
        export_calls.append("commits")
        return type(
            "CommitResult",
            (),
            {
                "exported_files": 1,
                "commit_count": 1,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
                "skipped_files": 0,
            },
        )()

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_check_logs", fake_export_pr_check_logs)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_files", fake_export_pr_commit_files)

    exit_code = main(["--pr", "1", "--export-commit-files", "--skip-check-logs"])

    assert exit_code == 0
    assert export_calls == ["commits"]


def _make_config(**overrides) -> object:
    base = {
        "log_level": "INFO",
        "gh_host": "github.com",
        "gh_token": None,
        "gh_config_dir": None,
        "export_commit_files": False,
        "export_comments": False,
        "export_commit_log": False,
        "skip_check_logs": True,
    }
    base.update(overrides)
    return type("Config", (), base)()


class DummyGhCli:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


def test_main_returns_zero_when_one_mode_fails_and_another_succeeds(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(export_comments=True, export_commit_log=True)
    calls: list[str] = []

    def fake_resolve_config(args):
        return config

    def fake_export_pr_comments(config_arg, gh_arg):
        calls.append("comments")
        raise ExportError("comment export boom")

    def fake_export_pr_commit_log(config_arg, gh_arg, commits_cache_arg=None):
        calls.append("commit_log")
        return type(
            "CommitLogResult",
            (),
            {
                "commit_count": 3,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
            },
        )()

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_comments", fake_export_pr_comments)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_log", fake_export_pr_commit_log)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1", "--export-comments", "--export-commit-log"])

    assert exit_code == 0
    assert set(calls) == {"comments", "commit_log"}
    assert "comment export boom" in caplog.text


def test_main_continues_other_modes_when_one_mode_raises_gh_cli_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """P1: a GhCliError from one export mode must not abort the remaining modes."""
    config = _make_config(export_comments=True, export_commit_log=True)
    calls: list[str] = []

    def fake_resolve_config(args):
        return config

    def fake_export_pr_comments(config_arg, gh_arg):
        calls.append("comments")
        raise GhCliError("gh api boom")

    def fake_export_pr_commit_log(config_arg, gh_arg, commits_cache_arg=None):
        calls.append("commit_log")
        return type(
            "CommitLogResult",
            (),
            {
                "commit_count": 3,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
            },
        )()

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_comments", fake_export_pr_comments)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_log", fake_export_pr_commit_log)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1", "--export-comments", "--export-commit-log"])

    assert exit_code == 0
    assert set(calls) == {"comments", "commit_log"}
    assert "gh api boom" in caplog.text


def test_main_returns_one_when_every_requested_mode_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_config(export_comments=True, export_commit_log=True)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_comments(config_arg, gh_arg):
        raise ExportError("comment export boom")

    def fake_export_pr_commit_log(config_arg, gh_arg, commits_cache_arg=None):
        raise ExportError("commit log export boom")

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_comments", fake_export_pr_comments)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_log", fake_export_pr_commit_log)

    exit_code = main(["--pr", "1", "--export-comments", "--export-commit-log"])

    assert exit_code == 1


def test_main_shares_one_commit_cache_between_commit_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_config(export_commit_files=True, export_commit_log=True)
    received_caches: list[object] = []

    def fake_resolve_config(args):
        return config

    def fake_export_pr_commit_files(config_arg, gh_arg, commits_cache_arg=None):
        received_caches.append(commits_cache_arg)
        return type(
            "CommitResult",
            (),
            {
                "exported_files": 1,
                "commit_count": 1,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
                "skipped_files": 0,
            },
        )()

    def fake_export_pr_commit_log(config_arg, gh_arg, commits_cache_arg=None):
        received_caches.append(commits_cache_arg)
        return type(
            "CommitLogResult",
            (),
            {
                "commit_count": 1,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
            },
        )()

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_files", fake_export_pr_commit_files)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_log", fake_export_pr_commit_log)

    exit_code = main(["--pr", "1", "--export-commit-files", "--export-commit-log"])

    assert exit_code == 0
    assert len(received_caches) == 2
    assert received_caches[0] is received_caches[1]


def test_version_reports_expected_release(capsys: pytest.CaptureFixture[str]) -> None:
    assert __version__ == "0.4.0"

    parser = build_parser()
    with pytest.raises(SystemExit, match="0"):
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert captured.out.strip() == "prinfo 0.4.0"
