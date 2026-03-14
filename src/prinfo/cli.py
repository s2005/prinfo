from __future__ import annotations

import argparse
import logging
from typing import Sequence

from prinfo import __version__
from prinfo.config import ConfigurationError, resolve_config
from prinfo.exporter import (
    ExportError,
    export_pr_check_logs,
    export_pr_commit_files,
)
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
        "--skip-empty-logs",
        action="store_true",
        help="Record empty logs in the manifest without writing zero-byte .log files.",
    )
    parser.add_argument(
        "--export-commit-files",
        action="store_true",
        help="Export PR commits into commits/<sha>/ folders with the changed files saved per commit.",
    )
    parser.add_argument(
        "--skip-check-logs",
        action="store_true",
        help="Skip PR check-log export. Use with --export-commit-files for commit-only exports.",
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
        log_result = None
        commit_result = None
        log_error = None
        commit_error = None

        if not config.skip_check_logs:
            try:
                log_result = export_pr_check_logs(config, gh)
            except ExportError as exc:
                log_error = exc
                if not config.export_commit_files:
                    raise

        if config.export_commit_files:
            try:
                commit_result = export_pr_commit_files(config, gh)
            except ExportError as exc:
                commit_error = exc

        if log_result is None and commit_result is None:
            if commit_error is not None:
                raise commit_error
            if log_error is not None:
                raise log_error
            raise ExportError("No PR data was exported.")
    except (ConfigurationError, ExportError, GhCliError, OSError) as exc:
        logging.getLogger("prinfo").error("%s", exc)
        return 1

    if log_result is not None:
        logging.getLogger("prinfo").info(
            "Exported %s check log(s) for PR #%s in %s to %s",
            log_result.exported_logs,
            log_result.pr_number,
            log_result.repo,
            log_result.output_dir,
        )
        if log_result.manifest_only_logs:
            logging.getLogger("prinfo").info(
                "Recorded %s empty check log(s) in the manifest without writing files.",
                log_result.manifest_only_logs,
            )
        if log_result.skipped_checks:
            logging.getLogger("prinfo").warning("Skipped %s check(s).", log_result.skipped_checks)
    elif log_error is not None:
        logging.getLogger("prinfo").warning("Check log export was skipped: %s", log_error)

    if commit_result is not None:
        logging.getLogger("prinfo").info(
            "Exported %s file snapshot(s) across %s commit(s) for PR #%s in %s to %s",
            commit_result.exported_files,
            commit_result.commit_count,
            commit_result.pr_number,
            commit_result.repo,
            commit_result.output_dir,
        )
        if commit_result.skipped_files:
            logging.getLogger("prinfo").warning(
                "Skipped %s commit file(s).",
                commit_result.skipped_files,
            )
    elif commit_error is not None:
        logging.getLogger("prinfo").warning("Commit file export failed: %s", commit_error)

    return 0


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
