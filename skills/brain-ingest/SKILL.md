---
name: brain-ingest
description: Preserve a supplied UTF-8 text or Markdown source and create a linked knowledge note in a selected vault. Use for ingesting files or material the user wants filed.
---

Read the [runtime contract](../references/runtime.md) first. Identify the supplied
source, title, selected vault, and desired result. Search related existing notes
before drafting to avoid duplicates. Read the supplied material within a stated
size/read budget; disclose incomplete reading and unsupported binary formats.

The CLI accepts local UTF-8 files. Pasted text may be staged in a temporary file
outside the vault. For a supplied URL, use the host's available browser/fetch
tool within the user's request, then stage the text actually retrieved. State
that the text is an extraction rather than original response bytes. Do not
pretend a URL, PDF, image, or transcript was read when no suitable tool exists.

```bash
python3 "$BRAIN_RUNNER" ingest "$BRAIN_SOURCE" --title "$BRAIN_TITLE" --vault "$BRAIN_VAULT" --plan "$BRAIN_PLAN" --json
```

This produces an extractive note by default. If the user wants synthesis, draft
it with the host model outside the vault and pass `--draft "$BRAIN_DRAFT"`.
Use `--source-url "$BRAIN_SOURCE_URL"` only for the actual supplied/retrieved
source URL; this records provenance and does not fetch it. Preserve source
claims, uncertainty, and references. Link only to verified existing notes.

Inspect the immutable capture, provenance, generated note, and index changes.
Apply the inspected plan within the ingestion request. Verify capture hash and
links, then report changed paths and transaction ID. Existing captures are
immutable; duplicate content should not create a competing copy.
