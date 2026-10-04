"""Command line interface; importing it never loads model weights."""

import argparse
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .evaluation import evaluate
from .index import Index
from .providers import LayaProvider, ProviderError
from .workflows import classify, search


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="brain-openkit", description="Read-only search and organization for Obsidian vaults")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    descriptions = {"doctor": "Check the Laya server (no inference unless --probe)",
                    "index": "Refresh the local Markdown index", "search": "Search with source excerpts",
                    "classify": "Suggest existing categories and tags", "evaluate": "Evaluate retrieval on labeled JSONL"}
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--config", type=Path, help="JSON settings; relative paths resolve from this file")
        command.add_argument("--vault", type=Path)
        command.add_argument("--cache-dir", type=Path, help="Derived SQLite cache (default: .cache/brain-openkit)")
        command.add_argument("--json", action="store_true", help="Emit one JSON object, including errors")
        if name != "index":
            command.add_argument("--provider", choices=("none", "laya"))
            command.add_argument("--base-url", help="Laya server (default: http://127.0.0.1:8000)")
            command.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
            command.add_argument("--max-tokens", type=int, help="Laya sequence budget, 1024 by default")
        if name in ("search", "evaluate"):
            command.add_argument("--limit", type=int, help="Maximum result notes (default: 5)")
            command.add_argument("--candidates", type=int, help="Maximum candidate passages (default: 20)")
        if name == "search":
            command.add_argument("query")
        elif name == "classify":
            command.add_argument("note", type=Path)
            command.add_argument("--taxonomy", required=True, type=Path)
        elif name == "evaluate":
            command.add_argument("dataset", type=Path)
        elif name == "doctor":
            command.add_argument("--probe", action="store_true", help="Run a synthetic inference; server may download the model")
    return parser


def _read_json(path: Path) -> dict:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("JSON input exceeds 1 MiB")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Input must be valid UTF-8 JSON") from exc


def _settings(args: argparse.Namespace) -> dict:
    result = {"vault": None, "cache_dir": Path(".cache/brain-openkit"),
              "provider": "laya" if args.command in ("classify", "doctor") else "none",
              "base_url": "http://127.0.0.1:8000", "timeout": 10.0,
              "max_tokens": 1024, "limit": 5, "candidates": 20}
    if args.config:
        config = _read_json(args.config)
        if not isinstance(config, dict) or set(config) - result.keys():
            raise ValueError("Unknown configuration fields; keep API keys in LAYA_API_KEY, not JSON")
        for key in ("vault", "cache_dir"):
            if key in config:
                if not isinstance(config[key], str) or not config[key].strip():
                    raise ValueError(f"Configuration {key} must be a nonempty path string")
                value = Path(config[key]).expanduser()
                config[key] = value if value.is_absolute() else args.config.absolute().parent / value
        result.update(config)
    for key in result:
        value = getattr(args, key, None)
        if value is not None:
            result[key] = value
    if result["provider"] not in ("none", "laya"):
        raise ValueError("Supported providers are none and laya; Jev is not implemented yet")
    if not isinstance(result["base_url"], str):
        raise ValueError("base_url must be a URL string")
    for key in ("limit", "candidates", "max_tokens"):
        if type(result[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    if not 1 <= result["limit"] <= result["candidates"] <= 200:
        raise ValueError("Require 1 <= limit <= candidates <= 200")
    if not 32 <= result["max_tokens"] <= 8192:
        raise ValueError("max_tokens must be between 32 and 8192")
    timeout = result["timeout"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 300 or not math.isfinite(timeout):
        raise ValueError("timeout must be a finite number between 0 and 300 seconds")
    for key in ("vault", "cache_dir"):
        if result[key] is not None:
            result[key] = Path(result[key]).expanduser().absolute()
    if args.command == "classify" and result["vault"] is None:
        args.note = args.note.expanduser().absolute()
        result["vault"] = args.note.parent
    if args.command in ("index", "search", "classify", "evaluate") and result["vault"] is None:
        raise ValueError("Specify --vault or a vault path in --config")
    return result


def _provider(settings: dict):
    if settings["provider"] == "none":
        return None
    return LayaProvider(base_url=settings["base_url"], api_key=os.environ.get("LAYA_API_KEY"),
                        timeout=settings["timeout"], max_tokens=settings["max_tokens"])


def _execute(args: argparse.Namespace) -> tuple[dict, int]:
    settings = _settings(args)
    vault, cache = settings["vault"], settings["cache_dir"]
    if args.command == "index":
        index = Index(vault, cache)
        try:
            report = index.update()
        finally:
            index.close()
        return report, 1 if report["errors"] else 0
    provider = _provider(settings)
    if args.command == "doctor":
        if provider is None:
            return {"version": __version__, "provider": "none", "inference_verified": False}, 0
        health = provider.health()
        report = {"version": __version__, "provider": "laya", "health": health, "inference_verified": False}
        if args.probe:
            from dataclasses import asdict
            report["probe"] = asdict(provider.choose("The note explains how to back up Markdown files.",
                                                      "What is the subject of the note?",
                                                      {"A": "Backing up notes", "B": "Cooking pasta"}))
            report["inference_verified"] = True
        return report, 0
    if args.command == "classify":
        if provider is None:
            raise ValueError("Classification requires --provider laya and a reachable server")
        return classify(vault, args.note, _read_json(args.taxonomy), provider), 0
    options = {"cache_dir": cache, "provider": provider, "limit": settings["limit"], "candidates": settings["candidates"]}
    if args.command == "search":
        return search(vault, args.query, **options), 0
    return evaluate(vault, args.dataset, **options), 0


def _text_report(command: str, report: dict) -> str:
    if command == "search":
        lines = [f"Reranking: {report['rerank_status']}"]
        if report.get("fallback_reason"):
            lines.append(f"Using BM25: {report['fallback_reason']}")
        for hit in report["results"]:
            lines.extend([f"\n{hit['path']}:{hit['start_line']}-{hit['end_line']}",
                          f"BM25={hit['bm25_score']:.4f}" + (f"  Laya={hit['model_score']:.4f}" if hit["model_score"] is not None else ""),
                          hit["text"].rstrip()])
        if not report["results"]:
            lines.append("No matching notes.")
        if report["index"]["errors"]:
            lines.append("Index warnings: " + json.dumps(report["index"]["errors"], ensure_ascii=False))
        return "\n".join(lines)
    if command == "classify":
        lines = [f"Note: {report['path']}", f"Category: {report['category'] or 'review conflicting passages'}",
                 "Suggested tags: " + (", ".join(report["tags"]) or "none"), "Source note unchanged."]
        for passage in report["passages"]:
            lines.append(f"\nLines {passage['start_line']}-{passage['end_line']}: {passage['category']}")
            lines.append(passage["text"].rstrip())
            lines.append("Category probabilities: " + json.dumps(passage["category_decision"]["probabilities"]))
            for name, tag in passage["tags"].items():
                lines.append(f"  {name}: {'suggest' if tag['suggested'] else 'do not suggest'} (score={tag['probabilities']['A']:.4f})")
        return "\n".join(lines)
    return json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    options = argv[:argv.index("--")] if "--" in argv else argv
    json_output = "--json" in options
    try:
        args = _parser().parse_args(argv)
        json_output = args.json
        report, status = _execute(args)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) if args.json else _text_report(args.command, report))
        return status
    except (ValueError, OSError, sqlite3.DatabaseError, ProviderError) as exc:
        message = str(exc)
        if json_output:
            print(json.dumps({"error": {"code": type(exc).__name__, "message": message}}, ensure_ascii=False))
        else:
            print(f"brain-openkit: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
