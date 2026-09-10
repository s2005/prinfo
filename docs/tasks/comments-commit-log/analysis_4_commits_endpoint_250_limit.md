# Analysis 4 - Handle pull requests with more than 250 commits

## Decision: Rejected - out of scope for this task, recorded as a follow-up

The 250-commit cap is real, but it is not introduced or worsened by this branch. `GhCli.list_pr_commits` and its use of `repos/<owner>/<repo>/pulls/<n>/commits` arrived in `cbf07b8`, the merge base of this branch, and `main` already writes `"commit_count": len(commits)` into `commits-manifest.json` from that same capped call. REQ-4 requires `--export-commit-log` to reuse the commit list the file export already fetches, so the new mode inherits the existing fetch rather than adding a second, differently-bounded one; the truncation therefore behaves on `commit-log.json` exactly as it already behaves on `commits-manifest.json`. Fixing it means changing `list_pr_commits` - a second endpoint, or a new explicit failure - which changes what `--export-commit-files` does today for every user with a large PR.

**Why:** The scope rule for this repository is that a change fixes the defect its ticket describes and nothing else, and that the test is whether the requested change makes the existing weakness measurably worse. It does not: the same call, the same cap and the same silent count already ship on `main`. The improvement is separable, it is a visible behaviour change for an existing mode, and no requirement or acceptance criterion in the PRD covers commit histories beyond 250, so it needs its own ticket where the endpoint choice and the fail-versus-truncate decision can be described, approved and tested on their own terms. Recorded under Follow-Ups Found in `progress.md`.

**Commit:** d1773aa - docs(prinfo): record the 250-commit review finding as a follow-up
