---
name: brain-organize
description: Suggest or apply categories, tags, and existing-note links in a selected vault. Use when organizing a note or applying reviewed classification suggestions.
---

Read the [runtime contract](../references/runtime.md) first. Preserve the selected
note's original content and existing frontmatter conventions.

When the user requests suggestions without selecting a separate provider, use
the current Claude/Codex host. Read the **entire note** and the user's taxonomy,
including the descriptions of every permitted category and tag. Choose the
note's dominant topic and only tags substantially supported by its main content.
An incidental testing section, cache example, or passing mention does not by
itself justify an extra category or tag. If the complete note exceeds the host's
context or the CLI input limit, report the limit; do not silently truncate it or
claim a whole-document judgment from selected passages.

Write a JSON suggestion outside the vault and plugin directory. It must contain
exactly these fields: `category` (one permitted category name), `tags` (an array
of unique permitted tag names, possibly empty), `rationale` (a nonempty explanation
of at most 2,000 characters), and `review_required` (a boolean indicating ambiguity).
Use `review_required: true` when competing interpretations need user review.
For example, with matching taxonomy names:

```json
{"category":"research","tags":["local"],"rationale":"The note focuses on local search methods.","review_required":false}
```

Validate that file without starting another model process:

```bash
python3 "$BRAIN_RUNNER" classify "$BRAIN_NOTE" --vault "$BRAIN_VAULT" --taxonomy "$BRAIN_TAXONOMY" --suggestions "$BRAIN_SUGGESTIONS" --json
```

This reports `provider: "host"` and `classification_scope: "document"`.
`--suggestions` overrides a saved provider setting for this call; do not combine
it with an explicit provider other than `none`. Validation checks the structure
and permitted values, not the factual quality of the host's interpretation.

When a provider is explicitly selected in this task or established configuration,
honor it instead. Codex classifies the whole note in one request; Kev, Laya, Jev,
and ko-decision retain passage-based decisions. Set `BRAIN_PROVIDER` accordingly:

```bash
python3 "$BRAIN_RUNNER" classify "$BRAIN_NOTE" --vault "$BRAIN_VAULT" --taxonomy "$BRAIN_TAXONOMY" --provider "$BRAIN_PROVIDER" --json
```

Provider classification needs the chosen service or authenticated Codex CLI.
Report failure without silently switching providers. There is no `--provider
claude`; Claude uses the host suggestion path above. Both paths leave notes
unchanged. Preserve conflicts and uncertainty, including `review_required`.
For user-specified category/tags, skip model inference. Search potential link
targets and verify they exist.

Preview only the chosen changes, repeating --tag or --link as needed and
omitting options the user did not request:

```bash
python3 "$BRAIN_RUNNER" organize "$BRAIN_NOTE" --category "$BRAIN_CATEGORY" --tag "$BRAIN_TAG" --link "$BRAIN_LINK" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Inspect the diff and apply within the authorized scope using the runtime
sequence. Suggestions alone do not authorize applying them. Unsupported
frontmatter must be reported rather than rewritten manually. Verify resulting
metadata/links and report the transaction ID for undo.
