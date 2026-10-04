# Synthetic examples

Every note in `examples/vault/` was written for this repository. They do not
contain a real personal vault, private observations, or credentials.

The four notes mix Korean and English:

- `examples/vault/local-search.md`: Korean notes about retrieval evaluation.
- `examples/vault/garden.md`: an invented Korean plant-care journal.
- `examples/vault/provider-notes.md`: English notes about decision providers.
- `examples/vault/reading.md`: an English journal about an invented book.

`examples/taxonomy.json` contains three category descriptions and three
independent tag descriptions for classification examples.

`examples/evaluation.jsonl` contains four hand-written queries and expected
note paths, relative to `examples/vault/`. For example, `garden.md` refers to
`examples/vault/garden.md`. Each JSONL row has this shape:

```json
{"query": "바질 화분에 물을 주는 시점", "relevant": ["garden.md"]}
```

This tiny dataset is a **smoke check for the retrieval/evaluation workflow**.
It is not a quality benchmark, held-out test set, or evidence that Laya improves
retrieval. Do not use its scores to make Korean/English performance claims.

Evaluation reports macro-averaged recall at the requested result limit and
mean reciprocal rank within that same limit. With a provider selected, the
report separates BM25 from the requested reranking run and identifies
fallbacks. Timings cover search calls and can include index checks, cache
effects, and model loading; they are not isolated model-inference benchmarks.

See the [project README](../README.md) for the current installation and CLI
instructions. The example vault can be copied to a temporary directory for
experiments; evaluation does not require modifying the source notes.
