# Analysis 3 - Preserve empty comment bodies in the transcript

## Decision: Valid - fix applied

`_comment_body` tested the body with `if not body`, which is true for both `None` and `""`, so a review submitted with an empty body - the normal shape of a `COMMENTED` review that carries only inline comments - was rendered in `comments.md` as the literal text `(no body)`. That contradicted `comments.json`, which stores the empty string verbatim, and made an empty body indistinguishable from a comment whose author actually typed `(no body)`. The check is now `if body is None`, so the placeholder is reserved for a genuinely absent body and an empty string renders as an empty section.

**Why:** PRD REQ-3 requires the transcript to be rendered from the same in-memory records as the JSON, so a value the JSON preserves must not be rewritten on the way to the Markdown. No requirement, README section or skill reference documents `(no body)`, so the placeholder is an implementation detail rather than a specified output, and narrowing it to `None` breaks no documented behavior. The rendering of a `None` body is unchanged.

**Commit:** 91e3584 - fix(cli): address review feedback for PR #2
