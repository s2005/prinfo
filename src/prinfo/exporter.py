from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from prinfo.config import AppConfig
from prinfo.gh import CheckRun, GhCli, GhCliError, parse_repo_ref

LOGGER = logging.getLogger(__name__)
FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ExportError(RuntimeError):
    """Raised when PR log export cannot complete."""


@dataclass(frozen=True)
class ExportResult:
    repo: str
    pr_number: int
    output_dir: Path
    manifest_path: Path
    exported_logs: int
    skipped_checks: int


def export_pr_check_logs(config: AppConfig, gh: GhCli) -> ExportResult:
    gh.ensure_available()

    repo_name = config.repo or gh.detect_repo()
    repo_ref = parse_repo_ref(repo_name, config.gh_host)
    checks = gh.list_pr_checks(repo_ref.full_name, config.pr_number)
    if not checks:
        raise ExportError(f"No checks were found for PR #{config.pr_number} in {repo_ref.full_name}.")

    config.output_dir.mkdir(parents=True, exist_ok=True)

    exported: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for index, check in enumerate(checks, start=1):
        if check.job_id is None:
            LOGGER.warning("Skipping check without downloadable job log: %s", check.name)
            skipped.append(_skipped_record(check, "check is not a GitHub Actions job"))
            continue

        LOGGER.info("Downloading log for check '%s' (job %s)", check.name, check.job_id)
        try:
            log_text = gh.download_job_log(repo_ref, check.job_id)
        except GhCliError as exc:
            if not _is_missing_log_error(exc):
                raise
            LOGGER.warning("Skipping check without published job log: %s", check.name)
            skipped.append(_skipped_record(check, str(exc)))
            continue
        log_file = config.output_dir / build_log_filename(index, check)
        log_file.write_text(log_text, encoding="utf-8")
        exported.append(
            {
                "check": asdict(check),
                "path": str(log_file.name),
                "bytes": log_file.stat().st_size,
            }
        )

    if not exported:
        raise ExportError(
            f"PR #{config.pr_number} in {repo_ref.full_name} has checks, but none exposed downloadable job logs."
        )

    manifest_path = config.output_dir / "manifest.json"
    manifest = {
        "repo": repo_ref.full_name,
        "pr_number": config.pr_number,
        "exported": exported,
        "skipped": skipped,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return ExportResult(
        repo=repo_ref.full_name,
        pr_number=config.pr_number,
        output_dir=config.output_dir,
        manifest_path=manifest_path,
        exported_logs=len(exported),
        skipped_checks=len(skipped),
    )


def build_log_filename(index: int, check: CheckRun) -> str:
    workflow = slugify(check.workflow_name or "workflow")
    check_name = slugify(check.name)
    suffix = f"job-{check.job_id}" if check.job_id is not None else "no-job"
    return f"{index:02d}-{workflow}-{check_name}-{suffix}.log"


def slugify(value: str) -> str:
    sanitized = FILENAME_SANITIZE_RE.sub("-", value.strip()).strip("-")
    return sanitized.lower() or "check"


def _skipped_record(check: CheckRun, reason: str) -> dict[str, object]:
    return {
        "check": asdict(check),
        "reason": reason,
    }


def _is_missing_log_error(error: GhCliError) -> bool:
    message = str(error)
    return "HTTP 404" in message or "Not Found" in message
