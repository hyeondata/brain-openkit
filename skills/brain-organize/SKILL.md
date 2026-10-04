---
name: brain-organize
description: Suggest or apply categories, tags, and existing-note links in a selected vault. Use when organizing a note or applying reviewed classification suggestions.
---

Read the [runtime contract](../references/runtime.md) first. Read the selected
note and preserve its original content and existing frontmatter conventions.

For model suggestions, use classify with the user's taxonomy and explicitly
selected provider; this does not modify notes:

```bash
python3 "$BRAIN_RUNNER" classify "$BRAIN_NOTE" --vault "$BRAIN_VAULT" --taxonomy "$BRAIN_TAXONOMY" --provider laya --json
```

Classification needs a running chosen provider. If none is configured, use
user-specified category/tags or offer host suggestions identified as such. Do
not claim Laya results. Preserve model conflicts and uncertainty. Search
potential link targets and verify they exist.

Preview only the chosen changes, repeating --tag or --link as needed and
omitting options the user did not request:

```bash
python3 "$BRAIN_RUNNER" organize "$BRAIN_NOTE" --category "$BRAIN_CATEGORY" --tag "$BRAIN_TAG" --link "$BRAIN_LINK" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Inspect the diff and apply within the authorized scope using the runtime
sequence. Suggestions alone do not authorize applying them. Unsupported
frontmatter must be reported rather than rewritten manually. Verify resulting
metadata/links and report the transaction ID for undo.
