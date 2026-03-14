# Analysis

## Scope check against the current codebase

The request is relevant to this project. The affected implementation points are:

- `src/prinfo/config.py` for `--output-dir` parsing and normalization
- `src/prinfo/gh.py` for `gh` subprocess execution and text decoding
- `src/prinfo/exporter.py` for empty-log handling, manifest shape, and diagnostics
- `tests/test_config.py`, `tests/test_gh.py`, and `tests/test_exporter.py` for coverage

## Root causes visible in the current implementation

1. Output directory handling is underspecified
- `resolve_config()` currently does `Path(output_dir_value)` and passes that through unchanged.
- That is acceptable for many cases, but there is no explicit normalization step and no regression test covering absolute Windows paths such as `C:\path\to\output`.
- Because there is no dedicated path helper, the behavior is implicit rather than defended.

2. `gh` subprocess decoding is locale-dependent and fragile
- `GhCli._run_text()` currently calls `subprocess.run(..., capture_output=True, text=True)`.
- With `text=True`, Python decodes stdout/stderr using the process default encoding unless an explicit encoding is supplied.
- On Windows, that can be a legacy code page and can fail on mixed or non-UTF-8 bytes before `prinfo` gets a chance to handle the data.
- The method also returns `completed.stdout` directly, so the contract depends on how `subprocess` populated that field rather than on an explicit tool-level guarantee.

3. Manifest output does not explain empty exported logs
- `export_pr_check_logs()` records only `path` and `bytes` for exported files.
- If `gh` returns an empty string for a valid job log, the file will be written as `0` bytes, but the manifest gives no reason.
- The current skipped-record structure also only stores a free-form `reason`, which makes it hard to distinguish unsupported checks from missing downloadable logs in a structured way.

4. Diagnostics are too generic for empty or missing logs
- The exporter logs warnings for unsupported checks and missing published logs, but it does not log when an exported file is empty.
- There is also no diagnostic path for decode fallback or decode failure because decoding is delegated to `subprocess`.

## Relevance notes

- The request to support absolute Windows paths appears precautionary rather than based on a clearly broken code path in this repository. Current `Path(...)` usage is likely already correct when run natively on Windows, but the project does not test that behavior and does not normalize the value explicitly.
- The subprocess decoding issue is a real gap. The current implementation is not robust on Windows locales that are not UTF-8.
- The empty-log manifest and diagnostics issues are also real gaps. The current code cannot explain why a zero-byte exported file exists.

## Constraints for the fix

- Keep public CLI arguments unchanged.
- Keep exporting intentionally empty logs if `gh` returns empty content for a valid job.
- Do not broaden scope into unrelated refactors.
- Prefer structured metadata additions in the manifest over changing top-level manifest layout drastically.
