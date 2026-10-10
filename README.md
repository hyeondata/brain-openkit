<h1 align="center">Brain OpenKit</h1>

<p align="center">
  <strong>An open-source second-brain toolkit for Obsidian.</strong><br>
  Source-grounded search and reviewed note workflows, with replaceable decision providers.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/status-alpha-d97706" alt="Alpha">
  <a href="https://huggingface.co/convaiinnovations/laya"><img src="https://img.shields.io/badge/optional%20model-Laya-0f766e" alt="Optional model: Laya"></a>
</p>

<p align="center">
  English · <a href="README.ko.md">한국어</a><br>
  <a href="#what-it-does">Overview</a> · <a href="#install-from-source">Install</a> ·
  <a href="docs/agent-integration.md">Claude Code / Codex</a> ·
  <a href="docs/conversation-archive.md">Conversation archive</a> ·
  <a href="#providers">Providers</a> · <a href="#roadmap">Roadmap</a>
</p>

> **Alpha [v0.2.0a4](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4).**
> Use the tagged checkout for a repeatable CLI and host-plugin installation.
> GitHub release assets provide the CLI and full source; PyPI is not published.
> See the [0.2.0a4 verification](docs/release-0.2.0a4.md),
> [historical 0.2.0a3 verification](docs/release-0.2.0a3.md) and
> [implementation notes](docs/implementation-notes.md) for their respective evidence and limits.

The optional `ko-decision` and `codex` providers and `--prompt-language` option described below
are unreleased source changes. They are not included in the `v0.2.0a4` tag or its
release assets; use the checkout containing these changes to try them.

Brain OpenKit finds Markdown passages with original paths, line numbers, and
excerpts. **Search defaults to local BM25, without a model or API key.** Claude
Code or Codex can use the same eight skills to retrieve evidence, draft notes,
and apply reviewed changes. Optional Laya, Kev, ko-decision, Codex, and TypeSafe Jev adapters make
relevance and category/tag decisions; they do not generate prose.

## What it does

- Index changed/deleted notes and retrieve original passages with inclusive,
  one-based source lines. Failed reranking preserves the complete BM25 order.
- Suggest among up to 10 categories and evaluate up to 30 tags independently.
  Conflicting passage categories remain visible; classification never edits notes.
- Initialize/adopt a vault, capture local sources, save selected drafts, add
  metadata/links, and create extractive overviews through reviewable change plans.
- Apply an exact approved plan, record a transaction, and undo or recover when
  file contents still match the recorded state.
- Inspect links and supported metadata, evaluate labeled queries, and browse
  read-only BM25 search at `127.0.0.1`.
- Keep optional local Markdown conversation archives under
  `Inbox/Conversations/`; archiving is off by default.

The product checkout and your vault are separate directories. Search and
classification read source notes; indexes are derived cache files. Curated
note workflows preview first and write only through an explicitly applied plan.

**Conversation archiving is off by default.** Enabling it for an explicit
vault authorizes local Markdown archive updates. Archiving uses no model and
makes no network requests; the host conversation may still use a paid hosted
model. See the [conversation archive guide](docs/conversation-archive.md) for
status, enable/disable commands, host setup and current verification limits.
Claude Code and Codex CLI capture passed working-source OFF/ON/resume checks.
Codex Desktop capture is unverified. Final artifact and CI results are recorded
with the [release evidence](docs/release-0.2.0a4.md).

A synthetic vault was checked in Obsidian 1.13.4 for saved content, native
content/tag search, links/backlinks, graph updates, and undo. See the app
verification report in [English](docs/obsidian-app-verification-2026-10-05.md)
or [한국어](docs/obsidian-app-verification-2026-10-05.ko.md) for nine screenshots
and the verified scope.

## Install from source

Use **Python 3.11 or newer**. These macOS/Linux commands use the `v0.2.0a4`
tag to fix the version; ongoing development uses `main`.

