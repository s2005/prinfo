# P4 - Handle pull requests with more than 250 commits

`export_pr_commit_log` in `src/prinfo/exporter.py:381` delegates to `GhCli.list_pr_commits`, which pages `repos/<owner>/<repo>/pulls/<n>/commits`; that endpoint returns at most 250 commits even when pagination is requested, so a PR with more commits yields a `commit-log.json` that silently reports `commit_count: 250` and omits the rest of the history, and the reviewer asks for either the general commits endpoint to fetch the remainder or an explicit failure when the limit is hit.
