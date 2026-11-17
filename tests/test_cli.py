import logging
from pathlib import Path

import pytest

from prinfo import __version__
from prinfo.cli import _log_skip_severity, build_parser, main
from prinfo.exporter import (
    ACTIONABLE_CHECK_SKIP_REASONS,
    ACTIONABLE_COMMIT_SKIP_REASONS,
    AgentSessionExportResult,
    CommitExportResult,
    ExportError,
    ExportResult,
)
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


def test_build_parser_supports_agent_sessions_export_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["--pr", "123", "--export-agent-sessions"])

    assert args.export_agent_sessions is True


def test_build_parser_help_mentions_agent_sessions_flag() -> None:
    help_text = " ".join(build_parser().format_help().split())

    assert "--export-agent-sessions" in help_text
    assert "--export-commit-log or --export-agent-sessions" in help_text


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
            "export_agent_sessions": False,
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
        "export_agent_sessions": False,
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


def test_main_continues_other_modes_when_one_mode_raises_os_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """P2: an OSError from one export mode must not abort the remaining modes."""
    config = _make_config(export_comments=True, export_commit_log=True)
    calls: list[str] = []

    def fake_resolve_config(args):
        return config

    def fake_export_pr_comments(config_arg, gh_arg):
        calls.append("comments")
        raise IsADirectoryError("comments.json is a directory")

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
    assert "comments.json is a directory" in caplog.text


