# Roadmap implementation and evidence

This matrix tracks the original roadmap rather than treating a plugin manifest
as the completed product. Release target: **0.2.0a3**, source installation from
`codex/cli-mvp`. Validation is against synthetic vaults, not private user data.

Implementation is available in [draft PR #1](https://github.com/hyeondata/brain-openkit/pull/1).
All six [CI jobs at `33d3a42`](https://github.com/hyeondata/brain-openkit/actions/runs/37210403995)
passed; actual host and model evidence is recorded in
[implementation notes](implementation-notes.md).

The 0.2.0a2 addition makes Laya and Hugging Face Kev checkpoints interchangeable
through the CLI. See [the actual model checks](model-verification-2026-10-05.md)
and [pinned local setup](local-models.md).

Version 0.2.0a3 selects Kev for `doctor`/`classify` and provides a pinned Kev
0.8B launcher. Search/evaluate retain their BM25 default. See the separate
[0.8B verification](kev-08-verification-2026-10-05.md); earlier model results
are preserved as historical evidence.

| Original item | Implementation | Verification and remaining limits |
| --- | --- | --- |
| Read-only indexing and retrieval | SQLite refresh, BM25, exact path/line/excerpt | Original CLI tests; unchanged source hashes; Korean/English and CRLF checks |
| Optional Laya decisions | Explicit multilingual choice adapter, whole-query fallback, passage classification/tags | Actual Laya 0.3.26/checkpoint run; 352 successful benchmark requests. Quality limits below |
| Hugging Face Kev decisions | Kev is the default for doctor/classify; pinned 0.8B launcher, replaceable endpoint/model/key | Actual Kev-0.8B CLI search, category/tag suggestions, evaluation, HTTP outage fallback and unchanged source hashes. Earlier 0.5B/Laya evidence retained; larger Kev checkpoints remain unmeasured |
| Installable CLI and tests | Python >=3.11 package and dependency-free plugin runner | Installed CLI, relocated plugin cache, standard-library test suite; CI verification recorded in implementation notes |
| Broader Korean/English evaluation | Frozen 24-note corpus, 36 retrieval queries, category/tag labels; separate development and query holdout | Labels independently reviewed before measurement; metrics independently recomputed. Same-corpus synthetic holdout only |
| Jev adapter/configuration | Separate TypeSafe response validation, environment credential, provider-specific endpoints/model | Local HTTP contract/error tests. Live account inference unverified because no key is configured; no silent hosted fallback |
| Reviewed metadata/link updates with recovery | Preview hashes/diffs, explicit plan ID, journal, apply/undo/recover | Fault-injected second-file failure, actual subprocess crash, stale-edit refusal, metadata/newline and path tests |
| Source ingestion, wiki creation, optional generation | Init/adopt index, immutable source capture, linked notes, save, additive fold, lint; host-written drafts | CLI workflow loop; actual agent runs recorded in implementation notes. Laya/Kev/Jev choose from options; the host writes prose |
| Obsidian plugin **or** local web interface | Read-only loopback web search | Actual browser Korean search and source display; HTTP/DOM/security regression tests. No native Obsidian plugin |
| Added requirement: Claude and Codex use | Eight shared skills, each host's plugin/catalog, cached source runner | Claude strict manifest validation; Codex installed cache discovery; actual host invocation separately recorded |

## Evaluation decision

Keep BM25 as the default. At k=3, the 24-query synthetic holdout had recall 0.75
for both BM25 and Laya, but MRR changed from 0.75 to 0.6042 with Laya. Holdout
category accuracy was 0.6667 and tag micro-F1 was 0.4691. This run supports
**optional suggestions and human review**, not an assertion that Laya improves
retrieval or that classification is ready for unattended note changes.

See the [frozen benchmark report](../benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md)
for raw evidence, versions, failures, split definitions and timing context.

## Follow-up requirements retained explicitly

- User-reviewed real-vault evaluation: the original design's minimum 30
  retrieval and 50 classification examples remains an unmet quality-validation
  target. Synthetic labels do not count as user review or private-vault proof.
- Live Jev inference once the operator configures `TYPESAFE_API_KEY` locally.
- Exact provider-tokenizer preflight and automatic safe re-chunking.
- Choice is the current common provider operation; score/noul are extension
  ideas rather than exercised interfaces of this release.
- Native Obsidian UI, MCP transport, public package/directory publication,
  full YAML semantics and heading/block-link linting are separate extensions.

The toolkit can be installed and used without these extensions. Production
quality for a user's own notes must be measured on their labels; no model score
or confidence threshold authorizes a file write.
