# Bilingual synthetic evaluation v1

This is an authored, openly inspectable integration and error-analysis suite. It
contains 24 original short notes (12 Korean, 12 English), 36 retrieval questions
(18 Korean, 18 English), and category/tag labels for every note. None of the text
comes from a private vault. It is not a representative quality benchmark.

## Label protocol

An authoring agent wrote notes, retrieval relevance labels, and classification
labels before running retrieval or a model. A different agent reviewed every
label and the taxonomy without seeing rankings. The review added two missing
`maintenance` tags for explicit restore drills and clarified how maintenance
differs from routine file copying. `manifest.json` freezes the resulting input
SHA-256 hashes, timestamp, counts, and ranking settings. The runner refuses changed
inputs. Labels were not corrected to fit predictions after measurement.

- Retrieval: 12 development questions and 24 holdout questions. The splits share
  all 24 documents; several holdout questions are close paraphrases of development
  questions. This is a held-out **query** set, not unseen documents or topics.
- Classification: six development notes and 18 different holdout notes. The six
  categories concern primary purpose; a research note using a laptop is still
  research. Four independent tags deliberately cross category boundaries.
- Queries include cross-language paraphrases. The lexical candidate stage may
  miss them entirely; a reranker cannot recover an absent candidate.
- Every query has one specifically relevant note. This simplifies judging and
  does not test multi-document synthesis. Other returned notes are reported as
  `false_matches` under those explicit labels, even if tangentially related.
- Fixed settings: top 3, at most 8 BM25 candidate passages. Neither core ranking
  nor these parameters were tuned on this suite, including development results.

The independent review is an agent review, not human or user validation. The
original design's user-reviewed real-vault target (30 retrieval queries and 50
classification/tag examples) remains separate and is not satisfied by this suite.

## Reproduce

From the repository root, with Python 3.11 or later:

```sh
python benchmarks/run_bilingual.py --provider none --output /tmp/bilingual-bm25
python benchmarks/run_bilingual.py --provider laya \
  --base-url http://127.0.0.1:18080 --output /tmp/bilingual-laya
```

The output directory must not exist. BM25 requires no model. Laya must already be
running locally; the runner makes one explicitly recorded warmup request and
requires the multilingual checkpoint reported by health to equal
`7b928d828b7b0e022f929d9bd2e44165aa270148`. Set `LAYA_REVISION` to that value when
starting the server. The recorded run used `laya==0.3.26`. It used a previously
downloaded cache with `HF_HUB_OFFLINE=1`, CPU, four threads, lazy model loading,
and only `127.0.0.1:18080`. It did not contact a hosted inference service.

Optional `--runtime-metadata FILE.json` includes independently collected server
package/device metadata in the report. The client cannot infer package versions
from the health endpoint. `report.json` includes actual health responses and
pre/post source hashes; `decisions.jsonl` includes each exact request state,
question, choices, returned decision, and client elapsed time.

## Metric definitions

Retrieval uses the existing CLI evaluator: macro recall@3 and reciprocal rank
truncated at 3. BM25 is measured first for each question, then the requested
provider refreshes the index and reranks candidates. These orders favor a warm
cache for the provider. A failed candidate causes an explicit full BM25 fallback;
the report counts fallbacks separately. Empty lexical candidates are `not_needed`,
not successful model queries.

Classification accuracy counts absent/conflicting categories and execution
errors as incorrect. Category macro F1 averages all six fixed categories. Tag
micro F1 aggregates TP/FP/FN across all four tags; macro F1 gives each tag equal
weight. Sample F1 averages note-level tag F1, treating a successfully predicted
empty set against an empty label set as 1. Exact match requires the whole tag set
to match. Execution errors remain in all denominators and count as missed gold
tags; they cannot become successful empty-set matches. Unused-class F1 is 0.

The checked-in report records one run on one machine, without confidence
intervals, power analysis, threshold calibration, or a claim of general quality
improvement. Latency includes Python workflow/index overhead and sequential model
calls, not just neural inference. Source hashes must be identical before and
after the run. No model decisions apply edits to the notes.

See [the measured results](reports/2026-10-04/RESULTS.md) and its raw JSON files
for failures as well as successful predictions.
