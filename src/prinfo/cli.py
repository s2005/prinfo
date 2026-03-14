from __future__ import annotations

import argparse
import logging
from typing import Sequence

from prinfo import __version__
from prinfo.config import ConfigurationError, resolve_config
from prinfo.exporter import ExportError, export_pr_check_logs
from prinfo.gh import GhCli, GhCliError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prinfo",
        description="Export GitHub pull request check logs into a local folder using gh CLI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument("--pr", type=int, help="Pull request number.")
    parser.add_argument("--repo", help="Repository in OWNER/REPO or HOST/OWNER/REPO format.")
    parser.add_argument(
        "--output-dir",
        help="Directory where exported log files and the manifest will be written.",
    )
    parser.add_argument(
        "--env-file",
        help="Optional env file containing PRINFO_* settings, for example .env or some.env.",
    )
    parser.add_argument("--gh-host", help="GitHub host to target. Defaults to github.com.")
    parser.add_argument("--gh-token", help="GitHub token used by gh for this run.")
    parser.add_argument(
        "--gh-config-dir",
        help="Path to a gh configuration directory for a specific authenticated account.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Application log level.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = resolve_config(args)
        configure_logging(config.log_level)
        gh = GhCli(
            gh_host=config.gh_host,
            gh_token=config.gh_token,
            gh_config_dir=str(config.gh_config_dir) if config.gh_config_dir else None,
        )
        result = export_pr_check_logs(config, gh)
    except (ConfigurationError, ExportError, GhCliError, OSError) as exc:
        logging.getLogger("prinfo").error("%s", exc)
        return 1

    logging.getLogger("prinfo").info(
        "Exported %s check log(s) for PR #%s in %s to %s",
        result.exported_logs,
        result.pr_number,
        result.repo,
        result.output_dir,
    )
    if result.skipped_checks:
        logging.getLogger("prinfo").warning("Skipped %s unsupported check(s).", result.skipped_checks)
    return 0


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
