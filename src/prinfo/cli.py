from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Callable, Sequence

from prinfo import __version__
from prinfo.config import ConfigurationError, resolve_config
from prinfo.exporter import (
    ACTIONABLE_COMMIT_SKIP_REASONS,
    CommentExportResult,
    CommitExportResult,
    CommitLogExportResult,
    ExportError,
    ExportResult,
    PrCommitCache,
    export_pr_check_logs,
    export_pr_comments,
    export_pr_commit_files,
    export_pr_commit_log,
)
from prinfo.gh import GhCli, GhCliError


@dataclass(frozen=True)
class _ModeRun:
    name: str
    result: object | None
    error: ExportError | GhCliError | OSError | None


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
        "--export-comments",
        action="store_true",
        help=(
            "Export PR discussion, review comments and review verdicts to comments.json and "
            "comments.md."
        ),
    )
    parser.add_argument(
        "--export-commit-log",
        action="store_true",
        help=(
            "Export PR commit metadata to commit-log.json without downloading any changed files."
        ),
    )
    parser.add_argument(
        "--skip-check-logs",
        action="store_true",
        help=(
            "Skip PR check-log export. Use with --export-commit-files, --export-comments or "
            "--export-commit-log."
        ),
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
        commits_cache = PrCommitCache()
        modes: list[tuple[str, Callable[[], object]]] = []
        if not config.skip_check_logs:
            modes.append(("check logs", lambda: export_pr_check_logs(config, gh)))
        if config.export_comments:
            modes.append(("comments", lambda: export_pr_comments(config, gh)))
        if config.export_commit_files:
            modes.append(
                ("commit files", lambda: export_pr_commit_files(config, gh, commits_cache))
            )
        if config.export_commit_log:
            modes.append(
                ("commit log", lambda: export_pr_commit_log(config, gh, commits_cache))
            )

        runs: list[_ModeRun] = []
        for name, run_mode in modes:
            try:
                result = run_mode()
            except (ExportError, GhCliError, OSError) as exc:
                runs.append(_ModeRun(name=name, result=None, error=exc))
            else:
                runs.append(_ModeRun(name=name, result=result, error=None))

        if not any(run.result is not None for run in runs):
            first_error = next((run.error for run in runs if run.error is not None), None)
            if first_error is not None:
                raise first_error
            raise ExportError("No PR data was exported.")
    except (ConfigurationError, ExportError, GhCliError, OSError) as exc:
        logging.getLogger("prinfo").error("%s", exc)
        return 1

    _log_mode_summaries(runs)

    return 0


def _log_mode_summaries(runs: list[_ModeRun]) -> None:
    logger = logging.getLogger("prinfo")
    for run in runs:
        result = run.result
        if isinstance(result, ExportResult):
            logger.info(
                "Exported %s check log(s) for PR #%s in %s to %s",
                result.exported_logs,
                result.pr_number,
                result.repo,
                result.output_dir,
            )
            if result.manifest_only_logs:
                logger.info(
                    "Recorded %s empty check log(s) in the manifest without writing files.",
                    result.manifest_only_logs,
                )
            if result.skipped_checks:
                logger.warning("Skipped %s check(s).", result.skipped_checks)
        elif isinstance(result, CommentExportResult):
            logger.info(
                "Exported %s issue comment(s), %s review comment(s) and %s review(s) "
                "(%s review thread(s)) for PR #%s in %s to %s",
                result.issue_comment_count,
                result.review_comment_count,
                result.review_count,
                result.review_thread_count,
                result.pr_number,
                result.repo,
                result.output_dir,
            )
            if result.skipped_sources:
                logger.warning(
                    "Skipped %s comment source(s).",
                    result.skipped_sources,
                )
        elif isinstance(result, CommitExportResult):
            logger.info(
                "Exported %s file snapshot(s) across %s commit(s) for PR #%s in %s to %s",
                result.exported_files,
                result.commit_count,
                result.pr_number,
                result.repo,
                result.output_dir,
            )
            if result.skipped_files:
                actionable = sum(
                    count
                    for reason_code, count in result.skipped_file_reasons.items()
                    if reason_code in ACTIONABLE_COMMIT_SKIP_REASONS
                )
                benign = result.skipped_files - actionable
                if actionable:
                    logger.warning(
                        "%s commit file(s) could not be downloaded.",
                        actionable,
                    )
                if benign:
                    logger.info(
                        "%s commit file(s) cannot be exported (removed in the commit, "
                        "or absent from the commit payload).",
                        benign,
                    )
        elif isinstance(result, CommitLogExportResult):
            logger.info(
                "Exported commit log for %s commit(s) for PR #%s in %s to %s",
                result.commit_count,
                result.pr_number,
                result.repo,
                result.output_dir,
            )
        elif run.error is not None:
            if run.name == "check logs":
                logger.warning("Check log export was skipped: %s", run.error)
            elif run.name == "commit files":
                logger.warning("Commit file export failed: %s", run.error)
            else:
                logger.warning("%s export failed: %s", run.name, run.error)


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
