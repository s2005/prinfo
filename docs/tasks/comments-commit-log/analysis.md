# Analysis: Export PR Comments and Commit Log

## Goal

Give `prinfo` two new export modes: one that saves a pull request's whole review discussion (REQ-1, REQ-2, REQ-3, REQ-7) and one that saves its commit history without downloading file blobs (REQ-4), both wired into the existing config, CLI and failure-isolation conventions (REQ-5, REQ-6) and documented (REQ-8).

## Current Behavior

### GitHub access

`GhCli` (`src/prinfo/gh.py:76`) shells out to `gh` through an injectable `runner`, which is what makes the whole client testable without a network. It exposes exactly five calls:

| Method | Transport | Line |
| ------ | --------- | ---- |
| `list_pr_checks` | `gh pr view --json statusCheckRollup` | `src/prinfo/gh.py:105` |
| `list_pr_commits` | `gh api` paginated over `pulls/<n>/commits` | `src/prinfo/gh.py:131` |
| `get_commit_details` | `gh api` paginated over `commits/<sha>` | `src/prinfo/gh.py:141` |
| `download_job_log` | `gh api` text | `src/prinfo/gh.py:164` |
| `download_commit_file` | `gh api` raw bytes | `src/prinfo/gh.py:175` |

None of them touches comments. `_run_paginated_json` (`src/prinfo/gh.py:188`) does the work the new REST calls need: it runs `gh api --hostname <host> --paginate --slurp -H "Accept: application/vnd.github+json" <endpoint>`, asserts the outer value is a list, and flattens pages that are objects or arrays, raising `GhCliError` with the endpoint named on anything else.

Records are frozen dataclasses (`CheckRun`, `PrCommit`, `CommitFile`, `CommitDetails`, `RepoRef`) and are serialized through `dataclasses.asdict` in the exporter, so a new dataclass automatically serializes correctly.

### Export

`export_pr_check_logs` (`src/prinfo/exporter.py:40`) and `export_pr_commit_files` (`src/prinfo/exporter.py:148`) each create the output directory, loop, and write a manifest. Both keep an `exported` list and a `skipped` list, and `skipped` entries carry a human `reason` plus a machine `reason_code` (`_skipped_commit_file_record`). Neither aborts on a single item failing: a `GhCliError` downloading one file is caught, logged at warning, and recorded (`src/prinfo/exporter.py:257`).

`export_pr_commit_files` calls `gh.list_pr_commits` once (`src/prinfo/exporter.py:155`), then `gh.get_commit_details` per commit, then `download_commit_file` per changed file. The `PrCommit` record is already written twice - into `commits/<sha>/_commit.json` and into each `commits-manifest.json` record - which is exactly the data `--export-commit-log` needs (REQ-4).

### Config and CLI

`resolve_config` (`src/prinfo/config.py:31`) merges CLI args over env-file values. Booleans go through `_resolve_bool`, where a set CLI flag wins outright and an env string is truthy for `1`, `true`, `yes`, `on`. One cross-field guard exists:

```python
if skip_check_logs and not export_commit_files:
    raise ConfigurationError(...)
```

`main` (`src/prinfo/cli.py:66`) runs each mode in its own `try`, keeps `log_result`/`commit_result` and `log_error`/`commit_error`, raises only when both results are `None`, and logs a per-mode summary at the end.

### Tests

872 lines across four files. `tests/test_gh.py` drives `GhCli` with a fake `runner` returning `subprocess.CompletedProcess`; `tests/test_exporter.py` uses fake gh objects; `tests/test_cli.py` monkeypatches the exporter functions and hands `main` a `type("Config", (), {...})` stand-in. Every new unit of work here has an established test shape to copy.

## Feasibility

Straightforward for REQ-1 through REQ-6 and REQ-8. The three REST comment endpoints have the same paginated JSON-array shape as `pulls/<n>/commits`, so `_run_paginated_json` serves them unchanged; the new work is three parser functions and three dataclasses. `--export-commit-log` is a strict subset of an existing code path.

