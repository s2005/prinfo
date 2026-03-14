import pytest

from prinfo import __version__
from prinfo.cli import build_parser, main


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
            "skip_check_logs": True,
        },
    )()

    def fake_resolve_config(args):
        return config

    def fake_export_pr_check_logs(config_arg, gh_arg):
        export_calls.append("logs")
        raise AssertionError("check log export should not run")

    def fake_export_pr_commit_files(config_arg, gh_arg):
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
