# Implementation and validation notes

Snapshot: 2026-10-04. Version: `0.2.0a1`, source installation from the
`codex/cli-mvp` implementation branch until merged. No PyPI release is published.
These notes distinguish implementation, fixture checks, actual execution, and
remaining acceptance work.

## Implemented scope

The CLI provides `doctor`, `index`, `search`, `classify`, `evaluate`,
`init`, `ingest`, `save`, `organize`, `fold`, `lint`, `apply`,
`undo`, `recover`, and `web`, with text/JSON output.
All vault commands require `--vault` or an explicit `vault` config value;
`doctor` alone can omit it. No note-parent inference is performed.

UTF-8 Markdown is indexed into a vault-specific SQLite cache. Search refreshes
changed/deleted files and preserves original passages and inclusive, one-based
line positions. Korean words/bigrams and normalized English words feed BM25.
Search/evaluate default to `none`; classify/doctor default to `laya`.
Any failed candidate decision discards the whole rerank and preserves BM25
order. Classification uses supplied categories/tags without changing notes;
conflicting passage categories remain visible. Tags are a union of positive
passage decisions, not a calibrated document probability.

Both Laya and Jev implement `DecisionProvider.choose()`. Laya explicitly
selects `multilingual`. Jev uses its own documented request/response contract
and retains its reported confidence, whose meaning differs from Laya entropy
confidence. There is no automatic cloud failover or automatic retry of a
billable Jev POST. Keys come from `LAYA_API_KEY`, or for Jev,
`TYPESAFE_API_KEY` with `JEV_API_KEY` as a fallback alias.

### Note plans and recovery

Initialization adopts an existing vault by adding an index without replacing
existing notes. Ingest preserves supplied local UTF-8 source bytes under
`Sources/`, records the original input path/hash and optional URL, and creates
a linked note under `Notes/`. The URL is provenance, not a fetch instruction.
Ingest may use a supplied host-written draft; save accepts a selected draft and
existing source-note references. Fold creates source-linked extracts while
retaining its child notes. The core performs no prose generation or web/media
extraction.

Planners return JSON with original/proposed content, hashes, diffs, and a plan
ID. CLI `--plan` exports to a new file outside the vault; it does not overwrite
an existing plan. Apply requires that exact ID and matching original contents.
Individual replacements are atomic; multi-file operations use a recoverable
journal and are not globally atomic. The toolkit lock coordinates toolkit
operations, not external editors.

Undo requires the recorded post-change contents. Recover handles interrupted
apply/undo; later edits produce conflicts instead of being overwritten.
Plans and `VAULT/.brain-openkit/transactions/` contain full before/after
private note text. Journals, provenance paths, caches, and host logs must be
considered when sharing or syncing a vault.

Organize supports a conservative frontmatter subset: a scalar category and
simple string tags, including supported scalar/flow/block forms. It merges
requested tags and preserves unrelated text/comments/newlines. Unsupported or
ambiguous structures, such as duplicate keys or nested tag values, are rejected.
It appends validated links to existing notes. Lint is read-only and reports
broken/ambiguous note links, orphan notes, and supported metadata errors.
It does not verify the existence of heading/block anchors or apply repairs.

### Host and web interfaces

Eight original skills share the bundled runner:
`brain-init`, `brain-search`, `brain-ingest`, `brain-save`,
`brain-organize`, `brain-lint`, `brain-fold`, and `brain-research`.
They use an explicit vault and the same preview/apply path. A requested
mutation can already authorize applying its inspected plan; preview-only
requests stop before apply. Host-generated drafts and research depend on the
host's own model access and tools, not Laya/Jev text generation.

The runner locates its bundled core from a relocated plugin cache without an
editable install or site packages. Python 3.11+ is still required.
[Agent integration](agent-integration.md) is the canonical setup/operation guide.

The web server binds only `127.0.0.1`, performs BM25 search, renders source
text safely, and has no note-write endpoint or remote assets. It is a local
web alternative, not an Obsidian plugin. It still writes a derived search cache.

## Verification record