REQ-7 is the only part that leaves the established groove. `reviewThreads.isResolved` has no REST equivalent, so it needs `gh api graphql`, which takes a different argument shape (`-f query=...`, `-F number=...`) and paginates differently: `gh api graphql --paginate` requires the query to declare an `$endCursor` variable and select `pageInfo { hasNextPage endCursor }`, and it emits one JSON document per page. `_run_paginated_json` cannot be reused as is because it builds a REST argument vector; a sibling `_run_graphql_paginated` is needed, sharing `_run_json_value` beneath it.

The one thing to get right is the join. GraphQL node ids (`PRRT_...`) are not the REST comment ids, so the thread query must select `comments { nodes { databaseId } }` - `databaseId` is the REST `id`. Without that field the mapping in REQ-7 cannot be built at all.

## Approach

### Recommended: three REST parsers plus one GraphQL sibling, one new exporter module section

Add the dataclasses and five client methods to `gh.py`, then add `export_pr_comments` and `export_pr_commit_log` to `exporter.py` beside the two existing exporters, and widen the orchestration in `main`.

| Advantages | Disadvantages |
| ---------- | ------------- |
| Every new REST call reuses `_run_paginated_json`, so pagination and page-flattening stay tested in one place | `exporter.py` grows past 400 lines and starts to be a candidate for splitting |
| New exporters are peers of the existing two, so the manifest, skipped-record and logging conventions carry over unchanged | GraphQL introduces a second `gh api` argument shape in the client |
| `main` already isolates errors per mode; extending it from two modes to four is a mechanical widening | `main` grows to four result variables and four error variables |
| Test doubles for all of it already exist in the suite | -- |

### Alternative: a separate `comments.py` module

Put the comment export in its own module rather than in `exporter.py`.

| Advantages | Disadvantages |
| ---------- | ------------- |
| Keeps `exporter.py` from growing | The shared helpers `_relative_manifest_path`, `_sanitize_repo_relative_path` and the skipped-record builders live in `exporter.py` and would need importing across modules or duplicating |
| Cleaner home for the Markdown renderer | Splits a convention that is currently in one file, for a task that does not otherwise require it |

Rejected: the shared helpers pull the split apart, and moving them is a refactor this task did not ask for.

### Alternative: skip GraphQL, defer resolved state

Considered and put to the user as Q2. The user chose to include it, so it is REQ-7, not a follow-up.

## Implementation Notes

- **GraphQL query shape (REQ-7).** The query needs `$owner`, `$name`, `$number` and `$endCursor`, and must select `pageInfo { hasNextPage endCursor }` for `gh api graphql --paginate` to advance. Select `id`, `isResolved`, `isOutdated` and `comments(first: 100) { nodes { databaseId } }` per thread. Pass variables with `-F owner=... -F name=... -F number=<int>` (`-F` types numbers; `-f` would send the PR number as a string and the query would reject it against `Int!`).
- **The join key (REQ-7).** `comments.nodes[].databaseId` is the REST `id` on `pulls/<n>/comments` entries. Build `dict[int, ReviewThread]` from it once, then attach on the way into the manifest. A thread whose comments page overflows 100 entries loses the tail of the mapping; those comments end at `is_resolved=None`, which is the documented "no thread matched" value, so nothing raises.
- **Host handling.** `parse_repo_ref` already splits `HOST/OWNER/REPO`, and every paginated call passes `--hostname repo_ref.host`. The GraphQL call must do the same or it silently hits github.com for a GitHub Enterprise repo.
- **Shared commit fetch (REQ-4).** Rather than have `export_pr_commit_log` call `list_pr_commits` itself, give both exporters an optional `commits` parameter and let `main` fetch once when both flags are set. The cleaner variant given the current structure: extract a small `_fetch_pr_commits(config, gh, cache)` helper in `exporter.py` holding the list, and have both exporters take it. Whatever the shape, AC-4 asserts the call count through a counting fake, so the design is pinned by the test, not by prose.
- **Markdown rendering (REQ-3).** Sort key is the timestamp string; ISO-8601 UTC strings from the GitHub API sort correctly as strings, so no `datetime` parsing is needed. `None` sorts last via a `(timestamp is None, timestamp or "")` tuple key. Bodies go in verbatim; a body containing its own `##` heading is acceptable, since faithfulness beats rendering purity here and REQ-2 already forbids editing content.
- **Encoding (project rule).** Every write uses `encoding="utf-8"`, matching the existing manifest writes. Comment bodies routinely contain non-ASCII, and a default-encoding write would raise `UnicodeEncodeError` on Windows.
- **No emoji or Unicode in code** per the project rules; that applies to the Markdown template strings in the renderer too, not just to comments.
- **Version bump.** `__version__` in `src/prinfo/__init__.py` goes to `0.4.0`: new flags are an additive feature, and `--version` is asserted against it in `tests/test_cli.py:7`.