~~~bash
git clone --branch v0.2.0a4 --depth 1 https://github.com/hyeondata/brain-openkit.git
cd brain-openkit
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m brain_openkit --help
brain-openkit --version
~~~

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
The CLI has no third-party runtime dependencies; installation may download
build tooling. Local Laya, Kev, and ko-decision servers use separate optional environments.

Download the release assets from the
[GitHub prerelease](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4):

| Asset | Use |
| --- | --- |
| [brain_openkit-0.2.0a4-py3-none-any.whl](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4-py3-none-any.whl) | CLI-only installation into a Python environment. |
| [brain_openkit-0.2.0a4.tar.gz](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4.tar.gz) | Full source distribution; extract it to use the CLI source and host plugins. |
| [SHA256SUMS](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/SHA256SUMS) | SHA-256 checksums for the release files. |

For the CLI alone, install the downloaded wheel in an activated Python environment:

~~~bash
python -m pip install ./brain_openkit-0.2.0a4-py3-none-any.whl
~~~

**Host plugins require the tagged checkout or extracted full source distribution.**
Keep `skills/`, `scripts/`, `src/`, `hooks/`, and the host manifests together. Installing
the wheel, or installing the source archive through pip, installs the Python
CLI but does not register a Claude/Codex plugin. The examples below use the
complete checkout, including its synthetic example vault. No PyPI package is published.

Every vault workflow requires an explicit vault. Existing note workflows accept
**`--vault` or `vault` in a JSON config**; `conversations` commands require
`--vault` directly.
The CLI does not infer the vault from a note's parent directory. Only
`doctor`, which checks the provider, can run without a vault.

## Use from Claude Code or Codex

From the root of the tagged checkout or extracted full source distribution,
register the local marketplace with your host:

~~~bash
# Claude Code
claude plugin marketplace add "$PWD"
claude plugin install brain-openkit@brain-openkit

# Codex
codex plugin marketplace add "$PWD"
codex plugin add brain-openkit@brain-openkit
~~~

Restart the host after installation. The bundled Python runner works from the
plugin cache without an editable package install. Python 3.11+ and the host's
normal authenticated model access are still required.
These instructions use a local product directory. See the
[0.2.0a4 verification](docs/release-0.2.0a4.md) for the current verification
scope. The [0.2.0a3 verification](docs/release-0.2.0a3.md) records the earlier
release and does not verify conversation archiving.

| Skill | Purpose |
| --- | --- |
| `brain-init` | Initialize or adopt a vault without replacing existing notes. |
| `brain-search` | Answer a vault-scoped question with real source citations. |
| `brain-ingest` | Preserve supplied source text and create a linked note. |
| `brain-save` | Save selected knowledge with source links. |
| `brain-organize` | Review and apply chosen metadata and existing-note links. |
| `brain-lint` | Report link and metadata issues without repairs. |
| `brain-fold` | Create an extractive overview while preserving source notes. |
| `brain-research` | Use host research tools, then save a cited dossier. |

For example, invoke `/brain-openkit:brain-search` in Claude Code or
`$brain-openkit:brain-search` in Codex and supply your vault's absolute path.
See the canonical [agent integration guide](docs/agent-integration.md) for
installation, invocation, workspace skill fallback, validation, and removal.

The host writes requested prose and supplies any web/extraction tools.
The CLI itself ingests local UTF-8 text; it does not browse, perform OCR, or
transcribe. Local decision models do not make a hosted Claude/Codex conversation offline.

## Try local search

With the CLI environment active, run from the checkout root:

~~~bash
brain-openkit index --vault examples/vault
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault
brain-openkit search "reading journal comets" --vault examples/vault --json
brain-openkit lint --vault examples/vault --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --json
brain-openkit web --vault examples/vault --port 8765
~~~

Open `http://127.0.0.1:8765` for the last command; stop it with Ctrl+C.
The web interface binds only to loopback and offers read-only BM25 search.
It is not an Obsidian plugin.

Search and evaluation default to `--provider none` and refresh the index.
Cache defaults to `.cache/brain-openkit` under the working directory; use
`--cache-dir` to change it. The [four-note fixture](examples/README.md)
checks execution, not retrieval quality.

