# Verification Plan: Export Copilot Agent Sessions for a PR

## Purpose

This plan verifies the `--export-agent-sessions` mode: the option and env key, session discovery, the Copilot API client and its token handling, the output files, log parsing, failure handling, documentation and the version bump.

## Pre-Implementation Verification

### Existing Tests Pass

```bash
uv run pytest
```

Expected: all pass.

### Linter Baseline

```bash
uv run ruff check .
```

Expected: clean.

### Version Baseline

```bash
uv run prinfo --version
```

Expected: `prinfo 0.4.0`.

## Post-Implementation Verification

### Per-Phase Verification

#### Phase 1: Option, env key and version bump

Covers REQ-1, REQ-8.

```bash
uv run pytest tests/test_config.py tests/test_cli.py -q
uv run prinfo --version
uv run prinfo --help
```

Expected: tests pass, the version is `prinfo 0.5.0`, and the help text lists `--export-agent-sessions`.

#### Phase 2: Copilot API client and gh helpers

Covers REQ-3.

```bash
uv run pytest tests/test_copilot.py tests/test_gh.py -q
```

Expected: pass, including the host-mapping cases and the sentinel token absent from error text.

#### Phase 3: Session log parser

Covers REQ-5, REQ-4.

```bash
uv run pytest tests/test_session_log.py -q
```

Expected: pass. The fixture yields 2 findings and 1 unparsed event, and the curated metadata excludes the planted identifying keys.

#### Phase 4: Export mode

Covers REQ-2, REQ-4, REQ-6, REQ-3.

```bash
uv run pytest tests/test_exporter.py tests/test_cli.py -q
```

Expected: pass, including ordering, the empty PR, the skip reason codes, per-session skip, all sessions failing, byte-identical `log.sse`, the sentinel-token scan and mode isolation.

#### Phase 5: Documentation and manual check

Covers REQ-7, REQ-2, REQ-3, REQ-5.

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: no errors.

Manual run, from any directory, with output outside the repository. Substitute a PR that has Copilot code review sessions:

```bash
uv run --project <prinfo-repo> prinfo --gh-host <tenant>.ghe.com --repo <tenant>.ghe.com/<owner>/<repo> --pr <n> --export-agent-sessions --skip-check-logs --output-dir <outside-repo-dir>
```

Expected:

- exit code 0;
- `agent-sessions/agent-sessions.json` lists every session, in `created_at` order;
- each session folder holds `session.json`, `log.sse` and `transcript.md`;
- at least one folder holds a non-empty `findings.json`.

Check for the token without printing it:

```bash
TOKEN=$(gh auth token --hostname <tenant>.ghe.com)
[ -n "$TOKEN" ] || { echo "no token read - aborting"; exit 1; }
printf %s "$TOKEN" | grep -rIlf - <outside-repo-dir> && echo "TOKEN FOUND" || echo "token absent"
```

Expected: `token absent`.

Optional: repeat the run against a `github.com` PR that has a Copilot review, to confirm the `api.githubcopilot.com` mapping.

### Linter

```bash
uv run ruff check .
```

Expected: clean.

### Regression Check

```bash
uv run pytest
uv run prinfo --help
```

Expected: all tests pass, and the help text renders.

## Final Acceptance Verification

The feature can be accepted when all items are true:

- [ ] AC-1 - the flag and the env key enable the mode, and `--skip-check-logs --export-agent-sessions` is accepted - verified by: Phase 1 tests
- [ ] AC-2 - two sessions are exported in `created_at` order, and an empty PR yields `sessions: []` - verified by: Phase 4 tests
- [ ] AC-3 - host mapping is correct for `github.com`, `<tenant>.ghe.com` and an Enterprise Server host, and the last makes no HTTP call - verified by: Phase 2 and Phase 4 tests
- [ ] AC-4 - the sentinel token is absent from logs, errors and written files - verified by: Phase 2 and Phase 4 tests, and the manual token check
- [ ] AC-5 - curated `session.json` and manifest, and byte-identical `log.sse` - verified by: Phase 3 and Phase 4 tests
- [ ] AC-6 - transcript order and `findings.json` match the fixture, and no `findings.json` is written without findings - verified by: Phase 3 tests
- [ ] AC-7 - 401, 403 and 404 skip reason codes, per-session skip, all sessions failing raises, and other modes are unaffected - verified by: Phase 4 tests
- [ ] AC-8 - README and the bundled skill document the mode, and markdown lint passes - verified by: Phase 5 lint and review
- [ ] AC-9 - `uv run prinfo --version` prints `prinfo 0.5.0` - verified by: Phase 1 verification
- [ ] AC-10 - the manual run writes the manifest, the session folders and a non-empty `findings.json` - verified by: Phase 5 manual run
