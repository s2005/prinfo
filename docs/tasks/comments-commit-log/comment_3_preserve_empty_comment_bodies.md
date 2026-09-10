# P2 - Preserve empty comment bodies in the transcript

`_comment_body` in `src/prinfo/exporter.py:626` tests the body with `if not body`, so a legitimately empty body - as GitHub commonly returns for a `COMMENTED` review - is replaced with the literal text `(no body)`, which makes `comments.md` differ from the exported record in `comments.json` and makes an empty body indistinguishable from a user who actually wrote that text; the empty string should be preserved verbatim and the placeholder reserved for `None`.