## Preview and apply note changes

Use a disposable vault first. Plans must be saved to a **new file outside the
vault**, in an existing directory. They contain the proposed text and diffs.

~~~bash
mkdir -p ../brain-openkit-demo ../brain-openkit-review
brain-openkit init --vault ../brain-openkit-demo --plan ../brain-openkit-review/init.json --json
~~~

Read that JSON's `changes`, `diff` entries, and `id`. Replace the placeholder
below with the exact ID of the plan you reviewed:

~~~bash
brain-openkit apply ../brain-openkit-review/init.json --vault ../brain-openkit-demo --approve PASTE_REVIEWED_PLAN_ID --json
~~~

The following examples build successive plans. **Review and apply each plan
before building the next one**, using the same apply command with its filename
and exact ID. Preview-only commands do not modify vault notes.

~~~bash
brain-openkit ingest examples/vault/local-search.md --title local-search --vault ../brain-openkit-demo --plan ../brain-openkit-review/ingest.json --json
brain-openkit save examples/vault/local-search.md --path Notes/search-decision.md --source Notes/local-search.md --vault ../brain-openkit-demo --plan ../brain-openkit-review/save.json --json
brain-openkit organize Notes/local-search.md --category research --tag local --link Notes/search-decision.md --vault ../brain-openkit-demo --plan ../brain-openkit-review/organize.json --json
brain-openkit fold Notes/local-search.md Notes/search-decision.md --path Notes/search-overview.md --title "Search overview" --vault ../brain-openkit-demo --plan ../brain-openkit-review/fold.json --json
~~~

`ingest` preserves source bytes under `Sources/`; `--draft FILE` optionally
uses host-written prose for the linked note. `--source-url URL` records
provenance and does not fetch the URL. `save` saves the supplied draft;
`fold` extracts passages and citations without generating a summary.
`organize` merges requested tags and supports a conservative frontmatter
subset, preserving unrelated text. Unsupported structures are rejected.
Model scores never authorize metadata changes.

Successful apply returns a transaction ID. Use it for reversal, or use the
interrupted transaction's ID for recovery:

~~~bash
brain-openkit undo TRANSACTION_ID --vault ../brain-openkit-demo --json
brain-openkit recover INTERRUPTED_TRANSACTION_ID --vault ../brain-openkit-demo --json
~~~

Apply checks original contents; undo checks the recorded post-change contents.
Conflicting edits stop the operation. Each file replacement is atomic; a
multi-file transaction relies on its journal for recovery. The toolkit lock
does not lock external editors.

**Plans and `VAULT/.brain-openkit/transactions/` contain private before/after
note text.** Treat them as private vault data, including when syncing or sharing.
Keep the journal for recovery; removing a plugin does not remove it.

## Providers