| Area | Evidence at this snapshot | Boundary |
| --- | --- | --- |
| Previous 0.1 baseline | 71 local tests and all six CI jobs passed at `9075acb`. | Historical evidence only; not the final 0.2 test/CI result. |
| Current 0.2 unit/fixture suite | Independent full runs on Python 3.11 and 3.13 each reported 159 tests, OK with four Windows-only skips. Coverage includes transactions, note workflows, providers, CLI, web, packaging, and evaluation. | These are local macOS results; the current-revision six-job CI matrix is still pending. |
| Distribution build and clean installation | The source distribution contained all eight skills, shared runtime reference, runner, and four host manifests. A wheel installed offline into a new Python 3.13 environment outside the checkout completed 17 CLI commands, including five planned/applied transactions and their reverse-order undo. Original Markdown hashes were fully restored. | Local installation proof; Linux/Windows release checks remain part of the pending CI matrix. |
| Real Laya | Installed CLI health/probe, rerank, classify, evaluate, unavailable-server fallback, and a larger frozen evaluation were exercised. | Synthetic data; quality results below are mixed or worse than BM25. |
| Jev | Official-contract request/response fixtures and CLI configuration/selection checks. | No actual key or live inference; costs and deployment behavior remain unverified. |
| Claude packaging | Claude Code 2.1.220 validated both manifest files individually with strict validation and discovered eight skills. | Discovery alone is not task execution. |
| Codex packaging | Codex CLI 0.149.0 installed an isolated cached plugin; app-server skill discovery returned all eight enabled skills. The cached runner searched Korean text without package installation. | Plugin installation/discovery and actual invocation are separate checks. |
| Actual Claude search | After renewing host OAuth, a real session invoked the skill, ran the packaged BM25 runner, and returned a Korean answer citing the source at line 3. | Initial host command permissions required a Python fallback; the final search completed. |
| Actual Codex search | A real authenticated session invoked the skill from a temporary workspace's `.agents` tree copied from the installed cache, answered in Korean, and cited `기록.md:3`. Original source bytes were unchanged. | This exercised workspace skill discovery, not the plugin-prefixed invocation route. |
| Actual Codex writes | A real session completed a write/undo flow. Independent inspection found five journal transactions (four applied, one undone), exact captured source bytes, unchanged seed CRLF bytes, expected category/tags/source links, and removal of the undone overview with its index restored. | One disposable-vault flow; not proof of every recovery edge case. |
| Actual Claude writes | A real session completed init, ingest, save, organize, fold, lint, search, and undo. Independent inspection confirmed exact captured source bytes, unchanged seed CRLF bytes, four applied transactions and one undone transaction, restored fold preimages, and expected summary metadata/links. | One disposable-vault flow; interrupted recovery remains covered separately by core tests. |
| Actual Codex research | A real session invoked the research skill, used one official Python documentation source through its web tool, drafted with that source URL, inspected a plan, applied it, and reread the saved note. Independent verification confirmed the applied transaction, source URL, and unchanged copied runtime. | One bounded, single-source run; not general web/PDF/media extraction coverage or a Claude research execution check. |
| Browser | Actual browser automation opened the loopback UI, searched “한국어 BM25 검색 후보”, and inspected two results including `local-search.md:1–7`. | One local browser run; not broad browser/platform certification. |

Local full-suite, host execution, and clean build/install checks above are
complete. The tested distributions preceded removal of an unused skills YAML
glob from the source manifest; implementation code was unchanged. Publication,
PR, and the six-job CI result for the new revision remain pending. Record those
results for the exact revision when available. A passing package import or
plugin inventory alone does not close acceptance.

## Referenced versions

