---
name: brain-fold
description: Create a source-linked extractive rollup of selected vault notes while preserving the originals. Use when combining selected notes into an overview.
---

Read the [runtime contract](../references/runtime.md) first. Select the specific
notes or bounded set requested by the user. Read them, identify overlap and
contradictions, and choose the requested new title and vault-relative path.

```bash
python3 "$BRAIN_RUNNER" fold "Notes/first.md" "Notes/second.md" --path "Notes/overview.md" --title "$BRAIN_TITLE" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Replace example paths with the selected notes; repeat positional notes within
CLI limits. The CLI creates an extractive, linked rollup, not an automatic model
summary. Inspect every source, the output and index changes. Apply only when the
user requested creating/saving the rollup; an exploratory summary is preview-only.

Verify original notes remain unchanged and the references resolve. Report the
rollup path, transaction ID, and source disagreements. For a prose synthesis
instead, draft with the host model and use brain-save with all supporting notes
as repeated --source values.
