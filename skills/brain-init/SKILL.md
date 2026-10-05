---
name: brain-init
description: Initialize or adopt a user-selected Markdown or Obsidian vault for Brain OpenKit. Use when setting up a knowledge vault or checking how to start.
---

Read the [runtime contract](../references/runtime.md) first to locate the bundled
runner, select the vault, and follow the preview/apply sequence.

Use the directory the user selected. If it does not exist, create that empty
directory only when the user asked to create it. Do not use the plugin cache or
clone as the knowledge vault. Existing notes stay user-owned.

```bash
python3 "$BRAIN_RUNNER" init --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Inspect the complete preview, especially existing-file handling. Apply within
the user's setup request using the runtime sequence. Report the index and other
paths created, preserved notes, and transaction ID. Open the chosen directory
in Obsidian if the user asks; Obsidian is optional for CLI use.

Route later tasks to brain-ingest for supplied sources, brain-search for cited
answers, brain-save for selected conversation knowledge, brain-organize for
tags/category/links, and brain-lint for health checks.