- [claude-obsidian at `32ac5a0`](https://github.com/AgriciDaniel/claude-obsidian/tree/32ac5a02c4e082e4a5628ca810776375e134708e): source preservation, fallback, and portable workflows informed an independent implementation. No code or templates were copied.
- [Laya at `2e4d9c8`](https://github.com/NandhaKishorM/laya/tree/2e4d9c87e8b1621deb344eac7de5c7258f32f849), package `laya==0.3.26`: `GET /health` and `POST /v1/systemone`, explicitly requesting `multilingual`.
- [Laya bundle `7b928d8`, `multilingual` subfolder](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148/multilingual): actual weights used. This SHA belongs to `convaiinnovations/laya`, not `laya-multilingual`.
- Jev: [official API](https://docs.typesafe.ai/api), [OpenAPI](https://api.typesafe.ai/openapi.json), `typesafe-sdk-python==0.7.2`, revision `f078f1e208a0d885154dc758344ae4fce77ac168`; recorded in [the adapter](../src/brain_openkit/jev.py).

## Actual model evaluation

The early four-query [smoke fixture](../examples/README.md) returned recall@5
and truncated MRR of 1.0 for both BM25 and Laya. It confirmed integration,
not a model advantage. The initial separate CPU model load/download took about
29.1 seconds; subsequent simple warm requests took roughly 119–124 ms.

The later [frozen bilingual benchmark](../benchmarks/bilingual-v1/README.md)
has 24 authored notes (12 Korean/12 English), 36 queries (12 development/24
holdout), six categories, and four tags. Classification uses six development
and 18 holdout notes. Labels were fixed before inference and independently
reviewed by a different agent without seeing rankings. The manifest preserves
input hashes and the review record. No labels, ranking settings, or thresholds
were changed after observing results.

| Holdout retrieval | Queries | BM25 recall@3 | Laya recall@3 | BM25 MRR@3 | Laya MRR@3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 24 | 0.7500 | 0.7500 | 0.7500 | 0.6042 |
| Korean query | 12 | 0.6667 | 0.7500 | 0.6667 | 0.6111 |
| English query | 12 | 0.8333 | 0.7500 | 0.8333 | 0.5972 |

Every requested rerank completed: 36 queries, zero fallback/provider errors.
Completion does not imply relevance. Four cross-language holdout questions
never had their relevant notes in the eight lexical candidates, so reranking
could not retrieve them.

For the 18 held-out classification notes, category accuracy was 0.6667 and
macro F1 0.6206. Tag micro/macro F1 were 0.4691/0.4661; exact tag-set accuracy
was 0. All three research notes were misclassified. Tag decisions contained
39 false positives and four false negatives. No calibration was evaluated.

The actual run used macOS arm64, client Python 3.13.1, separate server Python
3.12.11, CPU/four threads, Laya 0.3.26, torch 2.14.1, transformers 5.18.0, and
the pinned multilingual bundle above. Weights were already cached; the
loopback server ran offline. First request was 4.712 seconds including process
model loading; warm median was 115.6 ms over the recorded calls. Holdout
retrieval totaled about 90.4 ms for BM25 versus 19,079.8 ms for Laya.
All 28 input hashes, including all 24 vault notes, were unchanged.

These are one-machine observations, not throughput or hardware requirements.
BM25 ran first, so Laya reused a warm index. Holdout query paraphrases share
the development documents; labels are agent-reviewed synthetic data, not
user-reviewed real-vault labels. Neither significance nor general superiority
is established. See [the full run, raw artifacts, and limitations](../benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md).

## Remaining boundaries and acceptance work

- Complete publication/PR and record the new-revision CI matrix. Local acceptance
  evidence includes clean installation, both hosts' search/write flows, and one
  bounded Codex research flow; separately unmet requirements remain below.
- Verify Jev live inference with an intentionally configured service key;
  fixture coverage does not establish deployed service behavior.
- Evaluate at least 30 user-reviewed real-vault retrieval queries and 50
  classification/tag examples from the original design. The frozen synthetic
  benchmark does not meet that separate acceptance target.
- Generic `score`/`noul` operations and exact tokenizer preflight remain
  unimplemented. Laya requests are bounded; responses reporting dropped state,
  truncated questions, or collapsed options are rejected. `LAYA_JEV_STRICT=1`
  removes required validation fields and is unsupported.
- Probabilities and provider confidence are uncalibrated signals. No model
  threshold automatically authorizes a write.
- BM25 scores cached passages in memory; large-vault performance is unproven.
  Sequential candidate decisions add latency. Chunks target 1,200 characters
  but retain long lines intact; files are bounded to 2 MiB and classification
  to 200 passages.
- The local web alternative is implemented. An Obsidian-native plugin remains
  future work. Generation is supplied by an authenticated host with suitable
  tools; arbitrary web/PDF/media extraction is not a core capability.

See the [roadmap evidence matrix](roadmap-evidence.md), [README](../README.md),
[contribution guidance](../CONTRIBUTING.md), and
[attribution](../ATTRIBUTION.md). Retrieval evaluation rejects invalid relevance
labels or incomplete indexes rather than silently treating those as misses.
