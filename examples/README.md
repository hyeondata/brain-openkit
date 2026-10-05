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
It is not a quality benchmark, held-out test set, or evidence that Laya or Kev improves
retrieval. Do not use its scores to make Korean/English performance claims.

Evaluation reports macro-averaged recall at the requested result limit and
mean reciprocal rank within that same limit. With a provider selected, the
report separates BM25 from the requested reranking run and identifies
fallbacks. Timings cover search calls and can include index checks, cache
effects, and model loading; they are not isolated model-inference benchmarks.

See the [project README](../README.md) for the current installation and CLI
instructions. The example vault can be copied to a temporary directory for
experiments; evaluation does not require modifying the source notes.

With a local server running, the same examples work with either provider:

```bash
brain-openkit search "reading journal comets" --vault examples/vault --provider laya --timeout 120 --json
brain-openkit search "reading journal comets" --vault examples/vault --provider kev --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider kev --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider kev --timeout 120 --json
```

Start with `doctor --provider laya --probe --timeout 120` or
`doctor --provider kev --probe --timeout 120`
to check synthetic inference. A successful HTTP health check alone does not
establish that weights have loaded. See the [local model guide](../docs/local-models.md)
for setup and recorded verification.
