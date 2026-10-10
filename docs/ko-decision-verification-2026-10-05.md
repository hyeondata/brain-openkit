# KoDecision integration and verification — 2026-10-05

[한국어](ko-decision-verification-2026-10-05.ko.md)

`mmetamong/ko-decision-roberta-large` now works as the optional `ko-decision`
provider for classification, tag suggestions, and search reranking. Actual CPU
and Apple GPU inference, CLI operations, and reviewed metadata writes passed.
The measured quality does **not justify replacing Kev 0.8B**: keep Kev as the
classification default and BM25 as the search default.

This is **unreleased source work**, not a change to the published `v0.2.0a4`
assets. Brain OpenKit code remains MIT; the optional external model is identified
as CC BY-SA 4.0 by its publisher. Model weights are downloaded separately, not
bundled. See [attribution](../ATTRIBUTION.md) and [setup](local-models.md#ko-decision-unreleased-source).

## Implementation

- The local server exposes `/v1/models` and `/v1/systemone`, binds only to
  loopback, and loads a fixed Hugging Face checkpoint before accepting requests.
- Each choice is scored as a tokenizer pair: instruction plus option text,
  followed by source state. Choice IDs are excluded from model text. Scalar
  logits are normalized across choices with temperature 1.
- The server supports up to ten choices and **512 tokens per complete pair**,
  including special tokens. It rejects longer pairs instead of silently
  truncating. The client validates model identity, revision, and token metadata.
- `--prompt-language ko` changes workflow instructions and fixed yes/no option
  descriptions. It does not translate notes, queries, categories, or taxonomy
  descriptions. English remains the default.
- Model failures restore the complete BM25 search result; classification returns
  an explicit error. Suggestions do not write notes. Existing preview, exact-plan
  approval, apply, and undo remain the write path.
- Model confidence is an uncalibrated score, not a correctness probability.
  This integration does not add a tuned abstention threshold.

## Model and environment

Hardware: **Apple M1 Max, 64 GiB RAM, ten logical CPUs**.

| Setting | KoDecision | Kev comparison |
|---|---|---|
| Model | `mmetamong/ko-decision-roberta-large` | `jaredpalmer/kev-0.8b` |
| Revision | `dfd606fff30d52963c0073659ff9a8f6bf1fce6d` | `bf75a6a8848ea6960ff2ed108d9ed44c2941174f` |
| Runtime | PyTorch MPS, float32 | MLX/Metal, bfloat16 |
| Python | 3.13.1 | 3.12.11 |
| Key libraries | Torch 2.14.1, Transformers 5.18.0 | MLX 0.32.2, mlx-lm 0.31.3, Transformers 5.17.0 |
| Temperature | 1.0 | 2.3510958125672174 |

KoDecision has 336,657,409 parameters. Its safetensors SHA-256 is
`aac3d7fbfeaabe2ff532028ab296067e4b47ed41848819f6919fa8c695073c5d`.
It uses batch size four and four Torch CPU threads. A separate CPU run used the
same checkpoint and float32. Remote model code is disabled; safetensors loading
is required. CUDA was not tested.

Kev runtime source was `fe64b1274ea7f80d4095866df90666abb03e9cf6`, with base model
`Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`.
All four GPU benchmark runs were sequential. These are results for the specified
local configurations, **not a controlled architecture-only speed comparison**.
No paid inference API was used; electricity, download, memory, and storage costs
were not measured.

## Frozen benchmark

The existing [bilingual-v1 suite](../benchmarks/bilingual-v1/README.md) was used
without changing its documents, labels, ranking parameters, or taxonomy.
It contains 24 notes and 36 retrieval questions. Reported quality below uses
only the holdout split: **eight Korean and ten English classification notes,
twelve Korean and twelve English search questions**. The six category and four
tag descriptions remain English, including in Korean-prompt runs.

Each run made 352 decision requests: one warmup and 351 measured requests.
Two CPU KoDecision runs plus four GPU runs made **2,112 requests, with zero
request errors**. Every run completed 36/36 retrieval questions and 24/24
classifications, with zero search fallbacks. Before/after corpus hashes match
the frozen manifest. Raw choices and metrics were independently recomputed.

### Korean holdout

FP is the number of incorrect tag assignments across the eight notes. F1 is
micro-averaged over tag assignments; Recall and MRR use the top three results.

| Model / instruction language | Category correct | Tag F1 | Tag FP | Tag FN | Recall@3 | MRR@3 | Request median |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kev / English | 7/8 | 0.8333 | 1 | 3 | 0.7500 | 0.6667 | 123.30 ms |
| Kev / Korean | 8/8 | 0.8462 | 2 | 2 | 0.6667 | 0.6111 | 127.81 ms |
| KoDecision / English | 7/8 | 0.4828 | 9 | 6 | 0.7500 | 0.5278 | 182.65 ms |
| KoDecision / Korean | 7/8 | 0.5714 | 12 | 3 | 0.6667 | 0.5694 | 176.81 ms |
| BM25 | — | — | — | — | 0.6667 | 0.6667 | — |

Request medians cover **all 351 measured calls in each run**, not just Korean
holdout examples. They include local HTTP and client overhead, and exclude
model loading and warmup. One classification can make several requests.

### English holdout

| Model / instruction language | Category correct | Tag F1 | Tag FP | Tag FN | Recall@3 | MRR@3 |
|---|---:|---:|---:|---:|---:|---:|
| Kev / English | 9/10 | 0.6667 | 0 | 5 | 0.9167 | 0.8750 |
| Kev / Korean | 9/10 | 0.5333 | 1 | 6 | 0.8333 | 0.8333 |
| KoDecision / English | 8/10 | 0.3889 | 19 | 3 | 0.9167 | 0.8333 |
| KoDecision / Korean | 8/10 | 0.3200 | 11 | 6 | 0.7500 | 0.5556 |
| BM25 | — | — | — | — | 0.8333 | 0.8333 |

The Korean instructions improved KoDecision's Korean tag recall but increased
false positives from nine to twelve. For `citations.md`, which has no reference
tags, both instruction languages added all four tags. `field-recorder.md` was
classified as software instead of research. Korean-prompt KoDecision moved the
correct `basil.md` result outside the top three for one question where BM25
ranked it first. Kev also made mistakes, including a similar Korean-prompt
retrieval regression for `private-vault.md`.

CPU and MPS KoDecision returned identical choices for all 352 requests per
instruction language, and identical search rankings and tags. Maximum probability
drift was approximately `3.22e-6`. CPU medians were 386.03 ms with English and
415.12 ms with Korean instructions. The first CPU run briefly overlapped Kev
startup, so its latency is supplemental evidence only. An incomplete Kev CPU
attempt and an initial wrong-port connection attempt are excluded from results.

## Functional and regression verification

| Check | Result |
|---|---|
| Actual CPU and MPS checkpoint inference | Passed; model-card example selected the same answer through direct CPU and HTTP MPS paths |
| `doctor`, probe, search citations, classification, evaluation | Passed against the running model |
| Real tokenizer pair lengths 511 / 512 / 513 | First two accepted; 513 rejected with HTTP 413 |
| Oversized note in actual CLI | Full BM25 fallback; classification exits 2 with explicit error; source unchanged |
| Injected server outage | BM25 fallback and explicit classification error |
| Korean note and Korean taxonomy | Expected category `기술` and tag `백업`; no `요리` tag, for one functional example |
| Model suggestion → preview → apply → undo | Passed from source and installed wheel; metadata correct, CRLF body preserved, undo byte-identical |
| Python 3.11.13 unit tests | 288 run: 284 passed, four platform-specific skips, zero failures |
| Python 3.13.1 unit tests | 288 run: 284 passed, four platform-specific skips, zero failures |
| Core-only installed wheel | CLI, provider import, and server help work without Torch or Transformers |

The write test uses a synthetic temporary vault and actual model suggestions.
It verifies Obsidian-compatible Markdown/frontmatter at file level. **Obsidian
UI was not rerun for this feature.** A single fully Korean taxonomy example is
not evidence of broad classification quality.

## Reproduction and evidence

Follow the [runtime setup](local-models.md#ko-decision-unreleased-source) from
this source checkout. In a separate runtime environment and terminal:

```sh
python scripts/serve-ko-decision.py --device mps --threads 4 --batch-size 4
```

From the checkout, using the core CLI environment:

```sh
brain-openkit doctor --provider ko-decision --prompt-language ko --probe
python benchmarks/run_bilingual.py --provider ko-decision --prompt-language ko \
  --base-url http://127.0.0.1:8010 --output /tmp/brain-openkit-ko-benchmark-new
python benchmarks/check_local_providers.py --provider ko-decision --prompt-language ko \
  --output /tmp/brain-openkit-ko-functional-new.json
python benchmarks/check_ko_decision_limits.py \
  --output /tmp/brain-openkit-ko-limits-new.json
python -W error::ResourceWarning -m unittest discover -s tests
```

The benchmark refuses to overwrite its output directory. Use a new path per
run. Repeat with `--prompt-language en`; restart the model with `--device cpu`
for CPU verification. The installed-wheel verifier accepts `--installed
--python /path/to/core-env/bin/python`. Kev comparison setup is documented in
[local models](local-models.md); pass its actual server URL to the benchmark.

The [evidence directory](../benchmarks/ko-decision/2026-10-05/README.md) includes
all six raw runs, runtime metadata, model-file hashes, boundary and write
checks, test logs, and a SHA-256 manifest. Paths referring to the local checkout
or temporary vaults are normalized in published evidence.

These small synthetic holdouts demonstrate operation and reveal regressions;
they do not establish general model superiority or production-vault quality.
A fully Korean frozen taxonomy and a user-reviewed real-vault dataset remain
useful next evaluations. Laya, hosted Jev, Claude, and Codex were not newly
benchmarked here. Keep KoDecision optional and review its tag suggestions.
