"""Command line interface; importing it never loads model weights."""

import argparse
import io
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
    parser = _ArgumentParser(prog="brain-openkit", description="Source-grounded search and reviewed organization for Obsidian")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    archive = commands.add_parser("conversations", help="Opt-in local conversation recording; no model calls")
    actions = archive.add_subparsers(dest="conversation_action", required=True)
    for action in ("status", "configure", "capture", "prune"):
        sub = actions.add_parser(action)
        sub.add_argument("--vault", type=Path, required=True)
        sub.add_argument("--json", action="store_true")
        if action == "configure":
            enabled = sub.add_mutually_exclusive_group()
            enabled.add_argument("--enable", dest="enabled", action="store_const", const=True, default=None)
            enabled.add_argument("--disable", dest="enabled", action="store_const", const=False)
            sub.add_argument("--max-bytes", type=int)
            sub.add_argument("--include-tool-output", action=argparse.BooleanOptionalAction, default=None)
            sub.add_argument("--retention-days", type=int)
            sub.add_argument("--auto-prune", action=argparse.BooleanOptionalAction, default=None)
        elif action == "capture":
            sub.add_argument("--host", choices=("claude", "codex"), required=True)
            sub.add_argument("--session-id", required=True)
            sub.add_argument("--transcript", type=Path, required=True)
        elif action == "prune":
            sub.add_argument("--apply", action="store_true", help="Delete only unchanged managed records selected by retention")
    descriptions = {"doctor": "Check the decision provider (no inference unless --probe)",
                    "index": "Refresh the local Markdown index", "search": "Search with source excerpts",
                    "classify": "Suggest existing categories and tags", "evaluate": "Evaluate retrieval on labeled JSONL",
                    "init": "Preview initialization or adoption of an existing vault",
                    "ingest": "Preview a preserved source and linked knowledge note",
                    "save": "Preview saving a selected draft with source links",
                    "organize": "Preview category, tags and existing-note links",
                    "fold": "Preview an extractive rollup, preserving its source notes",
                    "lint": "Inspect links and supported metadata without changing notes",
                    "apply": "Apply a reviewed change plan with its exact ID",
                    "undo": "Undo a transaction if its files have not changed",
                    "recover": "Recover an interrupted transaction without overwriting edits",
                    "web": "Browse local BM25 search on 127.0.0.1"}
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("--config", type=Path, help="JSON settings; relative paths resolve from this file")
        command.add_argument("--vault", type=Path)
        command.add_argument("--cache-dir", type=Path, help="Derived SQLite cache (default: .cache/brain-openkit)")
        command.add_argument("--json", action="store_true", help="Emit one JSON object, including errors")
        if name in ("doctor", "search", "classify", "evaluate"):
            command.add_argument("--provider", choices=("none", "laya", "kev", "jev", "ko-decision", "codex"))
            command.add_argument("--base-url", help="Override the selected provider's endpoint")
            command.add_argument("--model", help="Jev/Kev/ko-decision server ID or Codex model; does not load HF weights")
            command.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
            command.add_argument("--codex-timeout", type=float, help="Codex execution timeout in seconds (default: 600)")
            command.add_argument("--codex-executable", help="Codex CLI executable path (default: codex)")
            command.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh", "max", "ultra"),
                                 help="Codex reasoning effort (default: ultra)")
            command.add_argument("--prompt-language", choices=("en", "ko"),
                                 help="Language of model instructions; leaves source and taxonomy unchanged (default: en)")
            command.add_argument("--max-tokens", type=int, help="Laya sequence budget, 1024 by default")
        if name in ("search", "evaluate"):
            command.add_argument("--limit", type=int, help="Maximum result notes (default: 5)")
            command.add_argument("--candidates", type=int, help="Maximum candidate passages (default: 20)")
        if name == "search":
            command.add_argument("query")
        elif name == "classify":
            command.add_argument("note", type=Path)
            command.add_argument("--taxonomy", required=True, type=Path)
            command.add_argument("--suggestions", type=Path,
                                 help="Validate host-written document suggestion JSON locally; no provider call")
        elif name == "evaluate":
            command.add_argument("dataset", type=Path)
        elif name == "doctor":
            command.add_argument("--probe", action="store_true", help="Run a synthetic inference; server may download the model")
        elif name == "ingest":
            command.add_argument("source", type=Path)
            command.add_argument("--title", required=True)
            command.add_argument("--draft", type=Path, help="Optional host-written UTF-8 draft")
            command.add_argument("--source-url")
        elif name == "save":
            command.add_argument("draft", type=Path)
            command.add_argument("--path", required=True, help="Vault-relative Markdown destination")
            command.add_argument("--source", action="append", default=[], help="Existing source note; repeat to add more")
        elif name == "organize":
            command.add_argument("note")
            command.add_argument("--category")
            command.add_argument("--tag", action="append", help="Tag to add; repeat for multiple tags")
            command.add_argument("--link", action="append", help="Existing note to link; repeat for more links")
        elif name == "fold":
            command.add_argument("notes", nargs="+")
            command.add_argument("--path", required=True)
            command.add_argument("--title", required=True)
        elif name == "apply":
            command.add_argument("plan_file", type=Path)
            command.add_argument("--approve", required=True, help="ID of the plan you inspected")
        elif name in ("undo", "recover"):
            command.add_argument("transaction_id")
        elif name == "web":
            command.add_argument("--port", type=int, default=8765, help="Loopback port; 0 selects an available port")
        if name in ("init", "ingest", "save", "organize", "fold"):
            command.add_argument("--plan", type=Path, help="Save preview JSON to a new file outside the vault")
    return parser


