---
name: brain-save
description: Save a user-selected answer, decision, or insight into a Markdown knowledge vault. Use when the user explicitly asks to keep conversation content.
---

Read the [runtime contract](../references/runtime.md) first. Save the content the
user selected, not an entire transcript by default. Reuse the selected vault;
clarify only genuinely missing scope or destination. Search for related notes.

Draft the selected knowledge into a UTF-8 file outside the vault. Preserve the
distinction between user assertions, cited evidence, and host inference.
Include external source URLs when actually available; never manufacture a
citation. --source records an existing vault Markdown note and may be repeated.

```bash
python3 "$BRAIN_RUNNER" save "$BRAIN_DRAFT" --path "Notes/decision.md" --source "Notes/evidence.md" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

Choose the requested vault-relative destination rather than the example name;
omit --source when no vault source supports the content. Read an existing
destination before proposing an update. Inspect note and index changes and
apply within the explicit save request using the runtime sequence. Report
saved paths and transaction ID. Saving conversation content adds a record of
that content, not independent proof that all its claims are true.
