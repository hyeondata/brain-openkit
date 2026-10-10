# KoDecision evidence — 2026-10-05

See the verification report in [English](../../../docs/ko-decision-verification-2026-10-05.md)
or [한국어](../../../docs/ko-decision-verification-2026-10-05.ko.md).

- `ko-en-cpu/`, `ko-ko-cpu/`: actual PyTorch CPU model runs.
- `ko-en-mps/`, `ko-ko-mps/`: actual PyTorch MPS/float32 runs.
- `kev-en-mlx/`, `kev-ko-mlx/`: actual Kev 0.8B MLX/bfloat16 comparison runs.
- Each run contains `report.json` and `decisions.jsonl`, with one warmup and
  351 measured requests. Instruction language is `en` or `ko`; the frozen
  taxonomy descriptions remain English. GPU runs did not overlap.
- `summary.json` aggregates holdout metrics and measured-request latency.
- `runtime*.json` record library versions, model revisions, and model-file hashes.
- `functional.json` records actual CLI health/probe/search/classification/eval
  and injected-outage checks.
- `limits-source.json` and `limits-wheel.json` record actual oversized-input
  handling and approved metadata apply/undo from source and the installed wheel.
- `actual-boundaries.json` records real 511/512/513-token pair checks and model
  card example agreement with direct CPU inference.
- `direct-smoke.json` records direct CPU model inference. Its
  `inference_and_hashing_seconds` includes file hashing, so it is not a model
  latency measurement.
- `tests-311.txt` and `tests-313.txt` contain the final local unit-test summaries.
- `sha256.json` hashes the other evidence files, excluding itself.

Reports use only synthetic/public benchmark text. Machine-specific paths in
functional outputs are normalized; timings and model responses are preserved.
The wheel used for local verification has the development checkout's existing
`0.2.0a4` version string; these results do not describe the published release
assets. The directory contains no model weights or private vault contents.
