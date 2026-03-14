# Implementation Plan

## Proposed changes

1. Normalize output directory values in configuration

- Add a small helper in `src/prinfo/config.py` that converts configured path strings into `Path` objects without altering whether they are absolute or relative.
- Use that helper for both `output_dir` and `gh_config_dir`.
- Add tests covering:

  - absolute Windows path input
  - relative backslash-separated path input
  - existing default behavior

1. Make `gh` subprocess handling byte-safe

- Change `GhCli._run_text()` to capture bytes instead of using `text=True`.
- Add a dedicated decode helper that:

  - accepts `bytes | None`
  - strips UTF BOM safely
  - prefers UTF-8
  - falls back in a controlled way for non-UTF-8 output
  - raises `GhCliError` with a clear message if decoding cannot produce valid text
- Keep stderr decoding on the same path so command failures remain actionable.
- Add tests for:

  - invalid UTF-8 bytes handled via fallback
  - explicit decode failure path if fallback cannot decode
  - command failure message formatting

1. Extend exported manifest entries for empty logs

- In `src/prinfo/exporter.py`, enrich each exported record with selected check metadata that is directly useful to users:

  - `status`
  - `conclusion`
  - `has_log_content`
  - `empty_log_reason`
- Set `empty_log_reason` only when the file is empty.
- For skipped jobs with no downloadable log endpoint, keep them in `skipped` but add a structured reason field that distinguishes:

  - unsupported non-Actions checks
  - missing downloadable log content

1. Improve diagnostics

- Add informational or warning logs for:

  - exported empty logs from skipped jobs
  - checks that expose a job ID but do not expose log content
  - decode fallback usage in `gh.py`
- Keep messages short and actionable, with job/check names where available.

1. Verify with targeted tests

- Run the focused test modules first:

  - `tests/test_config.py`
  - `tests/test_gh.py`
  - `tests/test_exporter.py`
- Run the full test suite after the targeted fixes pass.

## Expected minimal code impact

- `src/prinfo/config.py`
- `src/prinfo/gh.py`
- `src/prinfo/exporter.py`
- `tests/test_config.py`
- `tests/test_gh.py`
- `tests/test_exporter.py`

## Open implementation choices

- For Windows-path regression coverage on a non-Windows test runner, prefer `PureWindowsPath`-style expectations or string-preservation assertions so the test is stable across platforms.
- For decode fallback, the most pragmatic option is:

  - first `utf-8-sig`
  - then `utf-8` strict
  - then a single-byte fallback such as `cp1252` or `latin-1`

The final fallback choice should be documented in code comments or tests because it affects how mixed-byte logs are rendered.
