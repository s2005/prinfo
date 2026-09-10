# P2 - Isolate filesystem errors between export modes

The per-mode loop in `src/prinfo/cli.py:130` records only `ExportError` and `GhCliError`, so an `OSError` raised by an earlier exporter - for example when `comments.json` already exists as a directory, or the output directory is read-only - escapes the loop to the outer handler and prevents later requested modes such as the commit log from running even though they could succeed; expected filesystem failures should be normalized to `ExportError` inside each exporter or included in the per-mode isolation path.
