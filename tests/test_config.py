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
                "PRINFO_LOG_LEVEL=ERROR",
            ]
        ),
        encoding="utf-8",
    )
    args = Namespace(
        pr=200,
        repo="cli/override",
        output_dir="cli-output",
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
    assert config.gh_host == "github.com"
    assert config.gh_token == "cli-token"
    assert config.gh_config_dir == Path("cli-gh")
    assert config.log_level == "DEBUG"


def test_resolve_config_uses_defaults_when_optional_values_missing() -> None:
    args = Namespace(
        pr=15,
        repo=None,
        output_dir=None,
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
    assert config.gh_host == "github.com"
    assert config.gh_token is None
    assert config.gh_config_dir is None
    assert config.log_level == "INFO"


def test_resolve_config_requires_pr_number() -> None:
    args = Namespace(
        pr=None,
        repo=None,
        output_dir=None,
        env_file=None,
        gh_host=None,
        gh_token=None,
        gh_config_dir=None,
        log_level=None,
    )

    with pytest.raises(ConfigurationError):
        resolve_config(args, environ={})
