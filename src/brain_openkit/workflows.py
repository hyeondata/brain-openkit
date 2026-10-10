"""Read-only search and organization workflows, independent of HTTP providers."""

from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from .index import Index
from .providers import Decision, DecisionProvider, ProviderError
from .vault import read_note


def _choose_decisions(provider: DecisionProvider,
                      requests: list[tuple[str, str, dict[str, str]]]) -> list[Decision]:
    choose_many = getattr(provider, "choose_many", None)
    if not callable(choose_many):
        return [provider.choose(*request) for request in requests]
    decisions = []
    for start in range(0, len(requests), 64):
        batch = requests[start:start + 64]
        received = choose_many(batch)
        if not isinstance(received, list) or len(received) != len(batch):
            raise ProviderError("invalid_batch_response")
        decisions.extend(received)
    return decisions


def search(vault: Path, query: str, *, cache_dir: Path,
           provider: DecisionProvider | None = None, limit: int = 5,
           candidates: int = 20, prompt_language: str = "en") -> dict:
    if prompt_language not in ("en", "ko"):
        raise ValueError("prompt_language must be en or ko")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must not be blank")
    if not 1 <= limit <= candidates <= 200:
        raise ValueError("Require 1 <= limit <= candidates <= 200")
    started = perf_counter()
    index = Index(vault, cache_dir)
    try:
        report = index.update()
        hits = index.search(query, candidates)
    finally:
        index.close()
    rows = [{**asdict(hit.chunk), "bm25_score": hit.bm25_score,
             "model_score": None, "decision": None} for hit in hits]
    status = "disabled" if provider is None else "not_needed"
    reason = None
    model = None
    if provider is not None and rows:
        try:
            requests = []
            for row in rows:
                state = f"Query: {query}\nNote: {row['path']}\nTitle: {row['title']}\nPassage:\n{row['text']}"
                if prompt_language == "ko":
                    state = f"검색 질문: {query}\n문서: {row['path']}\n제목: {row['title']}\n본문:\n{row['text']}"
                requests.append((
                    state, "본문에 검색 질문에 답하는 데 유용한 정보가 있는가?" if prompt_language == "ko" else
                    "Does the passage contain information useful for the query?",
                    {"A": "검색 질문과 관련된 유용한 정보가 있다", "B": "관련이 없거나 정보가 부족하다"}
                    if prompt_language == "ko" else
                    {"A": "Relevant information for the query", "B": "Unrelated or insufficient information"}))
            decisions = _choose_decisions(provider, requests)
            # Apply only after every candidate succeeds: never mix score scales.
            for row, decision in zip(rows, decisions):
                row["model_score"] = decision.probabilities["A"]
                row["decision"] = asdict(decision)
            rows.sort(key=lambda row: (-row["model_score"], -row["bm25_score"], row["path"], row["start_line"]))
            status = "complete"
            model = decisions[0].model
        except ProviderError as exc:
            status, reason = "unavailable", str(exc)
    distinct = []
    seen = set()
    for row in rows:
        if row["path"] not in seen:
            distinct.append(row)
            seen.add(row["path"])
        if len(distinct) == limit:
            break
    return {"query": query, "provider": "none" if provider is None else getattr(provider, "name", type(provider).__name__),
            "model": model, "prompt_language": prompt_language, "rerank_status": status, "fallback_reason": reason,
            "candidate_count": len(hits), "results": distinct, "index": report,
            "elapsed_ms": round((perf_counter() - started) * 1000, 3)}


def validate_taxonomy(taxonomy: dict) -> dict:
    if not isinstance(taxonomy, dict) or set(taxonomy) - {"categories", "tags"}:
        raise ValueError("Taxonomy must contain categories and optional tags")
    categories, tags = taxonomy.get("categories"), taxonomy.get("tags", {})
    if not isinstance(categories, dict) or not 1 <= len(categories) <= 10:
        raise ValueError("Taxonomy categories must contain 1 to 10 named descriptions")
    if not isinstance(tags, dict) or len(tags) > 30:
        raise ValueError("Taxonomy tags must contain at most 30 named descriptions")
    for section in (categories, tags):
        for name, description in section.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                raise ValueError("Taxonomy names must be nonempty strings of at most 100 characters")
            if not isinstance(description, str) or not description.strip() or len(description) > 1000:
                raise ValueError("Taxonomy descriptions must be nonempty strings of at most 1000 characters")
    return {"categories": categories, "tags": tags}