def test_main_returns_one_when_every_mode_raises_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2: an OSError in every requested mode still exits non-zero."""
    config = _make_config(export_comments=True, export_commit_log=True)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_comments(config_arg, gh_arg):
        raise IsADirectoryError("comments.json is a directory")

    def fake_export_pr_commit_log(config_arg, gh_arg, commits_cache_arg=None):
        raise PermissionError("commit-log.json is not writable")

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_comments", fake_export_pr_comments)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_log", fake_export_pr_commit_log)

    exit_code = main(["--pr", "1", "--export-comments", "--export-commit-log"])

    assert exit_code == 1


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
    assert __version__ == "0.5.0"

    parser = build_parser()
    with pytest.raises(SystemExit, match="0"):
        parser.parse_args(["--version"])

    captured = capsys.readouterr()
    assert captured.out.strip() == "prinfo 0.5.0"


def test_main_does_not_warn_when_every_commit_skip_is_benign(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(export_commit_files=True)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_commit_files(config_arg, gh_arg, commits_cache_arg=None):
        return CommitExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/commits-manifest.json"),
            commit_count=1,
            exported_files=4,
            skipped_files=8,
        )

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_files", fake_export_pr_commit_files)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1", "--export-commit-files"])

    assert exit_code == 0
    # All eight skips are deleted files, which is normal and needs no user action.
    assert "Skipped 8 commit file(s)." not in caplog.text


def test_main_warns_only_for_actionable_commit_skips(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(export_commit_files=True)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_commit_files(config_arg, gh_arg, commits_cache_arg=None):
        return CommitExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/commits-manifest.json"),
            commit_count=1,
            exported_files=4,
            skipped_files=5,
            skipped_file_reasons={"removed": 3, "download_failed": 2},
        )

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_files", fake_export_pr_commit_files)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1", "--export-commit-files"])

    assert exit_code == 0
    # Only the two download failures are actionable; the three removed-file skips are benign.
    assert "2 commit file(s) could not be downloaded." in caplog.text
    assert "3 commit file(s) could not be downloaded." not in caplog.text


def test_main_warns_and_infos_for_mixed_check_log_skips(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(skip_check_logs=False)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_check_logs(config_arg, gh_arg):
        return ExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/manifest.json"),
            exported_logs=3,
            manifest_only_logs=0,
            skipped_checks=5,
            skipped_check_reasons={"unsupported_check_type": 3, "missing_log_content": 2},
        )

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_check_logs", fake_export_pr_check_logs)

    with caplog.at_level(logging.INFO):
        exit_code = main(["--pr", "1"])

    assert exit_code == 0
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    info_records = [r for r in caplog.records if r.levelname == "INFO" and "check(s)" in r.getMessage()]
    assert len(warning_records) == 1
    assert warning_records[0].getMessage() == "2 check(s) could not produce a log."
    assert len(info_records) == 1
    assert info_records[0].getMessage() == "3 check(s) are not GitHub Actions jobs and were skipped."


def test_main_does_not_warn_when_every_check_skip_is_benign(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(skip_check_logs=False)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_check_logs(config_arg, gh_arg):
        return ExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/manifest.json"),
            exported_logs=3,
            manifest_only_logs=0,
            skipped_checks=5,
            skipped_check_reasons={"unsupported_check_type": 5},
        )

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_check_logs", fake_export_pr_check_logs)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1"])

    assert exit_code == 0
    # All five skips are non-Actions checks, which is benign and needs no user action.
    assert not any(r.levelname == "WARNING" for r in caplog.records)
    assert "Skipped 5 check(s)." not in caplog.text


def test_log_skip_severity_mixed_breakdown_logs_warning_and_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("prinfo.test_skip_severity")

    with caplog.at_level(logging.INFO, logger="prinfo.test_skip_severity"):
        _log_skip_severity(
            logger,
            total=5,
            breakdown={"removed": 3, "download_failed": 2},
            actionable_reasons=frozenset({"download_failed"}),
            actionable_message="%s actionable item(s).",
            benign_message="%s benign item(s).",
        )

    assert len(caplog.records) == 2
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    assert len(warning_records) == 1
    assert len(info_records) == 1
    assert warning_records[0].getMessage() == "2 actionable item(s)."
    assert info_records[0].getMessage() == "3 benign item(s)."


def test_log_skip_severity_actionable_only_logs_warning_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("prinfo.test_skip_severity")

    with caplog.at_level(logging.INFO, logger="prinfo.test_skip_severity"):
        _log_skip_severity(
            logger,
            total=4,
            breakdown={"download_failed": 4},
            actionable_reasons=frozenset({"download_failed"}),
            actionable_message="%s actionable item(s).",
            benign_message="%s benign item(s).",
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert caplog.records[0].getMessage() == "4 actionable item(s)."


def test_log_skip_severity_benign_only_logs_info_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("prinfo.test_skip_severity")

    with caplog.at_level(logging.INFO, logger="prinfo.test_skip_severity"):
        _log_skip_severity(
            logger,
            total=6,
            breakdown={"removed": 6},
            actionable_reasons=frozenset({"download_failed"}),
            actionable_message="%s actionable item(s).",
            benign_message="%s benign item(s).",
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].getMessage() == "6 benign item(s)."


def test_log_skip_severity_zero_total_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("prinfo.test_skip_severity")

    with caplog.at_level(logging.INFO, logger="prinfo.test_skip_severity"):
        _log_skip_severity(
            logger,
            total=0,
            breakdown={"download_failed": 3},
            actionable_reasons=frozenset({"download_failed"}),
            actionable_message="%s actionable item(s).",
            benign_message="%s benign item(s).",
        )

    assert len(caplog.records) == 0


def test_both_summary_branches_call_one_shared_severity_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _make_config(skip_check_logs=False, export_commit_files=True)

    def fake_resolve_config(args):
        return config

    def fake_export_pr_check_logs(config_arg, gh_arg):
        return ExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/manifest.json"),
            exported_logs=1,
            manifest_only_logs=0,
            skipped_checks=2,
            skipped_check_reasons={"missing_log_content": 2},
        )

    def fake_export_pr_commit_files(config_arg, gh_arg, commits_cache_arg=None):
        return CommitExportResult(
            repo="octo/repo",
            pr_number=1,
            output_dir=Path("out"),
            manifest_path=Path("out/commits-manifest.json"),
            commit_count=1,
            exported_files=1,
            skipped_files=3,
            skipped_file_reasons={"download_failed": 3},
        )

    calls: list[frozenset[str]] = []

    def spy_log_skip_severity(logger, *, total, breakdown, actionable_reasons, **kwargs):
        calls.append(actionable_reasons)

    monkeypatch.setattr("prinfo.cli.resolve_config", fake_resolve_config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_check_logs", fake_export_pr_check_logs)
    monkeypatch.setattr("prinfo.cli.export_pr_commit_files", fake_export_pr_commit_files)
    monkeypatch.setattr("prinfo.cli._log_skip_severity", spy_log_skip_severity)

    exit_code = main(["--pr", "1", "--export-commit-files"])

    assert exit_code == 0
    # Patching the one helper intercepts both summary branches, which is what proves
    # the check-log and commit-file splits share a single implementation.
    assert calls == [ACTIONABLE_CHECK_SKIP_REASONS, ACTIONABLE_COMMIT_SKIP_REASONS]


def _sessions_result(**overrides) -> AgentSessionExportResult:
    values = {
        "repo": "octo/repo",
        "pr_number": 1,
        "output_dir": Path("out/agent-sessions"),
        "manifest_path": Path("out/agent-sessions/agent-sessions.json"),
        "copilot_api_host": "api.githubcopilot.com",
        "exported_sessions": 0,
        "skipped_sessions": 0,
        "findings_count": 0,
    }
    values.update(overrides)
    return AgentSessionExportResult(**values)


def _run_sessions_mode(monkeypatch: pytest.MonkeyPatch, fake_export) -> int:
    config = _make_config(export_agent_sessions=True)
    monkeypatch.setattr("prinfo.cli.resolve_config", lambda args: config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_agent_sessions", fake_export)
    return main(["--pr", "1", "--export-agent-sessions"])


def test_main_runs_agent_sessions_mode_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_export(config_arg, gh_arg):
        calls.append("sessions")
        return _sessions_result(exported_sessions=1, findings_count=2)

    assert _run_sessions_mode(monkeypatch, fake_export) == 0
    assert calls == ["sessions"]


def test_main_agent_sessions_failure_does_not_stop_comments(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    config = _make_config(export_agent_sessions=True, export_comments=True)
    calls: list[str] = []

    def fake_sessions(config_arg, gh_arg):
        calls.append("sessions")
        raise ExportError("sessions boom")

    def fake_comments(config_arg, gh_arg):
        calls.append("comments")
        return type(
            "CommentResult",
            (),
            {
                "issue_comment_count": 0,
                "review_comment_count": 0,
                "review_count": 0,
                "review_thread_count": 0,
                "pr_number": 1,
                "repo": "octo/repo",
                "output_dir": "out",
                "skipped_sources": 0,
            },
        )()

    monkeypatch.setattr("prinfo.cli.resolve_config", lambda args: config)
    monkeypatch.setattr("prinfo.cli.configure_logging", lambda log_level: None)
    monkeypatch.setattr("prinfo.cli.GhCli", DummyGhCli)
    monkeypatch.setattr("prinfo.cli.export_pr_agent_sessions", fake_sessions)
    monkeypatch.setattr("prinfo.cli.export_pr_comments", fake_comments)

    with caplog.at_level(logging.WARNING):
        exit_code = main(["--pr", "1", "--export-agent-sessions", "--export-comments"])

    assert exit_code == 0
    assert set(calls) == {"sessions", "comments"}
    assert "sessions boom" in caplog.text


@pytest.mark.parametrize("code", ["unsupported_host", "no_copilot_access", "no_sessions_endpoint"])
def test_main_warns_when_agent_sessions_mode_is_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, code: str
) -> None:
    with caplog.at_level(logging.INFO):
        exit_code = _run_sessions_mode(
            monkeypatch, lambda c, g: _sessions_result(mode_skip_reason_code=code)
        )

    assert exit_code == 0
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert code in warnings[0].getMessage()


def test_main_logs_empty_agent_session_list_at_info(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        _run_sessions_mode(monkeypatch, lambda c, g: _sessions_result())

    assert "No Copilot agent sessions were found for PR #1." in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_main_warns_only_for_actionable_agent_session_skips(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    result = _sessions_result(
        exported_sessions=1,
        skipped_sessions=3,
        skipped_session_reasons={"log_unavailable": 2, "invalid_session_id": 1},
    )

    with caplog.at_level(logging.INFO):
        _run_sessions_mode(monkeypatch, lambda c, g: result)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert warnings == ["2 agent session(s) could not be downloaded."]
    assert any("1 agent session(s) have an id" in message for message in infos)
