"""Source-grounded wiki plans and a read-only Markdown health check.

Organize supports a scalar ``category`` and ``tags`` as a scalar, a simple
flow list, or a block list of strings. Requested tags are merged. Unknown
frontmatter fields are preserved verbatim; duplicate keys, malformed top-level
structure and unsupported category/tag values are rejected. This is deliberately
a conservative metadata editor, not a complete YAML parser. Lint uses the same
structural checks. It resolves note paths/basenames, not heading/block anchors.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from urllib.parse import urlsplit

from .changes import make_plan
from .vault import (
    EXCLUDED_DIRECTORIES, MAX_NOTE_BYTES, _read_note_text, chunk_markdown, is_link_path,
    validate_vault,
)


def _lines(text):
    return re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)


def _newline(text):
    match = re.search(r"\r\n|\r|\n", text)
    return match[0] if match else "\n"


def _single_line(value, label, limit=200):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError(f"{label} must be a nonempty single-line string of at most {limit} characters")
    return value.strip()


def _slug(title):
    title = _single_line(title, "title")
    slug = re.sub(r"[^\w-]+", "-", unicodedata.normalize("NFKC", title), flags=re.UNICODE).strip("-_")[:100]
    if not slug:
        raise ValueError("title must contain a letter or number")
    return slug


def _destination(path):
    if not isinstance(path, str) or any(c in path for c in "\\#[]|"):
        raise ValueError("note path must use relative forward slashes")
    relative = PurePosixPath(path)
    if (relative.is_absolute() or not relative.parts or ".." in relative.parts
            or relative.suffix.lower() != ".md"
            or any(p.startswith(".") or p in EXCLUDED_DIRECTORIES for p in relative.parts)
            or relative.parts[0].casefold() == "sources"):
        raise ValueError("destination must be a relative Markdown note outside protected paths and Sources")
    return relative.as_posix()


def _catalog(vault, *, require_complete=False):
    root = validate_vault(vault)
    notes, files, errors = {}, set(), []
    def traversal_error(error):
        path = Path(error.filename) if error.filename else root
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = "."
        errors.append({"path": relative, "error": str(error)})

    def eligible(path):
        if path.name.startswith(".") or path.name in EXCLUDED_DIRECTORIES:
            return False
        try:
            return not is_link_path(path)
        except OSError as error:
            traversal_error(error)
            return False

    for directory, directories, filenames in os.walk(root, followlinks=False, onerror=traversal_error):
        directories[:] = sorted(d for d in directories if eligible(Path(directory) / d))
        for name in sorted(filenames):
            path = Path(directory) / name
            if not eligible(path):
                continue
            relative = path.relative_to(root).as_posix()
            try:
                if not stat.S_ISREG(path.stat().st_mode):
                    continue
                files.add(relative)
                if path.suffix.lower() == ".md":
                    _, notes[relative] = _read_note_text(root, Path(relative))
            except (OSError, ValueError) as exc:
                errors.append({"path": relative, "error": str(exc)})
    if errors and require_complete:
        raise ValueError("cannot plan changes from an incomplete vault scan: " + ", ".join(entry["path"] for entry in errors[:10]))
    return notes, files, errors


def _without_code(text):
    """Replace code/comments with spaces, preserving CR/LF citation positions."""
    output, fence = [], None
    for line in _lines(text):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence:
            output.append(re.sub(r"[^\r\n]", " ", line))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
            output.append(re.sub(r"[^\r\n]", " ", line))
        else:
            output.append(line)
    text = re.sub(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)", lambda m: re.sub(r"[^\r\n]", " ", m[0]), "".join(output), flags=re.S)
    return re.sub(r"<!--.*?(?:-->|\Z)", lambda m: re.sub(r"[^\r\n]", " ", m[0]), text, flags=re.S)


def _wikilinks(text):
    clean = _without_code(text)
    for match in re.finditer(r"!?\[\[([^\]\r\n]+)\]\]", clean):
        target = match[1].split("|", 1)[0].split("#", 1)[0].strip()
        line = len(re.findall(r"\r\n|\r|\n", clean[:match.start()])) + 1
        yield target, line


def _resolve(target, files, current=None):
    if not target:
        return [current] if current else []
    if "\\" in target or ":" in target:
        return []
    path = PurePosixPath(target)
    if path.is_absolute() or any(p.startswith(".") or p in EXCLUDED_DIRECTORIES for p in path.parts):
        return []
    candidates = [target] if path.suffix.lower() == ".md" else [target + ".md", target]
    for candidate in candidates:
        if candidate in files:
            return [candidate]
    if current and "/" in target:
        for candidate in candidates:
            relative = (PurePosixPath(current).parent / candidate).as_posix()
            if relative in files:
                return [relative]
    if "/" not in target:
        matches = sorted(p for p in files if PurePosixPath(p).name in candidates)
        return matches
    return []


def _references(values, files, current=None):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 200:
        raise ValueError("references must be a list of at most 200 existing note targets")
    resolved = []
    for value in values:
        value = _single_line(value, "reference", 1000)
        if any(c in value for c in "[]|#"):
            raise ValueError("references must be note targets without wikilink markup, aliases or anchors")
        matches = _resolve(value, files, current)
        if len(matches) != 1 or PurePosixPath(matches[0]).suffix.lower() != ".md":
            raise ValueError(f"reference is missing, ambiguous, or not Markdown: {value}")
        if matches[0] not in resolved:
            resolved.append(matches[0])
    return resolved


def _link(path):
    if any(c in path for c in "\\#[]|") or any(ord(c) < 32 for c in path):
        raise ValueError(f"note path cannot be represented as an unambiguous wikilink: {path}")
    return "[[" + str(PurePosixPath(path).with_suffix("")) + "]]"


def _append_links(text, paths, heading, files, current):
    seen = set()
    for target, _ in _wikilinks(text):
        resolved = _resolve(target, files, current)
        if len(resolved) == 1:
            seen.add(resolved[0])
    missing = [p for p in paths if p not in seen]
    if not missing:
        return text
    newline = _newline(text)
    separator = "" if not text else (newline if text.endswith(("\n", "\r")) else newline * 2)
    return text + separator + f"## {heading}" + newline * 2 + "".join(f"- {_link(p)}{newline}" for p in missing)


def _index(vault, paths):
    notes, files, _ = _catalog(vault, require_complete=True)
    matches = [path for path in notes if path.casefold() == "index.md"]
    if len(matches) > 1:
        raise ValueError("vault has ambiguous case variants of Index.md")
    path = matches[0] if matches else "Index.md"
    before = notes.get(path, "# Brain OpenKit\n")
    content = _append_links(before, sorted(set(paths) - {path}), "Notes", files | set(paths), path)
    return {"path": path, "content": content}


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _frontmatter(text):
    lines = _lines(text)
    if not lines or lines[0].rstrip("\r\n").lstrip("\ufeff") != "---":
        return lines, 0, {}
    end = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") in ("---", "...")), None)
    if end is None:
        raise ValueError("frontmatter has no closing delimiter")
    entries, previous = {}, None
    for number in range(1, end):
        line = lines[number].rstrip("\r\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            if previous is None or line.startswith("\t"):
                raise ValueError("unsupported frontmatter indentation")
            continue
        match = re.match(r"^([^:\s][^:]*):(?:\s|$)(.*)$", line)
        if (not match or match[1].strip() != match[1] or match[1] == "<<"
                or match[1][0] in "[{'\"&*!?>|%@`"):
            raise ValueError("unsupported frontmatter top-level structure")
        key = match[1]
        if key in entries:
            raise ValueError(f"duplicate frontmatter key: {key}")
        if previous:
            entries[previous][1] = number
        entries[key] = [number, end, match[2]]
        previous = key
    return lines, end + 1, entries


def _scalar(value):
    value = value.strip()
    if value.startswith('"'):
        try:
            result, position = json.JSONDecoder().raw_decode(value)
        except ValueError as exc:
            raise ValueError("unsupported quoted metadata value") from exc
        if not isinstance(result, str) or value[position:].strip() and not value[position:].lstrip().startswith("#"):
            raise ValueError("metadata value must be a string")
        return result
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:\s*#.*)?", value)
        if not match:
            raise ValueError("unsupported single-quoted metadata value")
        return match[1].replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if not value or value[0] in "[{&*!|>@" or re.search(r":\s", value):
        raise ValueError("unsupported metadata scalar")
    return value


def _tag(value):
    value = _single_line(value, "tag", 100)
    if re.search(r"[\s,\[\]{}:#\"'|\\]", value):
        raise ValueError("tags cannot contain whitespace, YAML punctuation or a leading #")
    return value


def _comment(line):
    """Return a YAML inline comment without interpreting its quoted values."""
    quote, escaped, number = None, False, 0
    while number < len(line):
        char = line[number]
        if quote == '"':
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif quote == "'":
            if char == quote:
                if number + 1 < len(line) and line[number + 1] == quote:
                    number += 1
                else:
                    quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (number == 0 or line[number - 1].isspace()):
            return line[number:].rstrip("\r\n")
        number += 1
    return None


def _metadata(text):
    lines, end, entries = _frontmatter(text)
    result = {}
    for key in ("category", "tags"):
        if key not in entries:
            continue
        start, stop, first = entries[key]
        continuation = [line.strip() for line in lines[start + 1:stop] if line.strip() and not line.lstrip().startswith("#")]
        if key == "category":
            if continuation:
                raise ValueError("category must be a scalar")
            result[key] = _single_line(_scalar(first), "category")
        elif not first.strip() or first.lstrip().startswith("#"):
            if any(not re.match(r"^-\s+", line) for line in continuation):
                raise ValueError("tags must be a list of strings")
            indents = {len(line) - len(line.lstrip(" ")) for line in lines[start + 1:stop]
                       if line.strip() and not line.lstrip().startswith("#")}
            if len(indents) > 1:
                raise ValueError("nested tag sequences are unsupported")
            result[key] = [_tag(_scalar(re.sub(r"^-\s+", "", line))) for line in continuation]
        elif first.lstrip().startswith("["):
            if continuation:
                raise ValueError("multiline flow lists are unsupported for tags")
            try:
                values, position = json.JSONDecoder().raw_decode(first.strip())
                rest = first.strip()[position:].strip()
                if rest and not rest.startswith("#"):
                    raise ValueError("invalid tags list suffix")
            except ValueError:
                match = re.fullmatch(r"\[(.*?)\](?:\s*#.*)?", first.strip())
                if not match:
                    raise ValueError("tags must be a complete flow list") from None
                values = [_scalar(v) for v in match[1].split(",")] if match[1].strip() else []
            if not isinstance(values, list):
                raise ValueError("tags must be a list")
            result[key] = [_tag(v) for v in values]
        else:
            if continuation:
                raise ValueError("tags must be a scalar or string list")
            result[key] = [_tag(_scalar(first))]
    return lines, end, entries, result


def _update_metadata(text, category, tags):
    lines, end, entries, metadata = _metadata(text)
    replacements = {}
    if category is not None:
        value = _single_line(category, "category")
        if metadata.get("category") != value:
            replacements["category"] = _json(value)
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 100:
            raise ValueError("tags must be a list of at most 100 strings")
        values = list(dict.fromkeys(metadata.get("tags", []) + [_tag(tag) for tag in tags]))
        if values != metadata.get("tags", []):
            replacements["tags"] = _json(values)
    if not replacements:
        return text
    newline = _newline(text)
    if not end:
        return "---" + newline + "".join(f"{key}: {value}{newline}" for key, value in replacements.items()) + "---" + newline + text
    edits = {entries[key][0]: (entries[key][1], f"{key}: {value}{newline}") for key, value in replacements.items() if key in entries}
    output, number = [], 0
    while number < end - 1:
        if number in edits:
            stop, replacement = edits[number]
            output.append(replacement)
            for original in lines[number:stop]:
                if not original.strip():
                    output.append(original)
                elif original.lstrip().startswith("#"):
                    output.append(original)
                elif (comment := _comment(original)) is not None:
                    output.append(comment + newline)
            number = stop
        else:
            output.append(lines[number])
            number += 1
    output.extend(f"{key}: {value}{newline}" for key, value in replacements.items() if key not in entries)
    output.extend(lines[end - 1:])
    return "".join(output)


def _fenced(text):
    fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", text)), default=3))
    return fence + "markdown\n" + text + ("" if text.endswith(("\r", "\n")) else "\n") + fence + "\n"


def plan_init(vault):
    """Adopt a vault by appending links; existing source notes are never edited."""
    notes, _, _ = _catalog(vault, require_complete=True)
    return make_plan(vault, [_index(vault, list(notes))], "Initialize wiki index")


def plan_ingest(vault, source: Path, title: str, draft: str | None = None, source_url: str | None = None):
    root = validate_vault(vault)
    slug = _slug(title)
    source = Path(source)
    if is_link_path(source):
        raise ValueError("source must not be a symlink or reparse point")
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_NOTE_BYTES:
            raise ValueError("source must be a regular UTF-8 file of at most 2 MiB")
        raw = stream.read(MAX_NOTE_BYTES + 1)
    if len(raw) > MAX_NOTE_BYTES:
        raise ValueError("source exceeds 2 MiB")
    text = raw.decode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    capture, note = f"Sources/{digest[:16]}-{slug}.md", f"Notes/{slug}.md"
    if source_url is not None:
        source_url = _single_line(source_url, "source URL", 2000)
        parsed = urlsplit(source_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("source URL must be HTTP(S) without credentials")
    if draft is not None and (not isinstance(draft, str) or not draft.strip()):
        raise ValueError("draft must be nonempty text")
    changes = []
    capture_path = root / capture
    if capture_path.exists() or is_link_path(capture_path):
        _, previous = _read_note_text(root, Path(capture))
        if previous.encode("utf-8") != raw:
            raise ValueError("immutable source capture differs from supplied source")
    else:
        changes.append({"path": capture, "content": text})
    metadata = {"title": title.strip(), "source_path": str(source.absolute()), "source_sha256": digest, "source_capture": capture}
    if source_url:
        metadata["source_url"] = source_url
    content = "---\n" + "".join(f"{key}: {_json(value)}\n" for key, value in metadata.items()) + "---\n\n"
    content += (draft if draft is not None else f"# {title.strip()}\n\n## Source extract\n\n" + _fenced(text))
    content += "\n\n## Sources\n\n- " + _link(capture) + "\n"
    if (root / note).exists() or is_link_path(root / note):
        _, previous = _read_note_text(root, Path(note))
        _, _, entries = _frontmatter(previous)
        if ("source_sha256" not in entries or _scalar(entries["source_sha256"][2]) != digest
                or "source_capture" not in entries or _scalar(entries["source_capture"][2]) != capture):
            raise ValueError("note title already exists with different provenance; choose another title")
    else:
        changes.append({"path": note, "content": content})
    changes.append(_index(root, [note]))
    return make_plan(root, changes, "Ingest source")


def plan_save(vault, path: str, content: str, sources: list[str] | None = None):
    path = _destination(path)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("saved content must be nonempty UTF-8 Markdown")
    _, files, _ = _catalog(vault, require_complete=True)
    references = _references(sources, files, path)
    content = _append_links(content, references, "Sources", files, path)
    changes = [{"path": path, "content": content}]
    if path.casefold() != "index.md":
        changes.append(_index(vault, [path]))
    return make_plan(vault, changes, "Save note")


def plan_organize(vault, note: str, category: str | None = None, tags: list[str] | None = None, links: list[str] | None = None):
    note = _destination(note)
    _, content = _read_note_text(vault, Path(note))
    _, files, _ = _catalog(vault, require_complete=True)
    references = _references(links, files, note)
    content = _update_metadata(content, category, tags)
    content = _append_links(content, references, "Related", files, note)
    return make_plan(vault, [{"path": note, "content": content}], "Organize note")


def plan_fold(vault, notes: list[str], path: str, title: str):
    path = _destination(path)
    _single_line(title, "title")
    _, files, _ = _catalog(vault, require_complete=True)
    references = _references(notes, files)
    if not references or path in references:
        raise ValueError("fold requires source notes and a destination distinct from every child")
    passages = []
    for relative in references:
        _, text = _read_note_text(vault, Path(relative))
        for chunk in chunk_markdown(text, relative):
            passages.append(f"## {_link(relative)} — lines {chunk.start_line}–{chunk.end_line}\n\n" + _fenced(chunk.text))
    destination = validate_vault(vault) / path
    if destination.exists() or is_link_path(destination):
        _, content = _read_note_text(vault, Path(path))
    else:
        content = f"# {title.strip()}\n"
    for passage in passages:
        if passage not in content:
            content += ("\n" if content.endswith(("\n", "\r")) else "\n\n") + passage
    return plan_save(vault, path, content, sources=references)


def lint(vault) -> dict:
    notes, files, metadata_errors = _catalog(vault)
    broken, ambiguous, incoming = [], [], set()
    for path, content in sorted(notes.items()):
        try:
            _metadata(content)
        except ValueError as exc:
            metadata_errors.append({"path": path, "error": str(exc)})
        for target, line in _wikilinks(content):
            matches = _resolve(target, files, path)
            entry = {"path": path, "line": line, "target": target}
            if not matches:
                broken.append(entry)
            elif len(matches) > 1:
                ambiguous.append({**entry, "matches": matches})
            elif matches[0] != path:
                incoming.add(matches[0])
    return {"notes": len(notes), "broken_links": broken, "ambiguous_links": ambiguous,
            "orphans": sorted(path for path in set(notes) - incoming if path.casefold() != "index.md"),
            "metadata_errors": sorted(metadata_errors, key=lambda entry: entry["path"])}