def _document_suggestion(suggestion, taxonomy):
    if (type(suggestion) is not dict
            or set(suggestion) != {"category", "tags", "rationale", "review_required"}
            or not isinstance(suggestion["category"], str)
            or suggestion["category"] not in taxonomy["categories"]
            or type(suggestion["tags"]) is not list
            or any(not isinstance(tag, str) or tag not in taxonomy["tags"] for tag in suggestion["tags"])
            or len(set(suggestion["tags"])) != len(suggestion["tags"])
            or not isinstance(suggestion["rationale"], str)
            or not suggestion["rationale"].strip() or len(suggestion["rationale"]) > 2000
            or type(suggestion["review_required"]) is not bool):
        raise ValueError("Invalid document suggestion: use allowed category, unique allowed tags, rationale and review_required")
    return {**suggestion, "tags": sorted(suggestion["tags"])}


def classify(vault: Path, note: Path, taxonomy: dict, provider: DecisionProvider | None = None,
             *, prompt_language: str = "en", suggestions: dict | None = None) -> dict:
    if prompt_language not in ("en", "ko"):
        raise ValueError("prompt_language must be en or ko")
    taxonomy = validate_taxonomy(taxonomy)
    chunks = read_note(vault, note)
    if not chunks:
        raise ValueError("The note has no nonempty passages to classify")
    if suggestions is not None and provider is not None:
        raise ValueError("Choose host suggestions or a provider, not both")
    document_classifier = getattr(provider, "classify_document", None)
    if suggestions is not None or callable(document_classifier):
        metadata = {"model": None, "usage": {}, "elapsed_ms": 0.0}
        if callable(document_classifier):
            document = {**asdict(chunks[0]), "end_line": chunks[-1].end_line,
                        "text": "".join(chunk.text for chunk in chunks)}
            result = document_classifier(document, taxonomy, prompt_language=prompt_language)
            try:
                suggestions = _document_suggestion(result["suggestion"], taxonomy)
                metadata = {key: result[key] for key in metadata}
            except (ValueError, TypeError, KeyError) as exc:
                raise ProviderError("invalid_document_response") from exc
        else:
            suggestions = _document_suggestion(suggestions, taxonomy)
        return {"path": chunks[0].path, "provider": "host" if provider is None else provider.name,
                "prompt_language": prompt_language, "classification_scope": "document",
                "status": "complete", **suggestions, **metadata,
                "category_candidates": [suggestions["category"]],
                "passages": [asdict(chunk) for chunk in chunks], "note_modified": False}
    if provider is None:
        raise ValueError("Classification requires a provider or host suggestions")
    if len(chunks) > 200:
        raise ValueError("The note exceeds the 200-passage classification limit")
    names = list(taxonomy["categories"])
    choices = {chr(65+i): f"{name}: {taxonomy['categories'][name]}" for i, name in enumerate(names)}
    requests = []
    for chunk in chunks:
        state = f"Note: {chunk.path}\nTitle: {chunk.title}\nPassage:\n{chunk.text}"
        if prompt_language == "ko":
            state = f"문서: {chunk.path}\n제목: {chunk.title}\n본문:\n{chunk.text}"
        requests.append((state, "본문에 가장 적합한 기존 분류를 고르세요." if prompt_language == "ko" else
                         "Which existing category best describes this passage?", choices))
        for name, description in taxonomy["tags"].items():
            requests.append((state,
                             f"본문이 다음 태그에 해당하는가? {name}: {description}" if prompt_language == "ko" else
                             f"Does this passage match the tag {name}: {description}?",
                             {"A": "태그에 해당한다", "B": "태그에 해당하지 않는다"} if prompt_language == "ko" else
                             {"A": "The tag applies", "B": "The tag does not apply"}))
    decisions = iter(_choose_decisions(provider, requests))
    passages, category_names, tags = [], set(), set()
    for chunk in chunks:
        category = next(decisions)
        selected = names[ord(category.choice)-65]
        category_names.add(selected)
        tag_results = {}
        for name in taxonomy["tags"]:
            decision = next(decisions)
            applies = decision.probabilities["A"] > decision.probabilities["B"]
            if applies:
                tags.add(name)
            tag_results[name] = {"suggested": applies, **asdict(decision)}
        passages.append({**asdict(chunk), "category": selected,
                         "category_decision": asdict(category), "tags": tag_results})
    return {"path": chunks[0].path, "provider": getattr(provider, "name", type(provider).__name__),
            "prompt_language": prompt_language, "classification_scope": "passage",
            "model": passages[0]["category_decision"]["model"],
            "status": "complete", "review_required": len(category_names) > 1,
            "category": next(iter(category_names)) if len(category_names) == 1 else None,
            "category_candidates": sorted(category_names), "tags": sorted(tags), "passages": passages,
            "note_modified": False}
