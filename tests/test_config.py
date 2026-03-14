from argparse import Namespace
from pathlib import Path

import pytest

from prinfo.config import ConfigurationError, resolve_config


def test_resolve_config_prefers_cli_values_over_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "some.env"
    env_file.write_text(
        "\n".join(
            [
                "PRINFO_PR=100",
                "PRINFO_REPO=env/example",
                "PRINFO_OUTPUT_DIR=env-output",
                "PRINFO_GH_HOST=git.example.com",
                "PRINFO_GH_TOKEN=env-token",
                "PRINFO_GH_CONFIG_DIR=env-gh",
                "PRINFO_EXPORT_COMMIT_FILES=true",
                "PRINFO_SKIP_CHECK_LOGS=true",
                "PRINFO_LOG_LEVEL=ERROR",
            ]
        ),
        encoding="utf-8",
    )
    args = Namespace(
        pr=200,
        repo="cli/override",
        output_dir="cli-output",
        skip_empty_logs=True,
        export_commit_files=False,
        skip_check_logs=False,
        env_file=str(env_file),
        gh_host="github.com",
        gh_token="cli-token",
        gh_config_dir="cli-gh",
        log_level="DEBUG",
    )

    config = resolve_config(args)

    assert config.pr_number == 200
    assert config.repo == "cli/override"
    assert config.output_dir == Path("cli-output")
    assert config.skip_empty_logs is True
    assert config.export_commit_files is True
    assert config.skip_check_logs is True
    assert config.gh_host == "github.com"
    assert config.gh_token == "cli-token"
    assert config.gh_config_dir == Path("cli-gh")
    assert config.log_level == "DEBUG"


def test_resolve_config_uses_defaults_when_optional_values_missing() -> None:
    args = Namespace(
        pr=15,
        repo=None,
        output_dir=None,
        skip_empty_logs=False,
        export_commit_files=False,
        skip_check_logs=False,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    config = resolve_config(args, environ={})

    assert config.pr_number == 15
    assert config.repo is None
    assert config.output_dir == Path("artifacts") / "pr-15"
    assert config.skip_empty_logs is False
    assert config.export_commit_files is False
    assert config.skip_check_logs is False
    assert config.gh_host == "github.com"
    assert config.gh_token is None
    assert config.gh_config_dir is None
    assert config.log_level == "INFO"


def test_resolve_config_preserves_absolute_windows_output_dir() -> None:
    args = Namespace(
        pr=15,
        repo=None,
        output_dir=r"C:\path\to\output",
        skip_empty_logs=False,
        export_commit_files=False,
        skip_check_logs=False,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    config = resolve_config(args, environ={})

    assert config.output_dir == Path(r"C:\path\to\output")


def test_resolve_config_preserves_relative_backslash_output_dir() -> None:
    args = Namespace(
        pr=15,
        repo=None,
        output_dir=r"relative\path",
        skip_empty_logs=False,
        export_commit_files=False,
        skip_check_logs=False,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    config = resolve_config(args, environ={})

    assert config.output_dir == Path(r"relative\path")


def test_resolve_config_requires_pr_number() -> None:
    args = Namespace(
        pr=None,
        repo=None,
        output_dir=None,
        skip_empty_logs=False,
        export_commit_files=False,
        skip_check_logs=False,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    with pytest.raises(ConfigurationError):
        resolve_config(args, environ={})


def test_resolve_config_prefers_cli_commit_export_flag_over_env_false(tmp_path: Path) -> None:
    env_file = tmp_path / "some.env"
    env_file.write_text(
        "\n".join(
            [
                "PRINFO_PR=100",
                "PRINFO_EXPORT_COMMIT_FILES=false",
            ]
        ),
        encoding="utf-8",
    )
    args = Namespace(
        pr=None,
        repo=None,
        output_dir=None,
        skip_empty_logs=False,
        export_commit_files=True,
        skip_check_logs=False,
        env_file=str(env_file),
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    config = resolve_config(args)

    assert config.export_commit_files is True


def test_resolve_config_requires_commit_export_when_skipping_check_logs() -> None:
    args = Namespace(
        pr=15,
        repo=None,
        output_dir=None,
        skip_empty_logs=False,
        export_commit_files=False,
        skip_check_logs=True,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    with pytest.raises(ConfigurationError, match="--skip-check-logs requires --export-commit-files"):
        resolve_config(args, environ={})
