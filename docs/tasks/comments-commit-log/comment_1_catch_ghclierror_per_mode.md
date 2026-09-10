# P1 - Catch GitHub errors inside each export mode

The per-mode loop in `src/prinfo/cli.py:130` catches only `ExportError`, so a `GhCliError` raised by an earlier mode - for example `list_pr_checks` failing on a permission or API error inside `export_pr_check_logs` - escapes the loop to the outer handler and returns before the later comment, commit-file or commit-log modes ever run, which breaks the per-mode isolation contract in REQ-6; each mode should catch and record expected `GhCliError` failures, or the exporters should normalize them to `ExportError`.