| Provider | Role and current evidence |
| --- | --- |
| `none` | Default for search/evaluate; local BM25, no model key or inference. |
| `laya` | Optional local multilingual decisions; exercised with real weights. |
| `kev` | Default for classify/doctor; the bundled launcher selects pinned Hugging Face Kev 0.8B weights. [Actual CLI checks passed](docs/kev-08-verification-2026-10-05.md). |
| `jev` | Hosted TypeSafe adapter; contract fixtures pass, live-key inference remains unverified. |
| `ko-decision` | Optional Korean RoBERTa decisions in the unreleased source. Uses a pinned external checkpoint; see [setup](docs/local-models.md#ko-decision-unreleased-source) and [verification](docs/ko-decision-verification-2026-10-05.md). |
| `codex` | Optional cloud decisions through an authenticated Codex CLI, in unreleased source. The current configured defaults are `gpt-6-astra` and `ultra` reasoning. |

`classify` and `doctor` default to Kev unless overridden by config or flags;
the bundled Kev launcher selects 0.8B. Select Laya with `--provider laya`.
Search and evaluation continue to default to local BM25 (`--provider none`).
The common protocol currently implements `choose`; generic `score` and
`noul` operations are future work. Remote providers receive selected excerpts
when explicitly selected; there is no automatic cloud failover.

Laya and Kev both download public weights from Hugging Face and run locally.
They use their own official servers behind the same Brain OpenKit commands;
Hugging Face hosts the downloads, not inference for this setup. No Hugging Face
token is required for these public weights. See the [local model guide](docs/local-models.md)
for pinned versions and the distinction between a checkpoint and an API model name.
Kev 0.8B passed [actual CLI checks](docs/kev-08-verification-2026-10-05.md) for
inference, reranking, category/tag suggestions, evaluation, failure fallback,
and unchanged source notes. Default `doctor` and `classify` calls also selected
Kev correctly. [Earlier Laya/0.5B results](docs/model-verification-2026-10-05.md)
remain separate. Functional checks establish execution; 0.8B still made a tag
error, so these checks do not establish quality parity or general improvement.

### Optional Laya server

In a **separate environment and terminal**, use the tested runtime:

~~~bash
python3.12 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=0 \
LAYA_REVISION=7b928d828b7b0e022f929d9bd2e44165aa270148 \
laya-serve
~~~

This loads lazily. `LAYA_MODELS` specifies preload targets, not access
restrictions. The client explicitly requests `multilingual`; the first
inference downloads/loads its checkpoint. Initial installation and weights
require network access, disk space, and runtime memory.

Back in the **CLI terminal** with `.venv` active:

~~~bash
brain-openkit doctor --provider laya --json
brain-openkit doctor --provider laya --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider laya --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --json
~~~

`doctor` checks health only; **`--probe` runs synthetic inference** and can
trigger downloading. Use `--timeout 120` for initial loading instead of the
default 10 seconds. If server authentication is enabled, set the same
`LAYA_API_KEY` in both terminals. These public weights do not require a
Hugging Face token.

### Optional Kev server

Start the server with the [Kev 0.8B setup](docs/local-models.md#kev-08b-default)
in a separate terminal. After runtime installation, `scripts/serve-kev.py`
loads the pinned 0.8B checkpoint without a `--run` argument. Then run these
commands from the CLI environment:

~~~bash
brain-openkit doctor --provider kev --json
brain-openkit doctor --provider kev --probe --timeout 120 --json
brain-openkit search "reading journal comets" --vault examples/vault --provider kev --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider kev --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider kev --timeout 120 --json
~~~

The default endpoint is `http://127.0.0.1:8009` and API model name is
`kev-latest`. The server launcher selects Kev 0.8B by default; its `--run`
option selects another Hugging Face checkpoint.
`--model` selects an API model name and does not download or switch weights.
Local Kev needs no API key unless the server enables authentication; in that
case set the matching `KEV_API_KEY` in the CLI environment. Kev is a separate
project from the hosted TypeSafe Jev service.
The [0.8B verification report](docs/kev-08-verification-2026-10-05.md) records
its own results separately from the historical 0.5B checks.

### Optional ko-decision server (unreleased source)

Follow the [separate runtime setup](docs/local-models.md#ko-decision-unreleased-source)
to install `.[ko-decision]` and start `brain-openkit-serve-ko-decision`. The server
downloads `mmetamong/ko-decision-roberta-large` at revision
`dfd606fff30d52963c0073659ff9a8f6bf1fce6d` and listens on `127.0.0.1:8010`.

~~~bash
brain-openkit doctor --provider ko-decision --prompt-language ko --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider ko-decision --prompt-language ko --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider ko-decision --prompt-language ko --timeout 120 --json
~~~

`--prompt-language ko` changes the built-in instructions and labels; it does not
translate the query, notes, or taxonomy. English remains the default for every
provider. Each instruction/option plus passage pair must fit 512 tokens,
including special tokens. Oversized pairs return HTTP 413: search falls back to
BM25 and classification returns an error. Scores are uncalibrated relative
option probabilities, and the model does not generate summaries. See the
[verification report](docs/ko-decision-verification-2026-10-05.md) for measured
behavior and limitations. Kev and BM25 remain the defaults.

The optional weights are downloaded separately under the publisher's
[CC BY-SA 4.0 license](https://huggingface.co/mmetamong/ko-decision-roberta-large/blob/dfd606fff30d52963c0073659ff9a8f6bf1fce6d/README.md).
Brain OpenKit's independently implemented integration remains MIT; the repository
does not include the weights. See [attribution](ATTRIBUTION.md).

### Optional TypeSafe Jev

Set `TYPESAFE_API_KEY` privately in the CLI environment. `JEV_API_KEY` is
an alias used only when the primary variable is unset or empty.
Do not put keys in JSON, notes, or checked-in scripts.

~~~bash
brain-openkit doctor --provider jev --json
brain-openkit search "reading journal" --vault examples/vault --provider jev --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider jev --json
~~~

The default endpoint is `https://api.typesafe.ai` and model is `jev-latest`;
override the model with `--model`. Jev health checks its model listing without
inference. `doctor --provider jev --probe` performs an inference request and
may incur service charges, as can search/classification. Live service behavior
has not been verified with an actual key.

### Optional Codex CLI (unreleased source)

Install a compatible Codex CLI and sign in separately with `codex login` (or
`/path/to/codex login` for a separate executable). Brain OpenKit uses that existing
login; it does not read credentials. Replace `/path/to/codex` below with your CLI
path, or omit `--codex-executable` to use `codex` from `PATH`.

~~~bash
brain-openkit doctor --provider codex --json
brain-openkit doctor --provider codex --model gpt-6-astra --reasoning-effort ultra --codex-executable /path/to/codex --probe --json
brain-openkit search "local search" --vault examples/vault --provider codex --model gpt-6-astra --reasoning-effort ultra --codex-executable /path/to/codex --codex-timeout 600 --json
~~~

Without `--probe`, `doctor` only checks the executable/version, not authentication
or model access. `--probe` performs real inference and consumes usage or incurs
charges, as do Codex search/classification requests. Selecting this provider sends
the selected note passages, questions, and choice descriptions to the cloud.
The provider is read-only and returns decisions; probabilities/confidence are
self-assessments, not calibrated classifier scores. A failed search rerank returns
BM25 with `rerank_status: "unavailable"`; this is not successful Codex inference.
Classification failures return an error.

`--model` and `--reasoning-effort` override the configured defaults above, without
automatic model fallback. `--codex-timeout` defaults to 600 seconds and is separate
from the HTTP `--timeout`. In a local check on 2026-10-09, CLI 0.149.0 was rejected
by the server for `gpt-6-astra`; CLI 0.162.0 completed a real structured-output
probe. This is an observed compatibility check, not a general quality ranking.

## Configuration and output

Note and provider commands accept `--config settings.json` and `--json`.
`conversations` commands instead require `--vault` directly, accept `--json`,
and manage their own `.brain-openkit/conversations.json` in that vault.
The following is an example of the note/provider configuration saved at the
checkout root:

~~~json
{
  "vault": "examples/vault",
  "cache_dir": ".cache/brain-openkit",
  "provider": "none",
  "laya_base_url": "http://127.0.0.1:8000",
  "kev_base_url": "http://127.0.0.1:8009",
  "kev_model": "kev-latest",
  "jev_base_url": "https://api.typesafe.ai",
  "jev_model": "jev-latest",
  "timeout": 10,
  "max_tokens": 1024,
  "limit": 5,
  "candidates": 20
}
~~~

Flags override JSON settings, which override defaults. JSON `vault` and
`cache_dir` resolve from the config file. An optional `base_url` config field
or `--base-url` overrides the selected HTTP provider's endpoint; Codex rejects it.
HTTP API keys are environment variables only. `--model` overrides the selected
Kev/Jev/ko-decision server model name or Codex model;
Laya explicitly uses its multilingual model. Classification/organization/source-note
paths are vault-relative; input drafts, taxonomy, datasets, and plans resolve
from the working directory.

The unreleased source also accepts `ko_decision_base_url` (default
`http://127.0.0.1:8010`), `ko_decision_model` (default
`mmetamong/ko-decision-roberta-large`), and `prompt_language` (`en` or `ko`,
default `en`) in JSON. `--model` selects the identity already served; it does not
download or replace weights.

Output is UTF-8, including redirected files and pipes. Rerank status is
`disabled`, `not_needed`, `complete`, or `unavailable`; unavailable
reranking returns BM25 with a reason. Classification failures do not fabricate
suggestions. See `brain-openkit <command> --help` for exact options.

## Quality evidence and limits

The [frozen bilingual synthetic evaluation](benchmarks/bilingual-v1/README.md)
contains 24 notes, 36 retrieval queries, and 18 held-out classification notes.
Labels were authored before inference and independently reviewed by another
agent, not the user. Holdout query paraphrases share development documents.

| Holdout retrieval, 24 queries | BM25 | Laya |
| --- | ---: | ---: |
| Recall@3 | 0.7500 | 0.7500 |
| MRR@3 | 0.7500 | 0.6042 |

Laya completed every rerank but **lowered reciprocal rank** in this run.
Holdout category accuracy was 0.6667; tag micro F1 was 0.4691, with 39 false
positive and four false negative tag decisions. These results support keeping
BM25 as the default and reviewing suggestions. See the
[actual run and limitations](benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md).

- Model probability/confidence signals are not guaranteed calibrated. There is
  no universal threshold for automatically applying metadata.
- Laya has a byte limit and sequence budget (`--max-tokens`, default 1024).
  **Exact tokenizer preflight for Laya is not implemented.** Reported truncation,
  dropped state, and collapsed options are rejected.
- ko-decision checks each complete tokenized pair before inference and rejects
  inputs over 512 tokens. Its relative option scores are not calibrated accuracy.
- A reranker cannot retrieve a relevant note absent from the BM25 candidates.
  Large-vault performance and general Korean/English quality remain unproven.
- Retrieval JSONL uses `{"query":"...","relevant":["note.md"]}` with existing
  vault-relative Markdown paths. Evaluation separates BM25/provider metrics,
  timings, and fallback counts.
- The design's separate real-vault acceptance targets—30 user-reviewed retrieval
  queries and 50 classification/tag examples—remain pending.

See [implementation notes](docs/implementation-notes.md) for host execution,
runtime versions, and verification status. The [original design](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)
and [agent workflow design](docs/superpowers/specs/2026-10-04-agent-workflows-design.md)
also describe intended behavior beyond completed validation.

## Roadmap

- [x] Source-preserving BM25 retrieval and optional Laya decisions.
- [x] Jev adapter and separate provider settings, with contract tests.
- [x] Interchangeable Laya/Kev local adapters with Hugging Face model setup.
- [x] Reviewed note plans, metadata/link updates, transactions, undo/recovery.
- [x] Source capture, wiki adoption, and host-assisted drafting/research skills.
- [x] Eight shared Claude Code/Codex skills and a read-only local web interface.
- [x] Broader frozen synthetic Korean/English evaluation with held-out labels.
- [ ] Live Jev service verification.
- [ ] User-reviewed real-vault retrieval and classification/tag acceptance.
- [ ] Exact tokenizer preflight for Laya and additional provider question types.
- [ ] Obsidian plugin UI.

See the [roadmap evidence matrix](docs/roadmap-evidence.md) for each original
item's implementation, proof, and remaining acceptance work.

## Contributing and license

Run `python -m unittest discover -s tests -v` in the CLI environment.
Tests use temporary vaults and local HTTP fixtures; real-model checks are
separate. See [CONTRIBUTING.md](CONTRIBUTING.md).

Original code and documentation use the [MIT License](LICENSE). External code,
weights, and hosted services retain their own licenses and terms. Inspired by
[AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
and independently implemented, without copying its code or templates.
Brain OpenKit is not affiliated with Obsidian, Laya, Kev, TypeSafe, or claude-obsidian.
See [ATTRIBUTION.md](ATTRIBUTION.md).
