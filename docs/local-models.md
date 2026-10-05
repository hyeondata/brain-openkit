# Local Laya and Kev models

Laya and Kev use the same Brain OpenKit search, classification, and evaluation
commands. Select `--provider laya` or `--provider kev`. Both can download public
weights from Hugging Face and run inference on your computer without a hosted
inference subscription or Hugging Face token.

Each model needs its own official runtime. Hugging Face is the shared model
registry, while Brain OpenKit provides the shared CLI. A generic text-generation
endpoint does not replace these decision-model servers. The core CLI keeps its
Python 3.11+ standard-library-only runtime; install model dependencies separately.

| Selection | Weights | Default local endpoint | Server model name |
| --- | --- | --- | --- |
| `--provider laya` | [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya), `multilingual` subfolder | `http://127.0.0.1:8000` | `multilingual`, sent explicitly |
| `--provider kev` | [`jaredpalmer/kev-0.8b`](https://huggingface.co/jaredpalmer/kev-0.8b), default checkpoint | `http://127.0.0.1:8009` | `kev-latest` |

`kev-latest` is an API alias for the checkpoint loaded by the server. It does
not mean the newest Hugging Face weights. Brain OpenKit's `--model` overrides
that API alias for Kev/Jev; it does not download or replace a checkpoint.
The bundled `scripts/serve-kev.py` launcher defaults to
`jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f`, the recorded
`v1.0` revision. Restart it with a different `--run` to change its weights.
Classification and `doctor` default to Kev; search and evaluation default to
local BM25 (`--provider none`). Select `--provider kev` to rerank with Kev or
`--provider laya` to use Laya explicitly.

The commands below are for macOS/Linux. They need [uv](https://docs.astral.sh/uv/),
Git, network access for the first installation/download, and sufficient local
disk and memory. Servers bind to loopback. Stop a server with Ctrl+C when done.

## Laya multilingual

In a separate terminal, create a runtime directory outside your vault:

```bash
mkdir -p ../brain-openkit-laya-runtime
cd ../brain-openkit-laya-runtime
uv venv --python 3.13 .venv-laya
uv pip install --python .venv-laya/bin/python "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=1 \
LAYA_REVISION=7b928d828b7b0e022f929d9bd2e44165aa270148 \
.venv-laya/bin/laya-serve
```

This preloads the pinned multilingual checkpoint. The initial download is
approximately 647 MiB. `LAYA_MODELS` controls preloading, not access restrictions;
Brain OpenKit explicitly requests `multilingual` on every inference call.
Use `LAYA_PRELOAD=0` to defer loading until the first request, allowing a longer
client timeout then. If you enable server authentication, set the same
`LAYA_API_KEY` in the server and CLI environments.

## Kev 0.8B default

Start in the Brain OpenKit checkout root in a separate terminal. Install the
official runtime beside the checkout, outside your vault:

```bash
BRAIN_OPENKIT_ROOT="$PWD"
git clone https://github.com/jaredpalmer/kev.git ../brain-openkit-kev-runtime
cd ../brain-openkit-kev-runtime
git checkout --detach fe64b1274ea7f80d4095866df90666abb03e9cf6
uv sync --extra serve --no-dev --python 3.12
uv run --no-sync python "$BRAIN_OPENKIT_ROOT/scripts/serve-kev.py"
```

The last line is the default startup command. It selects the pinned Kev 0.8B
checkpoint and binds to `127.0.0.1:8009`. Initial startup downloads its decision
adapter and Qwen3.5-0.8B-Base weights. The script uses the official Kev runtime
installed in this environment and leaves backend selection to it, including
automatic MLX selection for compatible Apple Silicon models.

The selected adapter also pins its base model to
`Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68` and stores
temperature `2.3510958125672174`. Both model revisions are fixed for this setup.

Use `--host`, `--port`, or `--run` on this launcher to override its startup
defaults. The official runtime defaults to `KEV_TRUNCATE_STATES=0`, so
oversized state is rejected; keep truncation disabled for source-grounded
decisions. Previous 0.5B runs may have used `KEV_BACKEND=torch` and
`KEV_DTYPE=fp32`; omit those overrides for the default 0.8B setup.

Local Kev is unauthenticated by default. If you set `KEV_API_KEY` on the server,
set the same value privately in the CLI environment. Kev and TypeSafe Jev are
separate projects; a TypeSafe service key is not required for local Kev.

The [0.8B verification report](kev-08-verification-2026-10-05.md) records the
checkpoint, loaded runtime, and separate functional results. For offline reuse,
first complete a successful online start, retain the complete model cache,
and add `HF_HUB_OFFLINE=1` to subsequent server starts.

### Optional legacy Kev 0.5B

The earlier [0.5B checkpoint](https://huggingface.co/jaredpalmer/kev-0.5b) remains
available through an explicit override. Stop the 0.8B server first if reusing
the same port, then run from the Kev runtime directory:

```bash
TORCH_FORCE_WEIGHTS_ONLY_LOAD=1 KEV_BACKEND=torch KEV_DTYPE=fp32 \
uv run --no-sync python "$BRAIN_OPENKIT_ROOT/scripts/serve-kev.py" \
  --run jaredpalmer/kev-0.5b@edf1dc6d7f8d983c0adfd251e80a686e5539fc61
```

The [historical 0.5B check](model-verification-2026-10-05.md) used Torch/MPS
float32, Qwen2.5-0.5B base revision
`060db6499f32faf8b98477b0a26969ef7d8b9987`, and adapter temperature `1.0`.
Its adapter metadata does not pin the base revision, so a later first
installation can resolve a different base. Offline reuse needs the cached
default-branch reference as well as weight files. These legacy results are
separate from the default 0.8B model's evidence.

## Check each provider

Return to the Brain OpenKit checkout with its CLI environment active. Run each
line for the server you started; both servers can remain available if the
machine has enough memory.

```bash
brain-openkit doctor --provider laya --json
brain-openkit doctor --provider laya --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider laya --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --timeout 120 --json

brain-openkit doctor --provider kev --json
brain-openkit doctor --provider kev --probe --timeout 120 --json
brain-openkit search "reading journal comets" --vault examples/vault --provider kev --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider kev --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider kev --timeout 120 --json
```

Health confirms that the service responds; `--probe` also asks a synthetic
question. Inspect search output's rerank status: `complete` means the selected
provider ran, while `unavailable` means Brain OpenKit returned BM25 with a
reason. An exit code of zero with BM25 fallback does not prove model inference
worked. Classification errors return no invented suggestions. These commands
do not modify source notes.

To check failure behavior, stop the selected server and repeat its search.
The result should retain BM25 order with an unavailable reason. Restart the
server before checking classification. Use `--base-url` if you chose a
different port; JSON configuration also supports `laya_base_url`,
`kev_base_url`, and `kev_model`. Do not put API keys in JSON configuration.

For a repeatable check of both running servers, run from the checkout root:

```bash
python benchmarks/check_local_providers.py --output ../brain-openkit-provider-check.json
```

To check only the default Kev server:

```bash
python benchmarks/check_local_providers.py --provider kev --output ../brain-openkit-kev-check.json
```

The script uses a temporary copy of the synthetic example vault. It checks
health, inference, reranking, classification, evaluation, simulated service
failure, and unchanged source bytes. For different ports, pass `--laya-url`
and `--kev-url`. It reports suggestion contents but does not treat every
model-selected tag as correct.

## Verification evidence and limits

The default 0.8B model has its own
[verification record](kev-08-verification-2026-10-05.md). On 2026-10-05, its
official runtime loaded the pinned weights on a 64 GiB Apple Silicon
Mac, automatically selecting MLX on MPS in bfloat16. All six direct
Korean/English smoke questions returned valid responses and matched their
expected labels. Starting the bundled launcher without `--run` also loaded the
pinned 0.8B checkpoint, confirmed by the server's model listing. These six
examples establish neither broad quality nor Claude/Codex parity.

The actual CLI check against that default launcher also passed health, synthetic
inference, search reranking, Korean/English classification, and four-query
evaluation with no fallback. Injected HTTP 503 responses preserved the full
BM25 result order and returned classification errors. All four source notes
retained their original hashes. Separate `doctor` and `classify` calls without
`--provider` correctly selected Kev.

Kev 0.8B classified `local-search.md` as `research` with `evaluation` and `local`
tags, and `reading.md` as `reading` with an incorrect `evaluation` tag. The
earlier 0.5B `plants` false positive disappeared, but this different false
positive prevents a claim that overall tagging improved. BM25 and Kev 0.8B both
scored 1.0 on Recall@3 and MRR@3 for the four-query fixture. Six correct simple
probe labels do not mean all classification and tagging decisions are correct.
See the [0.8B raw CLI evidence](../benchmarks/provider-smoke/2026-10-05-kev-08/report.json)
for the complete functional run.

The results below describe the earlier Laya/0.5B run and must not be read as
0.8B results.

On 2026-10-05, both official runtimes loaded actual downloaded weights on an
Apple Silicon Mac with 64 GiB memory:

| Runtime | Recorded environment | Direct inference check |
| --- | --- | --- |
| Laya multilingual | Laya 0.3.26, Python 3.13.1, Torch 2.14.1, Transformers 5.18.0, CPU with four threads | Four Korean/English choices returned valid responses; three matched the smoke labels. |
| Kev 0.5B | Pinned Kev source above, Python 3.12.11, Torch 2.8.0, Transformers 5.17.0, Torch/MPS float32 | Six choices returned valid responses; five matched the smoke labels. |

These small, different prompt sets verify execution, not comparative accuracy.
They do not establish that Kev beats Laya, either model matches Claude/Codex,
or the hybrid workflow saves total cost. Local computation still uses memory,
electricity, and time; host-written prose can still use a paid model. The
[existing bilingual Laya evaluation](../benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md)
is a separate synthetic quality test and contains no Kev comparison.

Laya and Kev 0.5B also passed the shared CLI functional check: complete search
reranking, classification, four-query evaluation without fallback, failure
fallback, and exact source preservation including Korean text and CRLF bytes.
Kev 0.5B suggested an irrelevant `plants` tag for the local-search note. All three
retrieval paths—BM25, Laya, and Kev 0.5B—scored 1.0 on the tiny four-query fixture;
this is not evidence of a model benefit. See the
[dated verification report](model-verification-2026-10-05.md) and
[raw CLI evidence](../benchmarks/provider-smoke/2026-10-05/report.json).

See [implementation notes](implementation-notes.md) for broader integration and
regression evidence. Other Kev checkpoints can be selected by the official
server; use each checkpoint's own evidence to assess its behavior. Code, weights, and base
models retain their respective licenses; Brain OpenKit's license does not
replace them.

Primary references: [Laya model](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148),
[default Kev 0.8B weights](https://huggingface.co/jaredpalmer/kev-0.8b/tree/bf75a6a8848ea6960ff2ed108d9ed44c2941174f),
[Kev 0.5B weights](https://huggingface.co/jaredpalmer/kev-0.5b/tree/edf1dc6d7f8d983c0adfd251e80a686e5539fc61),
[pinned Kev server](https://github.com/jaredpalmer/kev/blob/fe64b1274ea7f80d4095866df90666abb03e9cf6/kev/serve.py).
