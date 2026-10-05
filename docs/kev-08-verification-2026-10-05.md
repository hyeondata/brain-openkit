# Kev 0.8B default — 2026-10-05

Version 0.2.0a3 uses Kev by default for `doctor` and `classify`. The new
`scripts/serve-kev.py` starts pinned Kev 0.8B weights when `--run` is omitted.
It runs in the separately installed Kev Python environment; the core CLI does
not download or launch a model. Search and evaluation retain their BM25 default,
and an explicit provider or existing configuration still takes precedence.

## Loaded model

The actual launch used the new script with only `--port 18009`; no checkpoint
argument was supplied. `/v1/models` confirmed:

| Field | Observed value |
| --- | --- |
| HF checkpoint | `jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f` (resolved from `v1.0`) |
| Base checkpoint | `Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68` |
| Official server source | `fe64b1274ea7f80d4095866df90666abb03e9cf6` |
| Backend | Auto-selected MLX on Apple Silicon; bfloat16 |
| Temperature | `2.3510958125672174`, loaded from the checkpoint |
| Truncated states | Disabled |

The server used cached weights offline after download. Unlike the previous
0.5B setup, neither Torch nor fp32 was forced. Both adapter and base revisions
are pinned. The HTTP `kev-latest` alias is unchanged: it does not select weights.
Existing 0.5B servers must be restarted with the new launcher to use 0.8B;
inspect the `run` field in `doctor --json` to confirm the loaded checkpoint.

## Actual checks

| Check | Result |
| --- | --- |
| Default launcher, without `--run` | Loaded the pinned 0.8B checkpoint |
| `doctor --probe`, without `--provider` | Used Kev and returned expected choice A |
| `classify`, without `--provider` | Used Kev successfully |
| Search with `--provider kev` | Completed reranking with model scores and exact source citations |
| English and Korean category/tag suggestions | Completed for both synthetic example notes |
| Four-query retrieval evaluation | Four model-backed queries, zero fallbacks |
| Injected HTTP 503 during search | Complete return to original BM25 order; all model scores cleared |
| Injected HTTP 503 during classification | Error returned; no fabricated suggestions |
| Four source Markdown files, including Korean CRLF | All SHA-256 values unchanged |

An additional six direct synthetic questions reused the earlier probe inputs.
All six returned valid responses and matched the expected labels. These are
small functionality checks, not an estimate of real-vault accuracy.

## Suggestion quality

For `local-search.md`, 0.8B chose `research` and tags `evaluation`, `local`.
The earlier 0.5B `plants` false positive was absent. However, 0.8B attached an
incorrect `evaluation` tag to `reading.md`, while correctly choosing `reading`
as its category. This does not establish an overall quality improvement.

BM25 and 0.8B both had Recall@3 and MRR@3 of 1.0 on the tiny four-query example
corpus. Model confidence is not verified correctness, and suggestions still
require review before a note change. No Claude/Codex quality or cost comparison
was performed. The earlier [0.5B/Laya verification](model-verification-2026-10-05.md)
and its raw results are preserved separately.

## Reproduce

Follow [the local model setup](local-models.md), then run:

```bash
brain-openkit doctor --probe --timeout 120 --json
python benchmarks/check_local_providers.py --provider kev \
  --output /tmp/brain-openkit-kev-08-check.json
```

For a different port, pass `--base-url` to the CLI or `--kev-url` to the check
script. The [raw evidence](../benchmarks/provider-smoke/2026-10-05-kev-08/report.json)
contains actual runtime identity, requests, predictions, source hashes,
evaluation and injected-error results. Temporary paths are normalized.

The launcher regression tests exercise default and explicit checkpoints,
paths containing spaces, missing runtime guidance, port validation and child
exit status. A Windows-specific process-handling issue found during review
was corrected before release. Python 3.11 and 3.13 each ran 184 tests locally,
with four Windows-only skips. The wheel and source distribution built without
warnings; a separately installed 0.2.0a3 wheel also passed actual `doctor` and
`classify` calls without a provider flag. CI status is available in
[PR #1 checks](https://github.com/hyeondata/brain-openkit/pull/1/checks).
