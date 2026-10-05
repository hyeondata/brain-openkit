# Actual Laya run — 2026-10-04

The run does **not** establish an improvement over BM25. On this small synthetic
holdout, Laya preserved aggregate recall@3 but lowered reciprocal rank, and tag
suggestions included many false positives. Keep BM25 as the default and review
classification suggestions before any write. No labels, thresholds, or ranking
settings were changed after inspecting these results.

## Retrieval

| Split | Questions | BM25 recall@3 | Laya recall@3 | BM25 MRR@3 | Laya MRR@3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 12 | 1.0000 | 0.9167 | 1.0000 | 0.9167 |
| Holdout | 24 | 0.7500 | 0.7500 | 0.7500 | 0.6042 |
| Holdout: Korean query | 12 | 0.6667 | 0.7500 | 0.6667 | 0.6111 |
| Holdout: English query | 12 | 0.8333 | 0.7500 | 0.8333 | 0.5972 |

All 36 requested reranks completed. There were zero provider errors and zero
fallback queries. A completed call says nothing by itself about relevance quality.

The raw output preserves every returned top-three path, missed expected path,
and false match. Specific failures and improvements include:

- `hold-01` (Korean request for a recoverable Git copy) and `hold-07` (English
  request for source URL/line citations) entered the top three after Laya; both
  correct notes were already in the eight lexical candidates.
- `hold-14` (cancelled train itinerary) and `hold-16` (verified travel photo
  copies) were first under BM25, then disappeared from Laya's top three despite
  remaining in its candidate input.
- `hold-08`, `hold-12`, `hold-19`, and `hold-20` are cross-language questions whose
  correct notes never reached the lexical candidate set. The reranker could not
  retrieve them. This is a candidate-recall limitation of the current pipeline.
- `dev-11`, concerning private notes sent to external AI, lost the relevant
  private-vault note after reranking and returned passport/router topics instead.

## Category and tag suggestions

| Split | Notes | Category accuracy | Category macro F1 | Tag micro F1 | Tag macro F1 | Exact tag set |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 6 | 0.5000 | 0.3611 | 0.6000 | 0.5833 | 0.3333 |
| Holdout | 18 | 0.6667 | 0.6206 | 0.4691 | 0.4661 | 0.0000 |
| All (descriptive only) | 24 | 0.6250 | 0.5710 | 0.5045 | 0.4991 | 0.0833 |

No classification call failed or produced a multi-passage category conflict.
Each note fits one passage. All three holdout research notes were assigned the
wrong category, so their category F1 is 0. The holdout tag decisions contain
39 false positives and four false negatives across the four labels: privacy
10 FP/2 FN, backup 13 FP/0 FN, offline 8 FP/0 FN, maintenance 8 FP/2 FN.

For example, the alternative train itinerary incorrectly received `backup`,
despite the taxonomy explicitly limiting that tag to digital file/database
copies. The SQLite cache also incorrectly received it. These results support
manual review; they do not support automatically applying metadata at a universal
probability threshold. No probability calibration was evaluated.

## Runtime and preservation evidence

Run: 2026-10-04 14:25:32–14:26:19 UTC, macOS arm64, client Python 3.13.1;
server Python 3.12.11, CPU with four threads, `laya==0.3.26`, torch 2.14.1,
transformers 5.18.0. The health response reports the multilingual checkpoint at
`7b928d828b7b0e022f929d9bd2e44165aa270148` from the `convaiinnovations/laya`
bundle. The server used its existing cache in offline mode on loopback.

- First model request: 4.712 seconds, including process-local lazy model load
  from the existing cache; this was not a model download.
- 352 recorded requests: 1 warmup, 64 development retrieval candidates,
  167 holdout retrieval candidates, and 120 classification/tag decisions.
- Warm per-request client median: 115.6 ms; observed range: 88.7–373.5 ms.
- Development retrieval total: BM25 55.2 ms versus Laya 7,944.1 ms.
- Holdout retrieval total: BM25 90.4 ms versus Laya 19,079.8 ms.
- Classification total: 15,729.7 ms for 24 notes and 120 sequential decisions.
- All 28 input file SHA-256 hashes match before and after evaluation. The 24
  vault notes were unchanged. No model-directed source edits were performed.

These timings include client and workflow overhead. BM25 ran first for each
query, so the Laya phase reused a warm index. They are observations from one
machine and one run, not a throughput benchmark or a hardware requirement.

## Evidence and limits

- [Aggregate/per-query/per-note report](report.json)
- [Every model request and validated response](decisions.jsonl)
- [Frozen inputs and review record](../../manifest.json)
- [Method, splits, metric definitions, and reproduction](../../README.md)

The corpus is authored synthetic data and reviewed by another agent, not by the
user. Holdout query paraphrases share the same notes as development, and the
classification holdout has only 18 notes. No significance or superiority claim
is justified. The separate real-vault target of 30 user-reviewed retrieval
queries and 50 classification/tag examples remains unverified.
