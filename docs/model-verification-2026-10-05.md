# Laya and Kev verification — 2026-10-05

Brain OpenKit 0.2.0a2 supports `--provider laya` and `--provider kev` in
`doctor`, `search`, `classify`, and `evaluate`. Both use public Hugging Face
weights served locally by their respective official runtimes. The CLI keeps
model packages optional and never downloads weights itself. Jev remains a
separate hosted provider with its existing API-key requirement.

## Actual model setup

| Item | Laya | Kev |
| --- | --- | --- |
| HF repository | `convaiinnovations/laya`, `multilingual` subfolder | `jaredpalmer/kev-0.5b` |
| Model revision | `7b928d828b7b0e022f929d9bd2e44165aa270148` | `edf1dc6d7f8d983c0adfd251e80a686e5539fc61` (`v0.1`) |
| Runtime | Laya 0.3.26, Python 3.13.1, torch 2.14.1, transformers 5.18.0 | Kev source `fe64b1274ea7f80d4095866df90666abb03e9cf6`, Python 3.12.11, torch 2.8.0, transformers 5.17.0, peft 0.21.0 |
| Device | CPU, four threads | Apple MPS, float32 |
| Base model | Included in checkpoint | `Qwen/Qwen2.5-0.5B@060db6499f32faf8b98477b0a26969ef7d8b9987` |

Both ran on the same 64 GiB Apple Silicon macOS machine, with isolated
environments and offline mode after downloading. Kev's prototype temperature
was 1.0. Different devices and model architectures make these runs unsuitable
for a fair speed or cost comparison.

The [0.5B model card](https://huggingface.co/jaredpalmer/kev-0.5b) identifies it
as an English prototype superseded by the newer family. We exercised 0.5B
because it was specifically raised in the task. No results here establish
0.8B/4B/9B/27B behavior or general Korean quality.

## CLI checks

The [repeatable check script](../benchmarks/check_local_providers.py) copies
the four synthetic example notes to a temporary vault, converts the Korean
search note to CRLF, then uses the real CLI runner against both actual servers.

| Check | Laya | Kev-0.5B |
| --- | --- | --- |
| Health without inference | Passed | Passed (`/v1/models`) |
| Synthetic `doctor --probe` | Passed; expected answer A | Passed; expected answer A |
| Same JSON configuration, provider switch | Passed | Passed |
| Search with model scores and exact source citations | Passed | Passed |
| Korean and English category/tag suggestions | Completed | Completed |
| Four retrieval evaluation queries | 4 model executions, 0 fallbacks | 4 model executions, 0 fallbacks |
| Injected HTTP 503 during search | Original BM25 ordering, all model scores cleared | Same |
| Injected HTTP 503 during classification | Visible error, no fabricated result | Same |
| Original Markdown SHA-256, including CRLF | All four unchanged | All four unchanged |

The outage server is a local HTTP fixture; successful inference used real
weights. Provider-specific keys, malformed JSON/probabilities, no Kev POST
retry, timeout, redirects, truncation and partial-rerank failure are checked
separately by automated HTTP tests.

## Output correctness and limits

Both models categorized `local-search.md` as `research` and `reading.md` as
`reading`. Laya suggested `evaluation` and `local` for the search note. Kev
suggested those plus **the incorrect `plants` tag**. Both suggested no tags
for the reading note. Functional success does not imply every suggestion is
correct, and classification still does not write to notes.

All four small example retrieval queries had Recall@3 and MRR@3 of 1.0 for
BM25, Laya and Kev. This is a functional smoke corpus, not a held-out quality
benchmark. It shows no measured retrieval advantage. The earlier, larger
[Laya bilingual benchmark](../benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md)
remains separate. No Claude/Codex quality or cost comparison was performed.

Kev echoes the request `model` even when it is an arbitrary alias. Its loaded
HF checkpoint is selected by the server `--run`; inspect the `run` and `base`
fields in `doctor` health output. Changing CLI `--model` does not switch
weights. Laya's client explicitly requests `multilingual`.

## Reproduce and inspect

The complete automated suite passed locally on Python 3.11 and 3.13:
**176 tests per run**, with four Windows-only tests skipped on macOS. An
independent review found no actionable issue. A separately installed 0.2.0a2
wheel completed six further actual-server checks: doctor probe, search and
classification for each provider. The dependency-free runner and wheel both
include the new Kev adapter. Cross-platform CI status is available in
[PR #1 checks](https://github.com/hyeondata/brain-openkit/pull/1/checks);
live model inference was tested on the Mac described above.

Follow [the pinned runtime instructions](local-models.md), then run:

```bash
python benchmarks/check_local_providers.py \
  --laya-url http://127.0.0.1:8000 \
  --kev-url http://127.0.0.1:8009 \
  --output /tmp/brain-openkit-provider-smoke.json
```

The [recorded JSON](../benchmarks/provider-smoke/2026-10-05/report.json) includes
health, predictions, scores, evaluation, injected errors and source hashes.
It contains synthetic example text only; temporary absolute paths are replaced
with a stable placeholder. Runtime metadata records the actual revisions.
