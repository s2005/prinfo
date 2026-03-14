from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values

DEFAULT_ENV_FILE = ".env"


class ConfigurationError(ValueError):
    """Raised when CLI and env configuration cannot be resolved."""


@dataclass(frozen=True)
class AppConfig:
    pr_number: int
    repo: str | None
    output_dir: Path
    env_file: Path | None
    gh_host: str
    gh_token: str | None
    gh_config_dir: Path | None
    log_level: str


def resolve_config(args, environ: Mapping[str, str] | None = None) -> AppConfig:
    env_source = dict(environ or os.environ)
    env_file = _resolve_env_file(args.env_file, env_source)
    env_values = _load_env_values(env_file)

    pr_number = _resolve_int(args.pr, env_values.get("PRINFO_PR"), "PR number")
    repo = _resolve_str(args.repo, env_values.get("PRINFO_REPO"))
    output_dir_value = _resolve_str(args.output_dir, env_values.get("PRINFO_OUTPUT_DIR"))
    output_dir = Path(output_dir_value) if output_dir_value else Path("artifacts") / f"pr-{pr_number}"
    gh_host = _resolve_str(args.gh_host, env_values.get("PRINFO_GH_HOST")) or "github.com"
    gh_token = _resolve_str(args.gh_token, env_values.get("PRINFO_GH_TOKEN"))
    gh_config_dir_value = _resolve_str(args.gh_config_dir, env_values.get("PRINFO_GH_CONFIG_DIR"))
    gh_config_dir = Path(gh_config_dir_value) if gh_config_dir_value else None
    log_level = (_resolve_str(args.log_level, env_values.get("PRINFO_LOG_LEVEL")) or "INFO").upper()

    return AppConfig(
        pr_number=pr_number,
        repo=repo,
        output_dir=output_dir,
        env_file=env_file,
        gh_host=gh_host,
        gh_token=gh_token,
        gh_config_dir=gh_config_dir,
        log_level=log_level,
    )


def _resolve_env_file(explicit_env_file: str | None, environ: Mapping[str, str]) -> Path | None:
    candidate = explicit_env_file or environ.get("PRINFO_ENV_FILE")
    if candidate:
        env_path = Path(candidate)
        if not env_path.exists():
            raise ConfigurationError(f"Env file does not exist: {env_path}")
        return env_path

    default_path = Path(DEFAULT_ENV_FILE)
    if default_path.exists():
        return default_path

    return None


def _load_env_values(env_file: Path | None) -> dict[str, str]:
    if env_file is None:
        return {}
    raw_values = dotenv_values(env_file)
    return {key: value for key, value in raw_values.items() if value is not None}


def _resolve_int(cli_value: int | None, env_value: str | None, label: str) -> int:
    value = cli_value if cli_value is not None else env_value
    if value is None:
        raise ConfigurationError(f"{label} must be provided via CLI arguments or env file.")

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{label} must be an integer: {value!r}") from exc


def _resolve_str(cli_value: str | None, env_value: str | None) -> str | None:
    if cli_value is not None and cli_value != "":
        return cli_value
    if env_value is not None and env_value != "":
        return env_value
    return None
