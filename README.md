<h1 align="center">Brain OpenKit</h1>

<p align="center">
  <strong>An open-source second-brain toolkit for Obsidian.</strong><br>
  Local search and organization for Obsidian, with replaceable decision providers.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/status-alpha-d97706" alt="Alpha">
  <a href="https://huggingface.co/convaiinnovations/laya-multilingual"><img src="https://img.shields.io/badge/optional%20model-Laya-0f766e" alt="Optional model: Laya"></a>
</p>

<p align="center">
  English · <a href="README.ko.md">한국어</a><br>
  <a href="#what-it-does">Overview</a> · <a href="#install-from-source">Install</a> ·
  <a href="#optional-laya-server">Laya</a> · <a href="#roadmap">Roadmap</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

> **Source-installable alpha (0.1.0a1).** The read-only CLI, BM25 search, Laya
> adapter, and tests are implemented. Laya has been exercised on synthetic
> examples; real-vault retrieval quality is not established. There is no
> published PyPI package. Use a source checkout containing the CLI.

Brain OpenKit finds Markdown passages and returns original paths, line
numbers, and excerpts. **Search defaults to BM25, without a model or API key.**
Opt into a local [Laya](https://github.com/NandhaKishorM/laya) server for
reranking and suggestions from your existing categories and tags.

## What it does

- Refresh changed/deleted notes and search with 1-based, inclusive source lines.
- Rerank with multilingual Laya; any candidate failure preserves BM25 ordering.
- Suggest among up to 10 categories and evaluate up to 30 tags independently.
  Conflicting passage-level categories remain visible.
- Check server health, optionally probe inference, and evaluate labeled queries.

Source notes are read only; SQLite indexes are written to a separate cache.
The provider protocol currently exposes **choose only**. Jev, generic score
and noul questions, note edits, generation, and an Obsidian UI are future work.

~~~mermaid
flowchart LR
    A[Markdown vault] --> B[Local index]
    B --> C[BM25 candidates]
    C --> D[Default BM25 results]
    C -. Opt in .-> E[Laya local server]
    E --> F[Validate every decision]
    F --> G[Source excerpts and recommendations]
    D --> G
    F -. Model failure .-> D
~~~

## Install from source

Use **Python 3.11 or newer**. From the checkout containing this CLI, run these
macOS/Linux commands; substitute a newer Python executable if needed:

~~~bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
brain-openkit --version
~~~

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.
The CLI has no third-party runtime dependencies; installation may download
build tooling. Laya is a separate optional runtime.

## Try the included notes

Run from the checkout root with the CLI environment active:

~~~bash
brain-openkit index --vault examples/vault
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault
brain-openkit search "reading journal comets" --vault examples/vault --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --json
~~~

Search and evaluation default to `--provider none` and refresh the index.
No model server is needed. Cache defaults to `.cache/brain-openkit` under
the working directory; use `--cache-dir` to change it. The
[four synthetic notes](examples/README.md) are a smoke fixture, not a benchmark.

## Optional Laya server

Use a **separate environment and terminal**. The tested runtime is Laya
**0.3.26**, Python **3.12**, and CPU inference:

~~~bash
python3.12 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=0 \
laya-serve
~~~

This loads lazily. `LAYA_MODELS` selects preload targets, not access
restrictions. Brain OpenKit explicitly requests `multilingual`; the first
inference downloads/loads that checkpoint. Initial dependencies and weights
need network access, disk space, and model runtime memory.

In the **CLI terminal**, with `.venv` active:

~~~bash
brain-openkit doctor
brain-openkit doctor --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --json
~~~

`doctor` checks health only; `--probe` runs synthetic inference and can
trigger downloading. Classification defaults to Laya. Its relative note path
resolves **inside --vault**: use `local-search.md` above. Taxonomy and dataset
arguments resolve from the working directory.

If first loading exceeds the default 10-second timeout, wait for loading to
finish and retry, or pass `--timeout 120`. Use `--base-url` for another
address. If server authentication is enabled, set the same `LAYA_API_KEY`
in both terminals. These public weights need no Hugging Face token or Jev key.

## Configuration and output

Each subcommand accepts `--config settings.json` and `--json`.
Standard output and error use UTF-8, including redirected files and pipes.
Example configuration saved at the checkout root:

~~~json
{
  "vault": "examples/vault",
  "cache_dir": ".cache/brain-openkit",
  "provider": "none",
  "base_url": "http://127.0.0.1:8000",
  "timeout": 10,
  "max_tokens": 1024,
  "limit": 5,
  "candidates": 20
}
~~~

~~~bash
brain-openkit search "reading journal" --config settings.json --json
brain-openkit classify local-search.md --config settings.json --provider laya --taxonomy examples/taxonomy.json --json
~~~

Flags override JSON settings, which override defaults. JSON `vault` and
`cache_dir` paths resolve from the configuration file. Keep keys in
`LAYA_API_KEY`, not JSON or the vault. Providers are `none` and `laya`;
the adapter fixes its route to `multilingual`.

Reranking status is `disabled`, `not_needed`, `complete`, or
`unavailable`. Unavailable reranking returns BM25 with a fallback reason;
classification failures do not fabricate suggestions. JSON preserves source
locations, decisions, and handled runtime errors. See
`brain-openkit <command> --help` for options.

## Limits and evaluation

- Model probabilities are ranking signals, not guaranteed calibrated
  probabilities. No confidence threshold automatically changes notes.
- Requests have byte limits and a sequence budget (`--max-tokens`, default
  1024). **Exact tokenizer preflight is not implemented.** Responses reporting
  dropped state, truncated questions, or collapsed options are rejected.
- The default endpoint keeps inference on a local server. A remote
  `--base-url` sends selected passages there. There is no cloud failover.
- Evaluation JSONL uses `{"query": "...", "relevant": ["note.md"]}`.
  Labels must identify existing vault Markdown files. Reports separate BM25
  and requested-provider recall@k, MRR within k, timing, and fallback counts.
  Four bundled queries do not establish Korean/English quality or an
  improvement over BM25.

See [implementation and validation notes](docs/implementation-notes.md)
for tested versions and results. The
[original design](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)
also contains future capabilities; this README describes the implemented CLI.

## Roadmap

- [x] Read-only indexing and BM25 retrieval with source locations.
- [x] Optional multilingual Laya reranking and category/tag suggestions.
- [x] Source-installable CLI, automated tests, and smoke evaluation.
- [ ] Broader Korean/English evaluation with held-out labels.
- [ ] Jev adapter and provider-specific configuration.
- [ ] Reviewed metadata/link updates with recovery.
- [ ] Source ingestion, wiki creation, and optional generation.
- [ ] Obsidian plugin or local web interface.

## Contributing

Run `python -m unittest discover -s tests -v` in the CLI environment.
Tests use temporary vaults and local HTTP fixtures, without Laya weights.
Real model checks are separate. See [CONTRIBUTING.md](CONTRIBUTING.md).
Keep private notes and keys out of contributions.

## License and acknowledgements

Original code and documentation use the [MIT License](LICENSE).
External code and weights retain their own licenses.

Inspired by [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)'s
source-linked workflows and independently implemented. Brain OpenKit is not
affiliated with Obsidian, Laya, TypeSafe, or claude-obsidian.
See [ATTRIBUTION.md](ATTRIBUTION.md) for pinned references and license boundaries.
