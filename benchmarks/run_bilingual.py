#!/usr/bin/env python3
"""Run a frozen synthetic suite; never adjust labels or ranking parameters."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain_openkit.evaluation import evaluate
from brain_openkit.kev import KevProvider
from brain_openkit.providers import LayaProvider, ProviderError
from brain_openkit.workflows import classify, validate_taxonomy

REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"


def corpus_paths(vault: Path) -> list[Path]:
    entries = list(vault.rglob("*"))
    if vault.is_symlink() or any(p.is_symlink() for p in entries):
        raise ValueError("Frozen benchmark corpus must not contain symbolic links")
    return sorted(p for p in entries if p.is_file() and p.suffix.lower() == ".md")


def digest_inputs(suite: Path) -> dict[str, str]:
    paths = corpus_paths(suite / "vault") + [
        suite / "retrieval-development.jsonl", suite / "retrieval-holdout.jsonl",
        suite / "classification.jsonl", suite / "taxonomy.json",
    ]
    return {p.relative_to(suite).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n")
            if line.strip()]


def validate_suite(suite: Path) -> dict:
    frozen = json.loads((suite / "manifest.json").read_text(encoding="utf-8"))
    if digest_inputs(suite) != frozen["sha256"]:
        raise ValueError("Benchmark inputs differ from the reviewed, frozen manifest")
    labels = read_jsonl(suite / "classification.jsonl")
    taxonomy = validate_taxonomy(json.loads((suite / "taxonomy.json").read_text(encoding="utf-8")))
    paths = {p.relative_to(suite / "vault").as_posix() for p in corpus_paths(suite / "vault")}
    if {row["path"] for row in labels} != paths or len(labels) != len(paths):
        raise ValueError("Classification labels must cover each note exactly once")
    for row in labels:
        if (row["category"] not in taxonomy["categories"]
                or not set(row["tags"]) <= set(taxonomy["tags"])
                or len(set(row["tags"])) != len(row["tags"])
                or row["split"] not in {"development", "holdout"}
                or row["language"] not in {"ko", "en"}):
            raise ValueError("Invalid classification label")
    ids, queries = set(), set()
    for split in ("development", "holdout"):
        rows = read_jsonl(suite / f"retrieval-{split}.jsonl")
        if not rows:
            raise ValueError("Each query split must be nonempty")
        for row in rows:
            if (row["id"] in ids or row["query"] in queries or not row["query"].strip()
                    or not row["relevant"] or not set(row["relevant"]) <= paths
                    or row["language"] not in {"ko", "en"}):
                raise ValueError("Invalid or overlapping retrieval labels")
            ids.add(row["id"])
            queries.add(row["query"])
    return frozen


def _f1(tp: int, fp: int, fn: int) -> float:
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0


def _classification_metrics(rows: list[dict], taxonomy: dict) -> dict:
    if not rows:
        raise ValueError("Cannot evaluate an empty classification split")
    categories, tags = taxonomy["categories"], taxonomy["tags"]
    category_counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in categories}
    tag_counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in tags}
    correct, exact_tags, sample_f1 = 0, 0, []
    for row in rows:
        result = row.get("result") or {}
        gold, predicted = row["category"], result.get("category")
        correct += predicted == gold
        for name, counts in category_counts.items():
            counts["tp"] += predicted == name and gold == name
            counts["fp"] += predicted == name and gold != name
            counts["fn"] += predicted != name and gold == name
        gold_tags, predicted_tags = set(row["tags"]), set(result.get("tags", []))
        exact_tags += bool(result) and gold_tags == predicted_tags
        tp, fp, fn = (len(gold_tags & predicted_tags), len(predicted_tags - gold_tags),
                      len(gold_tags - predicted_tags))
        sample_f1.append(1.0 if result and not gold_tags and not predicted_tags else _f1(tp, fp, fn))
        for name, counts in tag_counts.items():
            counts["tp"] += name in gold_tags and name in predicted_tags
            counts["fp"] += name not in gold_tags and name in predicted_tags
            counts["fn"] += name in gold_tags and name not in predicted_tags
    for counts in list(category_counts.values()) + list(tag_counts.values()):
        counts["f1"] = _f1(counts["tp"], counts["fp"], counts["fn"])
    totals = {key: sum(row[key] for row in tag_counts.values()) for key in ("tp", "fp", "fn")}
    return {
        "note_count": len(rows), "error_count": sum(bool(r.get("error")) for r in rows),
        "review_required_count": sum(bool((r.get("result") or {}).get("review_required")) for r in rows),
        "category_accuracy": correct / len(rows),
        "category_macro_f1": statistics.mean(c["f1"] for c in category_counts.values()),
        "category_per_class": category_counts,
        "tag_micro_f1": _f1(**totals),
        "tag_micro_precision": totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0,
        "tag_micro_recall": totals["tp"] / (totals["tp"] + totals["fn"]) if totals["tp"] + totals["fn"] else 0.0,
        "tag_false_positives": totals["fp"], "tag_false_negatives": totals["fn"],
        "tag_macro_f1": statistics.mean(c["f1"] for c in tag_counts.values()) if tags else 0.0,
        "tag_sample_f1": statistics.mean(sample_f1), "tag_exact_match": exact_tags / len(rows),
        "tag_per_class": tag_counts,
        "elapsed_ms": sum(r["elapsed_ms"] for r in rows),
    }


def classification_metrics(rows: list[dict], taxonomy: dict) -> dict:
    result = _classification_metrics(rows, taxonomy)
    result["by_language"] = {}
    for language in ("ko", "en"):
        selected = [row for row in rows if row.get("language") == language]
        if selected:
            result["by_language"][language] = _classification_metrics(selected, taxonomy)
    return result


class RecordingProvider:
    def __init__(self, provider, stream):
        self.provider, self.stream, self.phase = provider, stream, "warmup"
        self.name = getattr(provider, "name", type(provider).__name__)
        self.timings: list[float] = []
        self.measured_timings: list[float] = []
        self.warmup_timings: list[float] = []
        self.models: set[str] = set()
        self.errors = 0

    def choose(self, state, question, choices):
        started = perf_counter()
        record = {"phase": self.phase, "state": state, "question": question, "choices": choices}
        try:
            decision = self.provider.choose(state, question, choices)
            record["decision"] = asdict(decision)
            self.models.add(decision.model)
            return decision
        except ProviderError as exc:
            self.errors += 1
            record["error"] = str(exc)
            raise
        finally:
            record["wall_elapsed_ms"] = (perf_counter() - started) * 1000
            self.timings.append(record["wall_elapsed_ms"])
            phase_timings = self.warmup_timings if self.phase == "warmup" else self.measured_timings
            phase_timings.append(record["wall_elapsed_ms"])
            self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.stream.flush()


def annotate_retrieval(report: dict, labels: list[dict]) -> None:
    for row, label in zip(report["queries"], labels):
        row.update({"id": label["id"], "language": label["language"]})
        for key in ("baseline", "requested"):
            if row[key] is not None:
                row[key]["misses"] = sorted(set(row["relevant"]) - set(row[key]["paths"]))
                row[key]["false_matches"] = [p for p in row[key]["paths"] if p not in row["relevant"]]
    report["by_query_language"] = {}
    for language in ("ko", "en"):
        report["by_query_language"][language] = {}
        for key in ("baseline", "requested"):
            rows = [r[key] for r in report["queries"] if r["language"] == language and r[key] is not None]
            report["by_query_language"][language][key] = None if not rows else {
                "query_count": len(rows), "recall_at_k": statistics.mean(r["recall_at_k"] for r in rows),
                "mrr": statistics.mean(r["reciprocal_rank"] for r in rows),
            }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "benchmarks" / "bilingual-v1")
    parser.add_argument("--output", type=Path, required=True, help="New directory, refuses overwrite")
    parser.add_argument("--provider", choices=("none", "laya", "kev", "ko-decision"), default="none")
    parser.add_argument("--base-url", help="Defaults to localhost port 8000 (Laya), 8009 (Kev), or 8010 (KoDecision)")
    parser.add_argument("--model", help="Server model identifier; Laya supports only multilingual")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--prompt-language", choices=("en", "ko"), default="en")
    parser.add_argument("--runtime-metadata", type=Path)
    args = parser.parse_args(argv)
    if args.provider == "laya" and args.model not in (None, "multilingual"):
        parser.error("Laya supports only --model multilingual")
    ports = {"laya": 8000, "kev": 8009, "ko-decision": 8010}
    models = {"laya": "multilingual", "kev": "kev-latest",
              "ko-decision": "mmetamong/ko-decision-roberta-large"}
    model = args.model or models.get(args.provider)
    base_url = args.base_url or (f"http://127.0.0.1:{ports[args.provider]}" if args.provider in ports else None)
    suite = args.suite.resolve()
    manifest = validate_suite(suite)
    before = digest_inputs(suite)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "suite": manifest["suite"], "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_manifest": manifest, "client_python": platform.python_version(),
        "platform": platform.platform(), "machine": platform.machine(),
        "ranking": {"limit": 3, "candidates": 8, "tuned_on_this_suite": False},
        "provider": args.provider,
        "requested_model": model, "observed_models": [],
        "base_url": base_url, "timeout_seconds": args.timeout,
        "prompt_language": args.prompt_language,
        "limitations": ["Authored synthetic corpus, not a random population sample or user-reviewed real vault",
                        "Query holdout shares the corpus; classification holdout has different notes",
                        "One run, one machine, warm inference; no statistical superiority claim"],
    }
    if args.runtime_metadata:
        report["server_runtime"] = json.loads(args.runtime_metadata.read_text(encoding="utf-8"))
    taxonomy = json.loads((suite / "taxonomy.json").read_text(encoding="utf-8"))
    with (args.output / "decisions.jsonl").open("w", encoding="utf-8") as raw:
        provider = None
        if args.provider != "none":
            if args.provider == "laya":
                underlying = LayaProvider(base_url=base_url, timeout=args.timeout)
            elif args.provider == "kev":
                underlying = KevProvider(base_url=base_url, model=model, timeout=args.timeout)
            else:
                from brain_openkit.ko_decision import KoDecisionProvider
                underlying = KoDecisionProvider(base_url=base_url, model=model, timeout=args.timeout)
            report["health_before"] = underlying.health()
            provider = RecordingProvider(underlying, raw)
            if args.prompt_language == "ko":
                provider.choose("마크다운 노트 검색에 관한 로컬 검증 메모입니다.", "노트 검색을 설명합니까?",
                                {"A": "예", "B": "아니요"})
            else:
                provider.choose("A local smoke note about Markdown search.", "Does it describe note search?",
                                {"A": "Yes", "B": "No"})
            report["first_request_ms"] = provider.timings[-1]
            report["health_after_warmup"] = underlying.health()
            if (args.provider == "laya"
                    and report["health_after_warmup"].get("revisions", {}).get("multilingual") != REVISION):
                raise ValueError("Actual multilingual checkpoint differs from the frozen evaluation revision")
        with tempfile.TemporaryDirectory(prefix="brain-openkit-benchmark-cache-") as cache:
            report["retrieval"] = {}
            for split in ("development", "holdout"):
                if provider:
                    provider.phase = f"retrieval-{split}"
                dataset = suite / f"retrieval-{split}.jsonl"
                measured = evaluate(suite / "vault", dataset, cache_dir=Path(cache), provider=provider,
                                    limit=3, candidates=8, prompt_language=args.prompt_language)
                measured["dataset"] = dataset.name
                annotate_retrieval(measured, read_jsonl(dataset))
                report["retrieval"][split] = measured
                print(f"Measured retrieval {split}: {measured['query_count']} queries", flush=True)
            report["classification"] = None
            if provider:
                results = []
                for row in read_jsonl(suite / "classification.jsonl"):
                    provider.phase = f"classification-{row['split']}:{row['path']}"
                    started = perf_counter()
                    measured = dict(row)
                    try:
                        measured["result"] = classify(suite / "vault", Path(row["path"]), taxonomy, provider,
                                                      prompt_language=args.prompt_language)
                    except (ProviderError, ValueError) as exc:
                        measured["result"], measured["error"] = None, str(exc)
                    measured["elapsed_ms"] = (perf_counter() - started) * 1000
                    results.append(measured)
                report["classification"] = {
                    "results": results,
                    "all": classification_metrics(results, taxonomy),
                    **{split: classification_metrics([r for r in results if r["split"] == split], taxonomy)
                       for split in ("development", "holdout")},
                }
                report["requests"] = {
                    "count_including_warmup": len(provider.timings), "error_count": provider.errors,
                    "count_excluding_warmup": len(provider.measured_timings),
                    "warmup_count": len(provider.warmup_timings),
                    "warm_median_ms": statistics.median(provider.measured_timings) if provider.measured_timings else None,
                    "warm_min_ms": min(provider.measured_timings, default=None),
                    "warm_max_ms": max(provider.measured_timings, default=None),
                    "latency_scope": "Client wall time for decision calls, including failed calls; warmups excluded",
                }
                report["observed_models"] = sorted(provider.models)
                report["health_after"] = underlying.health()
    after = digest_inputs(suite)
    report["source_preservation"] = {"unchanged": before == after, "sha256_before": before, "sha256_after": after}
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if before != after:
        raise RuntimeError("Benchmark inputs changed during evaluation")
    print(f"Report written to {args.output / 'report.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
