"""Small, explicit retrieval evaluations against user-reviewed relevance labels."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from time import perf_counter
import unicodedata

from . import workflows
from .providers import DecisionProvider
from .vault import read_note, validate_vault


def _read_dataset(vault: Path, dataset: Path, cache_dir: Path) -> list[dict]:
    try:
        lines = dataset.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Dataset could not be read as UTF-8: {dataset}") from exc
    rows = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        prefix = f"Dataset line {number}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{prefix}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{prefix}: expected an object with query and relevant fields")
        query, labels = row.get("query"), row.get("relevant")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{prefix}: query must be a nonempty string")
        query = query.strip()
        if len(query) > 8000 or len(unicodedata.normalize("NFKC", query)) > 8000:
            raise ValueError(f"{prefix}: query must contain at most 8000 normalized characters")
        try:
            query.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError(f"{prefix}: query must be valid UTF-8 text") from exc
        if not isinstance(labels, list) or not labels:
            raise ValueError(f"{prefix}: relevant must be a nonempty list of note paths")
        relevant = []
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"{prefix}: each relevant label must be a relative Markdown path")
            relative = PurePosixPath(label)
            if (
                relative.is_absolute() or PureWindowsPath(label).drive
                or "\\" in label or "\x00" in label or ".." in relative.parts
                or relative.suffix.lower() != ".md"
            ):
                raise ValueError(f"{prefix}: relevant paths must be relative Markdown paths inside the vault")
            target = vault.joinpath(*relative.parts)
            try:
                if target.resolve(strict=True).is_relative_to(cache_dir):
                    raise ValueError("configured cache notes are excluded")
                if not read_note(vault, target):
                    raise ValueError("empty notes are not indexable")
            except (OSError, RuntimeError, ValueError) as exc:
                raise ValueError(
                    f"{prefix}: relevant note must be readable, nonempty UTF-8 Markdown "
                    "outside excluded directories, symbolic links and the configured cache"
                ) from exc
            normalized = relative.as_posix()
            if normalized not in relevant:
                relevant.append(normalized)
        rows.append({"query": query, "relevant": relevant})
    if not rows:
        raise ValueError("Dataset is empty; provide at least one query with relevance labels")
    return rows


def _run_query(vault, row, *, cache_dir, provider, limit, candidates, prompt_language):
    started = perf_counter()
    result = workflows.search(
        vault, row["query"], cache_dir=cache_dir, provider=provider,
        limit=limit, candidates=candidates, prompt_language=prompt_language,
    )
    if result["index"]["errors"]:
        raise ValueError("Indexing failed; evaluation requires a complete readable vault")
    elapsed_ms = (perf_counter() - started) * 1000
    paths = [hit["path"] for hit in result["results"][:limit]]
    relevant = set(row["relevant"])
    reciprocal_rank = next((1 / rank for rank, path in enumerate(paths, 1) if path in relevant), 0.0)
    measured = {
        "paths": paths,
        "recall_at_k": len(relevant.intersection(paths)) / len(relevant),
        "reciprocal_rank": reciprocal_rank,
        "elapsed_ms": elapsed_ms,
        "rerank_status": result["rerank_status"],
        "model_used": result["rerank_status"] == "complete" and any(
            hit.get("model_score") is not None for hit in result["results"]
        ),
    }
    for field in ("fallback_reason", "provider", "model", "usage"):
        if field in result:
            measured[field] = result[field]
    return measured


def _summarize(measurements: list[dict]) -> dict:
    count = len(measurements)
    statuses = {}
    for measurement in measurements:
        status = measurement["rerank_status"]
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "query_count": count,
        "recall_at_k": sum(row["recall_at_k"] for row in measurements) / count,
        "mrr": sum(row["reciprocal_rank"] for row in measurements) / count,
        "elapsed_ms": sum(row["elapsed_ms"] for row in measurements),
        "model_query_count": sum(row["model_used"] for row in measurements),
        "fallback_query_count": statuses.get("unavailable", 0),
        "rerank_status_counts": statuses,
    }


def evaluate(
    vault: Path,
    dataset: Path,
    *,
    cache_dir: Path,
    provider: DecisionProvider | None = None,
    limit: int = 5,
    candidates: int = 20,
    prompt_language: str = "en",
) -> dict:
    """Compare BM25 with an optional provider; MRR is truncated to ``limit``.

    Dataset labels are vault-relative Markdown paths. All rows are validated
    before any model request. Provider failures remain visible as BM25 fallback
    results rather than being counted as completed model inference.
    """
    if prompt_language not in ("en", "ko"):
        raise ValueError("prompt_language must be en or ko")
    for name, value in (("limit", limit), ("candidates", candidates)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if not 1 <= limit <= candidates <= 200:
        raise ValueError("Require 1 <= limit <= candidates <= 200")
    vault = validate_vault(vault)
    dataset = Path(dataset)
    rows = _read_dataset(vault, dataset, Path(cache_dir).resolve())
    queries = []
    for row in rows:
        baseline = _run_query(
            vault, row, cache_dir=cache_dir, provider=None, limit=limit, candidates=candidates,
            prompt_language=prompt_language,
        )
        requested = None
        if provider is not None:
            requested = _run_query(
                vault, row, cache_dir=cache_dir, provider=provider, limit=limit, candidates=candidates,
                prompt_language=prompt_language,
            )
        queries.append({**row, "baseline": baseline, "requested": requested})
    return {
        "dataset": str(dataset),
        "prompt_language": prompt_language,
        "query_count": len(rows),
        "limit": limit,
        "candidates": candidates,
        "requested_provider": type(provider).__name__ if provider is not None else None,
        "baseline": _summarize([row["baseline"] for row in queries]),
        "requested": _summarize([row["requested"] for row in queries]) if provider is not None else None,
        "queries": queries,
    }