## Risks

| Risk | Mitigation |
| ---- | ---------- |
| `gh api graphql --paginate` behaves differently from the REST `--paginate --slurp` path already in use, and the parser mis-handles multi-page output | Phase 2 writes `_run_graphql_paginated` with its own tests over a fake runner returning two pages, so the shape is pinned before the exporter depends on it. If `--slurp` is unavailable for graphql on the installed `gh`, parse the concatenated documents instead - the test decides which |
| The thread-to-comment join silently produces `is_resolved=None` everywhere because `databaseId` was not selected | AC-9 asserts a matched comment carries `is_resolved` and an unmatched one carries `None`; an all-`None` result fails that test |
| Four export modes make `main` a tangle of result and error variables | Collect the per-mode results into a list of small records and loop over it for reporting rather than adding two more parallel variables |
| `--export-comments` on a large PR issues four calls and pages heavily | Pagination is already the tool's normal behaviour for commits; no new limit is introduced, and `--log-level DEBUG` shows the call sequence |
| A repo with review threads disabled or a GraphQL scope missing from the token fails REQ-7 on every run | REQ-6 puts the failure in `skipped_sources` and leaves the REST export intact, so the mode degrades rather than breaks (AC-10) |
| Comment bodies contain text that looks like a path and trips the Markdown linter or the no-absolute-paths rule | Bodies are content, not generated prose; the rule applies to the task and doc files this task writes. `comments.md` is a generated artifact under `artifacts/`, which is not linted |

## Test Strategy

| Level | File | What it covers |
| ----- | ---- | -------------- |
| Unit - client | `tests/test_gh.py` | Each new parser over a fake `runner` payload (AC-1); malformed entry raises `GhCliError` naming the endpoint; GraphQL paginated payload parses into `ReviewThread` records (AC-9, first half); `--hostname` reaches the argument vector for an enterprise host |
| Unit - config | `tests/test_config.py` | Both new flags resolve from CLI and from env with CLI winning (AC-5); the relaxed guard accepts each mode alone and rejects none-set with all three named (AC-6) |
| Unit - CLI | `tests/test_cli.py` | Parser accepts both flags (AC-5); `main` returns 0 on partial failure and 1 on total failure (AC-8); `--version` still matches the bumped `__version__` |
| Unit - exporter | `tests/test_exporter.py` | `comments.json` contents and per-source counts (AC-2); `comments.md` ordering including the untimestamped entry (AC-3); `commit-log.json` alone and combined with the file export, with a counting fake asserting one commits call (AC-4); one-source failure recorded and total failure raising (AC-7); thread mapping onto review comments (AC-9); GraphQL failure isolated (AC-10) |
| Gate | -- | `uv run ruff check .`, `uv run pytest`, `markdownlint-cli2` (AC-11, AC-12) |

No integration test against a live repository is added: the whole suite runs against injected fakes today, and adding a network-dependent test would break the CI matrix that currently runs a CLI help smoke test on Windows, Linux and macOS.
