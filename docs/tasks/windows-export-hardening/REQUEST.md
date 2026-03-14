# Windows Export Hardening Request

Please improve the `prinfo` CLI tool based on the following product-level issues.

Context:
- `prinfo` exports pull request check logs using the GitHub CLI.
- We observed several issues during real-world usage on Windows.

Observed issues to address:

1. Windows output path handling
- When `--output-dir` receives an absolute Windows path such as:
  `C:\path\to\output`
  the tool must write files exactly there.
- The tool must not mangle path separators, strip drive letters, or reinterpret the absolute path as a relative folder name.
- Expected behavior:
  - support absolute Windows paths
  - support relative paths
  - support backslash-separated paths safely
  - normalize paths correctly using `pathlib` or equivalent

2. Robust decoding of downloaded log content
- The tool must handle log data that contains bytes not decodable with the platform default encoding.
- The tool must not crash because the OS locale defaults to a legacy code page.
- Expected behavior:
  - capture subprocess output safely
  - avoid fragile locale-dependent decoding
  - decode in a controlled way
  - never return `None` unexpectedly from text-reading helpers
  - if decoding fails, raise a clear tool-specific error instead of a secondary exception

3. Clear handling of zero-byte exported logs
- Some exported log files may legitimately have size `0` when the corresponding job was skipped and emitted no log output.
- This is expected behavior, but it should be clearly represented in the output metadata.
- Expected behavior:
  - keep current export behavior if skipped jobs are intentionally exported
  - make it obvious in the manifest why a file is empty
  - distinguish "empty because skipped" from "empty because export failed"

4. Better user-facing diagnostics
- If an exported job has no log content, the manifest and/or CLI output should explain why.
- If the underlying service exposes a job but there is no downloadable log content, record that clearly.
- Error messages should be specific and actionable.

Your task:
- Investigate the `prinfo` codebase.
- Identify the root causes.
- Implement the smallest robust fix.
- Preserve existing public CLI behavior unless a change is required.
- Use named parameters everywhere.
- Do not suppress lint warnings instead of fixing root causes.
- Avoid Unicode characters in code and test fixtures unless explicitly necessary.

Required improvements:

A. Output directory handling
- Fix path resolution for `--output-dir`
- Correctly support:
  - `C:\path\to\output`
  - `relative\path`
  - `/unix/style/path` where applicable
- Ensure the final write location matches the user-requested directory exactly

B. Safe subprocess text handling
- Review the helper responsible for executing `gh`
- Prefer a byte-safe strategy:
  - capture bytes
  - decode with explicit logic
  - handle BOM if present
  - use a safe fallback strategy when bytes are not valid UTF-8
- Ensure helpers either return valid text or raise a clear exception
- Prevent secondary crashes such as calling string methods on `None`

C. Manifest clarity
- Extend exported manifest entries with enough metadata to explain empty logs
- Examples of acceptable additions:
  - `status`
  - `conclusion`
  - `has_log_content`
  - `empty_log_reason`
- If a job is skipped and the exported file is empty, that should be explicit

D. Logging and diagnostics
- Add clear informational or debug messages for:
  - skipped jobs with empty logs
  - missing downloadable log content
  - decode fallback behavior when relevant
- Messages should help users understand whether behavior is expected or anomalous

Testing requirements:
- Add or update tests for:
  1. absolute Windows output directory handling
  2. subprocess output containing problematic bytes
  3. zero-byte exported logs for skipped jobs with clear manifest metadata
- Prefer extending existing tests if relevant coverage already exists

Implementation guidance:
- Read the relevant files first and understand:
  - CLI/config parsing
  - output directory resolution
  - subprocess execution
  - log download
  - manifest generation
- Make small, targeted changes
- Keep code style consistent with the existing project

Acceptance criteria:
- An absolute Windows path passed to `--output-dir` is used correctly without mangling
- Export does not crash on non-UTF-8 or mixed-byte log content
- No secondary `NoneType` failure occurs in text post-processing
- Zero-byte exported files are clearly explained in the manifest
- Tests cover the fixes and pass

Deliverables:
- Code changes
- Tests
- Short summary of root causes
- Short verification summary