def _read_json(path: Path, max_bytes: int = 1024 * 1024, *, strict: bool = False) -> dict:
    if path.stat().st_size > max_bytes:
        raise ValueError("JSON input exceeds the size limit")
    try:
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("JSON input exceeds the size limit")
        if strict:
            from .providers import _unique_object, _reject_constant
            return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Input must be valid UTF-8 JSON") from exc


def _settings(args: argparse.Namespace) -> dict:
    result = {"vault": None, "cache_dir": Path(".cache/brain-openkit"),
              "provider": "kev" if args.command in ("classify", "doctor") else "none",
              "base_url": None, "laya_base_url": "http://127.0.0.1:8000",
              "jev_base_url": "https://api.typesafe.ai", "jev_model": "jev-latest",
              "kev_base_url": "http://127.0.0.1:8009", "kev_model": "kev-latest", "model": None,
              "ko_decision_base_url": "http://127.0.0.1:8010",
              "ko_decision_model": "mmetamong/ko-decision-roberta-large",
              "timeout": 10.0, "prompt_language": "en",
              "codex_model": "gpt-6-astra", "codex_timeout": 600.0, "codex_executable": "codex",
              "reasoning_effort": "ultra",
              "max_tokens": 1024, "limit": 5, "candidates": 20}
    if args.config:
        config = _read_json(args.config)
        if not isinstance(config, dict) or set(config) - result.keys():
            raise ValueError("Unknown configuration fields; keep API keys in environment variables, not JSON")
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
    if result["provider"] not in ("none", "laya", "kev", "jev", "ko-decision", "codex"):
        raise ValueError("Supported providers are none, laya, kev, jev, ko-decision and codex")
    if result["provider"] == "codex" and result["base_url"] is not None:
        raise ValueError("base_url is not supported by the Codex CLI provider")
    if result["reasoning_effort"] not in ("low", "medium", "high", "xhigh", "max", "ultra"):
        raise ValueError("reasoning_effort is not supported")
    codex_timeout = result["codex_timeout"]
    if (isinstance(codex_timeout, bool) or not isinstance(codex_timeout, (int, float))
            or not math.isfinite(codex_timeout) or not 0 < codex_timeout <= 3600):
        raise ValueError("codex_timeout must be a finite number between 0 and 3600 seconds")
    if result["prompt_language"] not in ("en", "ko"):
        raise ValueError("prompt_language must be en or ko")
    if result["base_url"] is not None and not isinstance(result["base_url"], str):
        raise ValueError("base_url must be a URL string")
    for key in ("laya_base_url", "jev_base_url", "jev_model", "kev_base_url", "kev_model",
                "ko_decision_base_url", "ko_decision_model", "codex_model", "codex_executable"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if result["model"] is not None and (not isinstance(result["model"], str) or not result["model"].strip()):
        raise ValueError("model must be a nonempty string")
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
    if args.command != "doctor" and result["vault"] is None:
        raise ValueError("Specify --vault or a vault path in --config")
    return result


def _provider(settings: dict):
    if settings["provider"] == "none":
        return None
    if settings["provider"] == "codex":
        from .codex_provider import CodexProvider
        return CodexProvider(model=settings["model"] or settings["codex_model"],
                             reasoning_effort=settings["reasoning_effort"], timeout=settings["codex_timeout"],
                             executable=settings["codex_executable"])
    if settings["provider"] == "jev":
        from .jev import JevProvider
        return JevProvider(base_url=settings["base_url"] or settings["jev_base_url"],
                           api_key=os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY"),
                           model=settings["model"] or settings["jev_model"], timeout=settings["timeout"])
    if settings["provider"] == "kev":
        from .kev import KevProvider
        return KevProvider(base_url=settings["base_url"] or settings["kev_base_url"],
                           api_key=os.environ.get("KEV_API_KEY"),
                           model=settings["model"] or settings["kev_model"], timeout=settings["timeout"])
    if settings["provider"] == "ko-decision":
        from .ko_decision import KoDecisionProvider
        return KoDecisionProvider(base_url=settings["base_url"] or settings["ko_decision_base_url"],
                                  api_key=os.environ.get("KO_DECISION_API_KEY"),
                                  model=settings["model"] or settings["ko_decision_model"],
                                  timeout=settings["timeout"])
    return LayaProvider(base_url=settings["base_url"] or settings["laya_base_url"], api_key=os.environ.get("LAYA_API_KEY"),
                        timeout=settings["timeout"], max_tokens=settings["max_tokens"])


def _draft(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Draft exceeds the 2 MiB limit")
    return raw.decode("utf-8")


def _export_plan(vault: Path, plan: dict, destination: Path | None) -> dict:
    if destination is not None:
        if destination.resolve().is_relative_to(vault.resolve()):
            raise ValueError("Store review plans outside the vault")
        data = (json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    return plan


def _execute(args: argparse.Namespace) -> tuple[dict, int]:
    if args.command == "conversations":
        from . import conversations
        action = args.conversation_action
        if action == "configure":
            fields = ("enabled", "max_bytes", "include_tool_output", "retention_days", "auto_prune")
            result = conversations.configure(args.vault, **{key: getattr(args, key) for key in fields
                                                            if getattr(args, key) is not None})
        elif action == "status":
            result = conversations.status(args.vault)
        elif action == "prune":
            result = conversations.prune(args.vault, apply=args.apply)
        else:
            from .conversation_hooks import capture_transcript
            result = capture_transcript(args.vault, args.host, args.session_id, args.transcript)
        return result, 3 if result.get("status") in {"blocked", "pending_transcript"} else 0
    settings = _settings(args)
    vault, cache = settings["vault"], settings["cache_dir"]
    if args.command in ("init", "ingest", "save", "organize", "fold", "lint"):
        from . import notes
        if args.command == "lint":
            report = notes.lint(vault)
            return report, 0
        if args.command == "init":
            plan = notes.plan_init(vault)
        elif args.command == "ingest":
            plan = notes.plan_ingest(vault, args.source, args.title,
                                     draft=_draft(args.draft) if args.draft else None, source_url=args.source_url)
        elif args.command == "save":
            plan = notes.plan_save(vault, args.path, _draft(args.draft), sources=args.source)
        elif args.command == "organize":
            plan = notes.plan_organize(vault, args.note, category=args.category, tags=args.tag, links=args.link)
        else:
            plan = notes.plan_fold(vault, args.notes, args.path, args.title)
        return _export_plan(vault, plan, args.plan), 0
    if args.command in ("apply", "undo", "recover"):
        from . import changes
        if args.command == "apply":
            return changes.apply_plan(vault, _read_json(args.plan_file, 64 * 1024 * 1024), args.approve), 0
        operation = changes.undo if args.command == "undo" else changes.recover
        return operation(vault, args.transaction_id), 0
    if args.command == "web":
        from .web import serve
        serve(vault, cache, port=args.port)
        return {"status": "stopped"}, 0
    if args.command == "index":
        index = Index(vault, cache)
        try:
            report = index.update()
        finally:
            index.close()
        return report, 1 if report["errors"] else 0
    if args.command == "classify" and args.suggestions is not None:
        if args.provider not in (None, "none"):
            raise ValueError("--suggestions cannot be combined with a model --provider")
        return classify(vault, args.note, _read_json(args.taxonomy),
                        suggestions=_read_json(args.suggestions, strict=True),
                        prompt_language=settings["prompt_language"]), 0
    provider = _provider(settings)
    if args.command == "doctor":
        if provider is None:
            return {"version": __version__, "provider": "none", "inference_verified": False}, 0
        health = provider.health()
        report = {"version": __version__, "provider": provider.name, "health": health, "inference_verified": False}
        if args.probe:
            from dataclasses import asdict
            if settings["prompt_language"] == "ko":
                report["probe"] = asdict(provider.choose("이 문서는 마크다운 파일을 백업하는 방법을 설명한다.",
                                                         "문서의 주제는 무엇인가?",
                                                         {"A": "노트 백업", "B": "파스타 요리"}))
            else:
                report["probe"] = asdict(provider.choose("The note explains how to back up Markdown files.",
                                                         "What is the subject of the note?",
                                                         {"A": "Backing up notes", "B": "Cooking pasta"}))
            report["prompt_language"] = settings["prompt_language"]
            report["inference_verified"] = True
        return report, 0
    if args.command == "classify":
        if provider is None:
            raise ValueError("Classification requires --provider laya, kev, jev, ko-decision or codex and a reachable service")
        return classify(vault, args.note, _read_json(args.taxonomy), provider,
                        prompt_language=settings["prompt_language"]), 0
    options = {"cache_dir": cache, "provider": provider, "limit": settings["limit"],
               "candidates": settings["candidates"], "prompt_language": settings["prompt_language"]}
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
                          f"BM25={hit['bm25_score']:.4f}" + (f"  {report['provider']}={hit['model_score']:.4f}" if hit["model_score"] is not None else ""),
                          hit["text"].rstrip()])
        if not report["results"]:
            lines.append("No matching notes.")
        if report["index"]["errors"]:
            lines.append("Index warnings: " + json.dumps(report["index"]["errors"], ensure_ascii=False))
        return "\n".join(lines)
    if command == "classify":
        lines = [f"Note: {report['path']}", f"Category: {report['category'] or 'review conflicting passages'}",
                 "Suggested tags: " + (", ".join(report["tags"]) or "none"), "Source note unchanged."]
        if report.get("classification_scope") == "document":
            lines.extend(["Classification scope: whole document",
                          f"Review required: {'yes' if report['review_required'] else 'no'}",
                          "Rationale: " + report["rationale"]])
            for passage in report["passages"]:
                lines.extend([f"\nLines {passage['start_line']}-{passage['end_line']}:", passage["text"].rstrip()])
            return "\n".join(lines)
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
        # Preserve Korean source text when Windows redirects output to a pipe.
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, io.TextIOWrapper):
                stream.reconfigure(encoding="utf-8")
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
