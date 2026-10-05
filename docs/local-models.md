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
| `--provider kev` | [`jaredpalmer/kev-0.5b`](https://huggingface.co/jaredpalmer/kev-0.5b) | `http://127.0.0.1:8009` | `kev-latest` |

`kev-latest` is an API alias for the checkpoint loaded by the server. It does
not mean the newest Hugging Face weights. Brain OpenKit's `--model` overrides
that API alias for Kev/Jev; it does not download or replace a checkpoint.
Restart the Kev server with a different `--run` to change its weights.

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

## Kev 0.5B

The [0.5B checkpoint](https://huggingface.co/jaredpalmer/kev-0.5b) exists and can
run through the official Kev server. It is the earlier `v0.1` checkpoint based
on Qwen2.5-0.5B; it is distinct from the newer 0.8B/4B/9B/27B family. This guide
and its live verification cover 0.5B.

In a separate terminal, clone the runtime outside Brain OpenKit and your vault:

```bash
git clone https://github.com/jaredpalmer/kev.git ../brain-openkit-kev-runtime
cd ../brain-openkit-kev-runtime
git checkout --detach fe64b1274ea7f80d4095866df90666abb03e9cf6
uv sync --extra serve --no-dev --python 3.12
TORCH_FORCE_WEIGHTS_ONLY_LOAD=1 \
KEV_BACKEND=torch KEV_DTYPE=fp32 KEV_TRUNCATE_STATES=0 \
uv run --no-sync python -m kev.serve \
  --run jaredpalmer/kev-0.5b@edf1dc6d7f8d983c0adfd251e80a686e5539fc61 \
  --host 127.0.0.1 --port 8009
```

The first start downloads the decision adapter and its Qwen base model.
This explicitly uses the Torch backend; the recorded Apple Silicon run used
MPS in float32. CPU/CUDA and other operating systems have not been checked in
this live-model run. `KEV_TRUNCATE_STATES=0` makes the server reject oversized
state rather than silently shorten it. Keep it disabled for source-grounded
decisions. `TORCH_FORCE_WEIGHTS_ONLY_LOAD=1` applies Torch's restricted weight
loading path to the legacy checkpoint.

Local Kev is unauthenticated by default. If you set `KEV_API_KEY` on the server,
set the same value privately in the CLI environment. Kev and TypeSafe Jev are
separate projects; a TypeSafe service key is not required for local Kev.

The adapter revision above is fixed, but its metadata does not pin the base
model revision. The live check resolved `Qwen/Qwen2.5-0.5B` to
`060db6499f32faf8b98477b0a26969ef7d8b9987`; a later first installation can resolve
a different base revision. The recorded run used cached weights with
`HF_HUB_OFFLINE=1` after download. For offline reuse, first complete a successful
online start, then retain that cache and add `HF_HUB_OFFLINE=1` to subsequent
server starts. Offline mode requires the base model's cached default-branch
reference as well as its weight files; downloading an explicit base commit
alone may not establish that reference.

The loaded adapter reports temperature `1.0`; calibration values discussed in
the model card do not automatically change its metadata.

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

The script uses a temporary copy of the synthetic example vault. It checks
health, inference, reranking, classification, evaluation, simulated service
failure, and unchanged source bytes. For different ports, pass `--laya-url`
and `--kev-url`. It reports suggestion contents but does not treat every
model-selected tag as correct.

## Recorded runtime evidence and limits

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

Both providers also passed the shared CLI functional check: complete search
reranking, classification, four-query evaluation without fallback, failure
fallback, and exact source preservation including Korean text and CRLF bytes.
Kev suggested an irrelevant `plants` tag for the local-search note. All three
retrieval paths—BM25, Laya, and Kev—scored 1.0 on the tiny four-query fixture;
this is not evidence of a model benefit. See the
[dated verification report](model-verification-2026-10-05.md) and
[raw CLI evidence](../benchmarks/provider-smoke/2026-10-05/report.json).

See [implementation notes](implementation-notes.md) for broader integration and
regression evidence. Other Kev checkpoints can be selected by the official
server, but are not covered by this 0.5B live check. Code, weights, and base
models retain their respective licenses; Brain OpenKit's license does not
replace them.

Primary references: [Laya model](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148),
[Kev 0.5B weights](https://huggingface.co/jaredpalmer/kev-0.5b/tree/edf1dc6d7f8d983c0adfd251e80a686e5539fc61),
[pinned Kev server](https://github.com/jaredpalmer/kev/blob/fe64b1274ea7f80d4095866df90666abb03e9cf6/kev/serve.py).
