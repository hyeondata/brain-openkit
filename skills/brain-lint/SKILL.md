---
name: brain-lint
description: Inspect a selected Markdown or Obsidian vault for broken links and metadata or structure issues. Use for read-only vault health checks.
---

Read the [runtime contract](../references/runtime.md) first.

```bash
python3 "$BRAIN_RUNNER" lint --vault "$BRAIN_VAULT" --json
```

Report checks and findings the CLI actually returns, preserving affected paths,
line numbers, and targets. Distinguish broken links from ambiguous ones; a lack
of incoming links can be intentional. Explain likely repairs without claiming
semantic fact checking, contradiction analysis, or automatic fixes.

This workflow is read-only. Do not persist a lint report, create missing notes,
change metadata, or delete orphan notes unless the user requests a concrete
repair. Route requested tag/category/link edits to brain-organize and selected
note updates to brain-save, with a preview and hash-checked apply.
