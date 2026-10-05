"""Opt-in, bounded local conversation snapshots without model or network calls.

The quota covers final archive-file bytes, configuration bytes, and the shared
lock byte. Atomic replacement temporarily needs one additional snapshot (at most
2 MiB). Directory metadata and journals belonging to other workflows are not
part of this quota. No per-turn journal or transcript registry is created.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import stat

from .changes import _Tree, _journal_lock, _reject_link, _root
from .vault import MAX_NOTE_BYTES


ARCHIVE_DIR = 'Inbox/Conversations'
CONFIG_PATH = '.brain-openkit/conversations.json'
DEFAULT_CONFIG = {
    'enabled': False,
    'max_bytes': 100 * 1024 * 1024,
    'include_tool_output': False,
    'retention_days': 0,
    'auto_prune': False,
}
MAX_CONFIG_BYTES = 4096
MAX_MESSAGES = 10000
MAX_ARCHIVE_ENTRIES = 10000
_HOST = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')
_FILE = re.compile(r'^([a-z][a-z0-9_-]{0,31})-([0-9a-f]{64})\.md$')
_HEX = re.compile(r'^[0-9a-f]{64}$')
_PREFIX = b'<!-- brain-openkit-conversation-v1\n'
_END = b'\n-->\n'
_META_KEYS = {'host', 'session_hash', 'message_count', 'history_sha256',
              'updated_at', 'body_sha256', 'metadata_sha256'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


@contextmanager
def _reader(root):
    tree = _Tree(root)
    try:
        yield tree
    finally:
        tree.close()


def _regular(tree, relative):
    try:
        with tree.parent(relative) as (descriptor, parent, leaf):
            location, kwargs = tree._at(descriptor, parent, leaf)
            metadata = os.stat(location, follow_symlinks=False, **kwargs)
            _reject_link(metadata)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError('conversation files must be regular files without hardlinks')
            return metadata
    except FileNotFoundError:
        return None


def _validate_config(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULT_CONFIG):
        raise ValueError('unknown or missing conversation configuration field')
    for key in ('enabled', 'include_tool_output', 'auto_prune'):
        if type(config[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    if type(config['max_bytes']) is not int or not 1 <= config['max_bytes'] <= 2 ** 40:
        raise ValueError('max_bytes must be a positive integer no larger than 1 TiB')
    if type(config['retention_days']) is not int or not 0 <= config['retention_days'] <= 36500:
        raise ValueError('retention_days must be an integer between 0 and 36500')
    if config['auto_prune'] and not config['retention_days']:
        raise ValueError('auto_prune requires a positive retention_days setting')
    return config


def _read_config(tree):
    _regular(tree, CONFIG_PATH)
    raw = tree.read(CONFIG_PATH, MAX_CONFIG_BYTES)
    if raw is None:
        return dict(DEFAULT_CONFIG), None
    try:
        config = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique)
        return _validate_config(config), raw
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid conversation configuration') from exc


def _lock_size(tree):
    metadata = _regular(tree, '.brain-openkit/lock')
    if metadata is not None and metadata.st_size > 1:
        raise ValueError('conversation writer requires a canonical zero-or-one-byte journal lock')
    return 0 if metadata is None else metadata.st_size


def _scan(tree):
    """Count even unknown and temporary files without following directory links."""
    files = []
    pending = [ARCHIVE_DIR]
    entries_seen = 0
    while pending:
        directory = pending.pop()
        try:
            with tree.parent(directory + '/.scan') as (descriptor, parent, _):
                names = sorted(os.listdir(descriptor if descriptor is not None else parent))
                entries_seen += len(names)
                if entries_seen > MAX_ARCHIVE_ENTRIES:
                    raise ValueError('conversation archive exceeds the 10000-entry scan limit')
                for name in names:
                    location, kwargs = tree._at(descriptor, parent, name)
                    metadata = os.stat(location, follow_symlinks=False, **kwargs)
                    _reject_link(metadata)
                    path = directory + '/' + name
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(path)
                    elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                        files.append((path, metadata.st_size))
                    else:
                        raise ValueError('conversation archive contains a special file or hardlink')
        except FileNotFoundError:
            if directory != ARCHIVE_DIR:
                raise ValueError('conversation archive changed during scan') from None
    return files


def _info(tree, config, raw):
    files = _scan(tree)
    used = sum(size for _, size in files) + len(raw or b'') + _lock_size(tree)
    return {'enabled': config['enabled'], 'config': dict(config),
            'archive_dir': ARCHIVE_DIR, 'used_bytes': used,
            'max_bytes': config['max_bytes'], 'file_count': len(files),
            'capacity_exceeded': used > config['max_bytes']}


def status(vault):
    """Inspect configuration and byte usage without creating any files."""
    with _reader(_root(vault)) as tree:
        return _info(tree, *_read_config(tree))


def configure(vault, **changes):
    """Persist explicit settings. Disabling never deletes existing snapshots."""
    root = _root(vault)
    with _reader(root) as tree:
        config, _ = _read_config(tree)
        _validate_config(dict(config, **changes))
        _lock_size(tree)
        _scan(tree)
    if not changes:
        return status(root)
    with _journal_lock(root) as tree:
        current, before = _read_config(tree)
        config = _validate_config(dict(current, **changes))
        _scan(tree)
        raw = _json(config) + b'\n'
        if raw != before:
            tree.write(CONFIG_PATH, raw, before, limit=MAX_CONFIG_BYTES)
        return _info(tree, config, raw)


def _time(now):
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, str):
        try:
            now = datetime.fromisoformat(now.replace('Z', '+00:00'))
        except ValueError as exc:
            raise ValueError('now must be an ISO timestamp with a timezone') from exc
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must include a timezone')
    return now.astimezone(timezone.utc)


def _timestamp(now):
    return now.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def _messages(messages, include_tool_output):
    if not isinstance(messages, list):
        raise ValueError('messages must be a complete list of role/text objects')
    if len(messages) > MAX_MESSAGES:
        return None
    result = []
    total = 0
    for message in messages:
        if not isinstance(message, dict) or set(message) != {'role', 'text'}:
            raise ValueError('each message must contain only role and text')
        role = message['role']
        if role not in ('user', 'assistant', 'tool') or not isinstance(message['text'], str):
            raise ValueError('message role must be user, assistant, or tool and text must be a string')
        if role == 'tool' and not include_tool_output:
            continue
        text = message['text']
        if len(text) > MAX_NOTE_BYTES:
            return None
        try:
            total += len(text.encode('utf-8'))
        except UnicodeError as exc:
            raise ValueError('message text must be valid UTF-8') from exc
        if total > MAX_NOTE_BYTES:
            return None
        result.append({'role': role, 'text': text})
    return result


def _body(host, messages):
    parts = [f'# Conversation archive — {host}\n\n']
    for number, message in enumerate(messages, 1):
        text = message['text']
        longest = max((len(run) for run in re.findall(r'`+', text)), default=0)
        fence = '`' * max(3, longest + 1)
        parts.append(f'## {number}. {message["role"]}\n\n{fence}text\n{text}\n{fence}\n\n')
    return ''.join(parts).encode('utf-8')


def _render(host, session_hash, messages, now):
    body = _body(host, messages)
    metadata = {'host': host, 'session_hash': session_hash,
                'message_count': len(messages), 'history_sha256': _sha(_json(messages)),
                'updated_at': _timestamp(now), 'body_sha256': _sha(body)}
    metadata['metadata_sha256'] = _sha(_json(metadata))
    return _PREFIX + _json(metadata) + _END + body


def _managed(raw, path):
    """Return verified ownership metadata, or None for edits/unmanaged files."""
    if raw is None or not raw.startswith(_PREFIX) or len(raw) > MAX_NOTE_BYTES:
        return None
    match = _FILE.fullmatch(path.removeprefix(ARCHIVE_DIR + '/'))
    if not match:
        return None
    header, separator, body = raw[len(_PREFIX):].partition(_END)
    if not separator or len(header) > MAX_CONFIG_BYTES:
        return None
    try:
        metadata = json.loads(header.decode('utf-8'), object_pairs_hook=_unique)
        if not isinstance(metadata, dict) or set(metadata) != _META_KEYS:
            return None
        if (metadata['host'], metadata['session_hash']) != match.groups():
            return None
        if type(metadata['message_count']) is not int or not 0 <= metadata['message_count'] <= MAX_MESSAGES:
            return None
        if any(not isinstance(metadata[key], str) or not _HEX.fullmatch(metadata[key])
               for key in ('history_sha256', 'body_sha256', 'metadata_sha256')):
            return None
        if not isinstance(metadata['updated_at'], str):
            return None
        if _timestamp(_time(metadata['updated_at'])) != metadata['updated_at']:
            return None
        unsigned = {key: value for key, value in metadata.items() if key != 'metadata_sha256'}
        if _sha(_json(unsigned)) != metadata['metadata_sha256'] or _sha(body) != metadata['body_sha256']:
            return None
        if _PREFIX + _json(metadata) + _END + body != raw:
            return None
        return metadata
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return None


def _eligible(tree, files, config, now, exclude=None):
    if not config['retention_days']:
        return []
    cutoff = now - timedelta(days=config['retention_days'])
    eligible = []
    read_bytes = 0
    for path, size in files:
        if path == exclude or size > MAX_NOTE_BYTES or not _FILE.fullmatch(path.removeprefix(ARCHIVE_DIR + '/')):
            continue
        # Limit one cleanup to a bounded amount of content even if a user has
        # manually filled the archive beyond its configured quota.
        read_bytes += size
        if read_bytes > DEFAULT_CONFIG['max_bytes']:
            raise ValueError('retention inspection exceeds the 100 MiB read limit')
        raw = tree.read(path)
        metadata = _managed(raw, path)
        if metadata is not None and _time(metadata['updated_at']) < cutoff:
            eligible.append((path, raw))
    return eligible


def capture(vault, host, session_id, messages, *, now=None):
    """Archive a full append-compatible snapshot, or report why it was skipped."""
    root = _root(vault)
    with _reader(root) as tree:
        config, _ = _read_config(tree)
        if not config['enabled']:
            return {'status': 'disabled'}
        _lock_size(tree)
    if not isinstance(host, str) or not _HOST.fullmatch(host):
        raise ValueError('host must be a portable lowercase identifier of at most 32 characters')
    if not isinstance(session_id, str) or not session_id or len(session_id) > 1024:
        raise ValueError('session_id must be a nonempty string of at most 1024 characters')
    try:
        session_hash = _sha(session_id.encode('utf-8'))
    except UnicodeError as exc:
        raise ValueError('session_id must be valid UTF-8') from exc
    path = f'{ARCHIVE_DIR}/{host}-{session_hash}.md'
    at = _time(now)
    with _journal_lock(root) as tree:
        config, config_raw = _read_config(tree)
        if not config['enabled']:
            return {'status': 'disabled'}
        selected = _messages(messages, config['include_tool_output'])
        if selected is None:
            return {'status': 'blocked', 'reason': 'session_limit', 'path': path}
        _regular(tree, path)
        before = tree.read(path)
        previous = _managed(before, path)
        if before is not None:
            if previous is None:
                return {'status': 'blocked', 'reason': 'edited', 'path': path}
            count = previous['message_count']
            if len(selected) < count or _sha(_json(selected[:count])) != previous['history_sha256']:
                return {'status': 'blocked', 'reason': 'history_conflict', 'path': path}
            if len(selected) == count:
                return {'status': 'unchanged', 'path': path, 'message_count': count, 'pruned': []}
        if not selected:
            return {'status': 'unchanged', 'path': path, 'message_count': 0, 'pruned': []}
        updated_at = max(at, _time(previous['updated_at'])) if previous is not None else at
        raw = _render(host, session_hash, selected, updated_at)
        if len(raw) > MAX_NOTE_BYTES:
            return {'status': 'blocked', 'reason': 'session_limit', 'path': path}
        files = _scan(tree)
        used = sum(size for _, size in files) + len(config_raw or b'') + _lock_size(tree)
        candidates = _eligible(tree, files, config, at, exclude=path) if config['auto_prune'] else []
        projected = used - len(before or b'') + len(raw) - sum(len(data) for _, data in candidates)
        if projected > config['max_bytes']:
            return {'status': 'blocked', 'reason': 'size_limit', 'path': path,
                    'used_bytes': used, 'required_bytes': projected, 'max_bytes': config['max_bytes']}
        for old_path, data in candidates:
            tree.delete(old_path, data)
        tree.write(path, raw, before)
        return {'status': 'saved', 'path': path, 'message_count': len(selected),
                'bytes': len(raw), 'used_bytes': projected, 'max_bytes': config['max_bytes'],
                'pruned': [name for name, _ in candidates]}


def prune(vault, apply=False, *, now=None):
    """Preview or explicitly delete old, unedited snapshots; retention defaults off."""
    if type(apply) is not bool:
        raise ValueError('apply must be boolean')
    root = _root(vault)
    at = _time(now)
    with _reader(root) as tree:
        config, _ = _read_config(tree)
        candidates = _eligible(tree, _scan(tree), config, at)
        _lock_size(tree)
    if not apply or not candidates:
        return {'status': 'preview' if not apply else 'unchanged',
                'paths': [path for path, _ in candidates],
                'bytes': sum(len(raw) for _, raw in candidates)}
    with _journal_lock(root) as tree:
        config, _ = _read_config(tree)
        candidates = _eligible(tree, _scan(tree), config, at)
        for path, raw in candidates:
            tree.delete(path, raw)
        return {'status': 'pruned', 'paths': [path for path, _ in candidates],
                'bytes': sum(len(raw) for _, raw in candidates)}
