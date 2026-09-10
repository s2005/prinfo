# Analysis 2 - Isolate filesystem errors between export modes

## Decision: Valid - fix applied

The per-mode loop in `main` recorded only `ExportError` and `GhCliError`, while every exporter entry point performs its own filesystem work - `config.output_dir.mkdir(...)`, `manifest_path.write_text(...)`, `target_path.write_bytes(...)` - and any `OSError` from those escaped the loop to the outer handler, so a read-only output directory or a `comments.json` that already exists as a directory aborted the run before the later requested modes were reached. The loop now records `OSError` alongside the two export errors, `_ModeRun.error` accepts it, and the "no mode produced a result" path re-raises whichever error came first, so a single-mode run keeps the same exit code and the same logged message it had before.

**Why:** PRD REQ-6 states that each mode records its own error, a failure in one does not prevent the others from running, and the run exits non-zero only when no mode produced a result. AC-8 spells out the exit codes. `OSError` is the third error family an exporter can raise and it was the only one still breaking that contract. Catching it at the loop was chosen over normalizing inside each exporter for the same reason recorded in [Analysis 1](analysis_1_catch_ghclierror_per_mode.md): the isolation contract belongs to `main`, and re-wrapping in four exporters would change the messages those exporters log without making the loop any safer.

**Commit:** 91e3584 - fix(cli): address review feedback for PR #2
