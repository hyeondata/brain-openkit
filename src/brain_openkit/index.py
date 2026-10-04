"""Disposable SQLite chunk cache and deterministic lexical BM25 retrieval."""

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import unicodedata

from .vault import Chunk, EXCLUDED_DIRECTORIES, _read_note_text, chunk_markdown, validate_vault


_CACHE_VERSION = 2  # Rebuild citations previously counted with str.splitlines().
_WORDS = re.compile(r"[가-힣]+|[^\W_가-힣]+(?:[_'-][^\W_가-힣]+)*", re.UNICODE)


def _tokens(text: str) -> list[str]:
    words = _WORDS.findall(unicodedata.normalize("NFKC", text).casefold())
    terms = list(words)
    for word in words:
        if re.fullmatch(r"[가-힣]+", word):
            terms.extend(word[i:i + 2] for i in range(len(word) - 1) if len(word) > 2)
    return terms


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    bm25_score: float


class Index:
    """One independently owned cache per canonical vault path.

    Call update before a user-facing search. search itself only reads the cache,
    allowing a workflow to include update errors with the results it presents.
    """

    def __init__(self, vault: Path, cache_dir: Path):
        self.vault = validate_vault(vault)
        cache_dir = Path(cache_dir)
        if cache_dir.is_symlink():
            raise ValueError("cache directory must not be a symlink")
        self.cache_dir = cache_dir.resolve()
        if self.vault == self.cache_dir or self.vault.is_relative_to(self.cache_dir):
            raise ValueError("cache directory must not contain the vault")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(str(self.vault).encode()).hexdigest()
        database = self.cache_dir / f"{identity}.sqlite3"
        if database.is_symlink():
            raise ValueError("cache database must not be a symlink")
        self._connection = sqlite3.connect(database, timeout=10)
        self._connection.execute("PRAGMA foreign_keys = ON")
        try:
            with self._connection as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS ownership (vault TEXT NOT NULL)")
                owner = conn.execute("SELECT vault FROM ownership").fetchone()
                if owner is not None and owner[0] != str(self.vault):
                    raise ValueError("cache belongs to another vault")
                if owner is None:
                    conn.execute("INSERT INTO ownership VALUES (?)", (str(self.vault),))
                if conn.execute("PRAGMA user_version").fetchone()[0] != _CACHE_VERSION:
                    conn.execute("DROP TABLE IF EXISTS chunks")
                    conn.execute("DROP TABLE IF EXISTS notes")
                    conn.execute(f"PRAGMA user_version = {_CACHE_VERSION}")
                conn.execute("CREATE TABLE IF NOT EXISTS notes (path TEXT PRIMARY KEY, digest TEXT NOT NULL)")
                conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
                    path TEXT NOT NULL REFERENCES notes(path) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL, title TEXT NOT NULL,
                    start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
                    text TEXT NOT NULL, terms TEXT NOT NULL, length INTEGER NOT NULL,
                    PRIMARY KEY (path, ordinal))""")
        except Exception:
            self._connection.close()
            raise

    def update(self) -> dict:
        validate_vault(self.vault)
        report = {"indexed": 0, "unchanged": 0, "deleted": 0, "errors": []}
        current = set()
        prior = dict(self._connection.execute("SELECT path, digest FROM notes"))

        def walk_error(error):
            try:
                path = Path(error.filename).relative_to(self.vault).as_posix()
            except (TypeError, ValueError):
                path = "."
            report["errors"].append({"path": path, "error": str(error)})

        with self._connection as conn:
            for directory, names, filenames in os.walk(self.vault, followlinks=False, onerror=walk_error):
                base = Path(directory)
                names[:] = sorted(name for name in names if not name.startswith(".")
                                  and name not in EXCLUDED_DIRECTORIES and not (base / name).is_symlink()
                                  and (base / name).resolve() != self.cache_dir)
                for name in sorted(filenames):
                    path = base / name
                    if name.startswith(".") or path.suffix.lower() != ".md" or path.is_symlink():
                        continue
                    relative = path.relative_to(self.vault).as_posix()
                    try:
                        _, text = _read_note_text(self.vault, path)
                        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                        chunks = None if prior.get(relative) == digest else chunk_markdown(text, relative)
                    except (OSError, ValueError) as exc:
                        report["errors"].append({"path": relative, "error": str(exc)})
                        continue
                    current.add(relative)
                    if chunks is None:
                        report["unchanged"] += 1
                        continue
                    conn.execute("DELETE FROM notes WHERE path = ?", (relative,))
                    conn.execute("INSERT INTO notes VALUES (?, ?)", (relative, digest))
                    for ordinal, chunk in enumerate(chunks):
                        terms = Counter(_tokens(f"{chunk.title}\n{chunk.path}\n{chunk.text}"))
                        conn.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                     (relative, ordinal, chunk.title, chunk.start_line, chunk.end_line,
                                      chunk.text, json.dumps(terms, ensure_ascii=False), sum(terms.values())))
                    report["indexed"] += 1
            stale = set(prior) - current
            conn.executemany("DELETE FROM notes WHERE path = ?", [(path,) for path in stale])
            report["deleted"] = len(stale)
        return report

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000")
        if not isinstance(query, str) or len(query) > 8000 or len(unicodedata.normalize("NFKC", query)) > 8000:
            raise ValueError("query must contain at most 8000 normalized characters")
        query_terms = set(_tokens(query))
        if not query_terms:
            return []
        rows = self._connection.execute(
            "SELECT path, title, start_line, end_line, text, terms, length FROM chunks ORDER BY path, start_line"
        ).fetchall()
        if not rows:
            return []
        counts = [json.loads(row[5]) for row in rows]
        frequencies = Counter(term for terms in counts for term in query_terms if term in terms)
        average_length = sum(row[6] for row in rows) / len(rows)
        if not average_length:
            return []
        hits = []
        for row, terms in zip(rows, counts):
            score = 0.0
            for term in sorted(query_terms):
                frequency = terms.get(term, 0)
                if frequency:
                    inverse_frequency = math.log(1 + (len(rows) - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
                    score += inverse_frequency * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * row[6] / average_length))
            if score > 0:
                hits.append(SearchHit(Chunk(*row[:5]), score))
        hits.sort(key=lambda hit: (-hit.bm25_score, hit.chunk.path, hit.chunk.start_line))
        return hits[:limit]

    def close(self) -> None:
        self._connection.close()
