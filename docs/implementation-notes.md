# CLI alpha implementation notes

Implementation date: 2026-10-04. Version: `0.1.0a1` (source installation; no PyPI release).

## Implemented scope

The CLI supports `index`, `search`, `classify`, `evaluate`, and `doctor`, with text
and JSON output. It reads UTF-8 Markdown and stores derived data in a vault-specific
SQLite cache. Search refreshes changed/deleted files before scoring. Korean words
and bigrams and normalized English words feed BM25. Source excerpts and inclusive,
one-based line positions are preserved.

The default search requires no model server. Explicit `--provider laya` reranks
the BM25 candidate passages through a separate HTTP server. Any failed candidate
causes the entire rerank to fall back to the original BM25 order. Classification
uses supplied category/tag descriptions and returns source passages and individual
decisions; it does not change the note. Conflicting passage categories require
review. Suggested tags are the union of positive passage decisions, not a
calibrated document probability.

## Referenced versions

- [`claude-obsidian` at `32ac5a0`](https://github.com/AgriciDaniel/claude-obsidian/tree/32ac5a02c4e082e4a5628ca810776375e134708e): retrieval, original-source handling and failure fallback informed the independent implementation. No source code or templates were copied.
- [Laya at `2e4d9c8`](https://github.com/NandhaKishorM/laya/tree/2e4d9c87e8b1621deb344eac7de5c7258f32f849), package `laya==0.3.26`: `GET /health` and `POST /v1/systemone`. Requests explicitly select `multilingual`.
- [Laya bundle revision `7b928d8`, `multilingual` subfolder](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148/multilingual): the weights used in the local smoke run. The runtime downloads the bundled repository rather than the standalone `laya-multilingual` model page.

## Real-model verification

The installed CLI was exercised against Laya 0.3.26 on macOS, CPU, four threads,
in a separate Python 3.12.11 environment (torch 2.14.1, transformers 5.18.0).
The server was bound to `127.0.0.1` with lazy loading. Plain `doctor` used health
only; `doctor --probe`, search reranking, taxonomy classification and retrieval
evaluation all completed with the multilingual route. Source-file hashes were
unchanged after the CLI flow. An unreachable server produced explicit BM25 fallback.

A separate Korean three-choice request took about 29.1 seconds including initial
loading/download, then about 119–124 ms for warm requests on this machine. Those
numbers describe this smoke run, not throughput or hardware requirements.

The four synthetic queries in `examples/evaluation.jsonl` returned recall@5 = 1.0
and truncated MRR = 1.0 for both BM25 and Laya. In one installed-CLI run the totals
were about 6 ms and 799 ms, respectively. All four model queries completed without
fallback. This fixture checks integration and metric reporting; it provides no
evidence of improved search quality. The default therefore remains BM25.

## Boundaries and remaining work

- `DecisionProvider.choose()` is the implemented common operation. Jev, score/noul
  questions, generation, note edits, and Obsidian UI integration are future work.
- Chunks target 1,200 characters at Markdown boundaries. A long single line remains
  intact to preserve source text and can exceed that target. Files are limited to
  2 MiB and classification to 200 passages.
- The HTTP request is bounded to 64 KiB. Exact tokenizer preflight is not implemented
  in this dependency-free client. The adapter rejects any server-reported token
  truncation, dropped state, question truncation or collapsed choices. Search then
  falls back; classification returns an error. Adjust `--max-tokens` deliberately
  within the server/model limit when needed.
- `LAYA_JEV_STRICT=1` removes fields required for validation and is unsupported.
  Provider probability and entropy confidence remain distinct, uncalibrated values.
- BM25 currently scores the cached corpus in memory. Large-vault performance has
  not been established. Sequential candidate decisions can add latency.
- Local tests cover Python 3.11 and 3.13. The checked-in Linux/macOS/Windows CI matrix
  must run on GitHub before claiming those platforms are verified.
- A user-reviewed Korean benchmark (at least 30 retrieval queries and 50 labeled
  classification/tag examples in the design) remains pending. Classification quality
  metrics and document-level probability calibration are not implemented.

See [README](../README.md) for installation and [examples](../examples/README.md)
for the fixture format. Evaluation aborts on excluded/unreadable relevance labels
or an incomplete index instead of silently treating those as retrieval failures.
