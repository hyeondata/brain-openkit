"""Read Markdown without changing the bytes used for source citations."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat


MAX_NOTE_BYTES = 2 * 1024 * 1024
EXCLUDED_DIRECTORIES = {"__pycache__", "node_modules"}
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True)
class Chunk:
    path: str
    title: str
    start_line: int
    end_line: int
    text: str


def is_link_path(path: Path) -> bool:
    """Reject symlinks and Windows reparse points, including directory junctions."""
    try:
        metadata = Path(path).lstat()
    except FileNotFoundError:
        return False
    return (stat.S_ISLNK(metadata.st_mode)
            or bool(getattr(metadata, "st_file_attributes", 0) & 0x400))


def validate_vault(vault: Path) -> Path:
    vault = Path(vault)
    if is_link_path(vault) or not vault.is_dir():
        raise ValueError("vault must be an existing directory, not a symlink or reparse point")
    return vault.resolve()


def _read_note_text(vault: Path, path: Path) -> tuple[str, str]:
    supplied_root = Path(vault).absolute()
    root = validate_vault(vault)
    path = Path(path)
    try:
        relative = path.relative_to(supplied_root) if path.is_absolute() else path
    except ValueError as exc:
        raise ValueError("note must be inside the vault") from exc
    if not relative.parts or ".." in relative.parts:
        raise ValueError("note must be inside the vault")
    if relative.suffix.lower() != ".md" or any(
        part.startswith(".") or part in EXCLUDED_DIRECTORIES for part in relative.parts
    ):
        raise ValueError("note must be Markdown outside hidden and cache directories")
    candidate = root
    for component in relative.parts:
        candidate = candidate / component
        if is_link_path(candidate):
            raise ValueError("symlink and reparse notes and directories are excluded")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(candidate, flags)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("note must be a regular file")
        if metadata.st_size > MAX_NOTE_BYTES:
            raise ValueError("note exceeds the 2 MiB read limit")
        raw = stream.read(MAX_NOTE_BYTES + 1)
    if len(raw) > MAX_NOTE_BYTES:
        raise ValueError("note exceeds the 2 MiB read limit")
    return relative.as_posix(), raw.decode("utf-8")


def read_note(vault: Path, path: Path) -> list[Chunk]:
    relative, text = _read_note_text(vault, path)
    return chunk_markdown(text, relative)


def chunk_markdown(text: str, path: str, max_chars: int = 1200) -> list[Chunk]:
    """Prefer Markdown boundaries while keeping exact, inclusive line slices.

    A single oversized line remains intact. Model adapters must reject inputs
    exceeding their own budgets instead of silently truncating that evidence.
    """
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if not text.strip():
        return []
    # Markdown line positions use CR/LF, not splitlines()' Unicode controls.
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)
    title = Path(path).stem
    metadata_end = 0
    if lines[0].strip().lstrip("\ufeff") == "---":
        for number, line in enumerate(lines[1:], 1):
            if line.strip() in ("---", "..."):
                metadata_end = number + 1
                break
    metadata_title = None
    for line in lines[1:metadata_end - 1] if metadata_end else []:
        match = re.match(r"^title:\s*(.*?)\s*$", line)
        if match and match[1] and match[1] not in ("|", ">"):
            metadata_title = match[1].strip("\"'")

    # Blocks are intervals into the original lines, never rewritten strings.
    boundaries = {0, len(lines)}
    if metadata_end:
        boundaries.add(metadata_end)
    fence = None
    heading_starts = set()
    first_heading = None
    for number in range(metadata_end, len(lines)):
        line = lines[number]
        marker = _FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = None
                boundaries.add(number + 1)
            continue
        if marker:
            boundaries.add(number)
            fence = marker[1]
            continue
        heading = _HEADING.match(line.rstrip("\r\n"))
        if heading:
            if first_heading is None:
                first_heading = heading[1]
            boundaries.add(number)
            heading_starts.add(number)
        elif not line.strip():
            boundaries.add(number + 1)
    title = metadata_title or first_heading or title

    # Split oversized blocks only between lines; then pack short paragraphs.
    spans = []
    ordered = sorted(boundaries)
    for start, end in zip(ordered, ordered[1:]):
        piece_start, size = start, 0
        for number in range(start, end):
            if size and size + len(lines[number]) > max_chars:
                spans.append((piece_start, number))
                piece_start, size = number, 0
            size += len(lines[number])
        spans.append((piece_start, end))
    chunks = []
    start, end, size = 0, 0, 0
    for next_start, next_end in spans:
        next_size = sum(len(line) for line in lines[next_start:next_end])
        if size and (size + next_size > max_chars or next_start in heading_starts):
            chunks.append(Chunk(path, title, start + 1, end, "".join(lines[start:end])))
            start, size = next_start, 0
        end = next_end
        size += next_size
    if size:
        chunks.append(Chunk(path, title, start + 1, end, "".join(lines[start:end])))
    return chunks
