"""Reviewed Markdown changes with durable snapshots and conservative recovery.

Each note replacement is atomic; a multi-note transaction is recoverable rather
than atomically visible. The journal lock serializes toolkit writers. Existing
editors do not take that lock, so preimages are checked again at each replacement.
"""

from contextlib import contextmanager
import difflib
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
import uuid

from .vault import EXCLUDED_DIRECTORIES, MAX_NOTE_BYTES, validate_vault


MAX_CHANGES = 100
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PLAN_BYTES = 32 * 1024 * 1024
_JOURNAL = '.brain-openkit'
_TRANSACTIONS = f'{_JOURNAL}/transactions'
_HEX = re.compile(r'^[0-9a-f]{64}$')
_TRANSACTION = re.compile(r'^[0-9a-f]{32}$')
_DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', re.I)
_PLAN_KEYS = {'version', 'vault', 'label', 'changes', 'id'}
_CHANGE_KEYS = {'path', 'before', 'before_sha256', 'content', 'after_sha256', 'diff'}
_FINISHED = {'applied', 'undone', 'rolled_back'}
_IN_PROGRESS = {'prepared', 'rolling_back', 'undoing'}


def _encode(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError('plan must contain valid UTF-8 JSON data') from exc


def _hash(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def _text_bytes(text):
    if not isinstance(text, str):
        raise ValueError('note content must be a UTF-8 string')
    try:
        raw = text.encode('utf-8')
    except UnicodeError as exc:
        raise ValueError('note content must be valid UTF-8') from exc
    if len(raw) > MAX_NOTE_BYTES:
        raise ValueError('note exceeds the 2 MiB limit')
    return raw


def _path(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 1024:
        raise ValueError('note path must be a bounded relative Markdown path')
    parts = value.split('/')
    if any(not part or part.startswith('.') or part.casefold() in EXCLUDED_DIRECTORIES
           or part.rstrip(' .') != part or _DEVICE.match(part)
           or any(ord(char) < 32 or char in '\\:*?"<>|' for char in part)
           for part in parts) or not value.lower().endswith('.md'):
        raise ValueError('note path must be portable relative Markdown outside protected directories')
    return value


def _reject_link(metadata):
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
        raise ValueError('symlink and reparse paths are excluded')


def _root(vault):
    try:
        _reject_link(os.stat(vault, follow_symlinks=False))
    except FileNotFoundError as exc:
        raise ValueError('vault must be an existing directory') from exc
    return validate_vault(vault)


class _Tree:
    """Anchor POSIX operations to no-follow directory descriptors.

    Windows lacks Python's dir_fd operations. There we reject all reparse points
    and revalidate parents immediately before replacing or deleting a note.
    """

    def __init__(self, root):
        self.root = root
        self.fd = None
        if os.name != 'nt':
            self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)

    @staticmethod
    def _check_spelling(descriptor, parent, component):
        key = unicodedata.normalize('NFC', component).casefold()
        for existing in os.listdir(descriptor if descriptor is not None else parent):
            if existing != component and unicodedata.normalize('NFC', existing).casefold() == key:
                raise ValueError('path aliases an existing name with different spelling')

    @contextmanager
    def parent(self, relative, create=False):
        parts = relative.split('/')
        current = self.root
        descriptor = os.dup(self.fd) if self.fd is not None else None
        try:
            root_meta = os.stat(self.root, follow_symlinks=False)
            _reject_link(root_meta)
            if not stat.S_ISDIR(root_meta.st_mode):
                raise ValueError('vault directory changed')
            if descriptor is not None and not os.path.samestat(root_meta, os.fstat(self.fd)):
                raise ValueError('vault directory changed')
            for part in parts[:-1]:
                self._check_spelling(descriptor, current, part)
                current = current / part
                if descriptor is not None:
                    try:
                        next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                          dir_fd=descriptor)
                    except FileNotFoundError:
                        if not create:
                            raise
                        os.mkdir(part, mode=0o700, dir_fd=descriptor)
                        os.fsync(descriptor)
                        next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                          dir_fd=descriptor)
                    os.close(descriptor)
                    descriptor = next_fd
                else:
                    try:
                        metadata = os.stat(current, follow_symlinks=False)
                    except FileNotFoundError:
                        if not create:
                            raise
                        current.mkdir(mode=0o700)
                        metadata = os.stat(current, follow_symlinks=False)
                    _reject_link(metadata)
                    if not stat.S_ISDIR(metadata.st_mode):
                        raise ValueError('note parent must be a directory')
            self._check_spelling(descriptor, current, parts[-1])
            yield descriptor, current, parts[-1]
        except (NotADirectoryError, IsADirectoryError) as exc:
            raise ValueError('note and journal paths must not contain links or non-directories') from exc
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError('symlink paths are excluded') from exc
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def ensure_dir(self, relative):
        with self.parent(relative + '/unused', create=True):
            pass

    @staticmethod
    def _at(descriptor, parent, leaf):
        return (leaf, {'dir_fd': descriptor}) if descriptor is not None else (parent / leaf, {})

    def _read_at(self, descriptor, parent, leaf, limit):
        location, arguments = self._at(descriptor, parent, leaf)
        try:
            metadata = os.stat(location, follow_symlinks=False, **arguments)
        except FileNotFoundError:
            return None
        _reject_link(metadata)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError('note and journal entries must be regular files')
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
        fd = os.open(location, flags, **arguments)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
                raise ValueError('file changed while opening')
            if opened.st_size > limit:
                raise ValueError('file exceeds the read limit')
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('file exceeds the read limit')
        return raw

    def read(self, relative, limit=MAX_NOTE_BYTES):
        try:
            with self.parent(relative) as (descriptor, parent, leaf):
                return self._read_at(descriptor, parent, leaf, limit)
        except FileNotFoundError:
            return None

    def _verify_parent(self, relative, descriptor, parent):
        with self.parent(relative) as (current_fd, current_path, _):
            first = os.fstat(descriptor) if descriptor is not None else os.stat(parent, follow_symlinks=False)
            second = os.fstat(current_fd) if current_fd is not None else os.stat(current_path, follow_symlinks=False)
            if not os.path.samestat(first, second):
                raise ValueError('note parent changed during transaction')

    def write(self, relative, raw, expected, limit=MAX_NOTE_BYTES):
        with self.parent(relative, create=True) as (descriptor, parent, leaf):
            if self._read_at(descriptor, parent, leaf, limit) != expected:
                raise ValueError(f'content conflict: {relative}')
            temporary = '.brain-openkit-' + uuid.uuid4().hex + '.tmp'
            location, arguments = self._at(descriptor, parent, temporary)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
            fd = os.open(location, flags, 0o600, **arguments)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    if expected is not None and hasattr(os, 'fchmod'):
                        target, target_args = self._at(descriptor, parent, leaf)
                        mode = stat.S_IMODE(os.stat(target, follow_symlinks=False, **target_args).st_mode)
                        os.fchmod(stream.fileno(), mode)
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._verify_parent(relative, descriptor, parent)
                if self._read_at(descriptor, parent, leaf, limit) != expected:
                    raise ValueError(f'content conflict: {relative}')
                if descriptor is not None:
                    os.replace(temporary, leaf, src_dir_fd=descriptor, dst_dir_fd=descriptor)
                    os.fsync(descriptor)
                else:
                    os.replace(parent / temporary, parent / leaf)
            finally:
                try:
                    os.unlink(location, **arguments)
                except FileNotFoundError:
                    pass

    def delete(self, relative, expected):
        with self.parent(relative) as (descriptor, parent, leaf):
            self._verify_parent(relative, descriptor, parent)
            if self._read_at(descriptor, parent, leaf, MAX_NOTE_BYTES) != expected:
                raise ValueError(f'content conflict: {relative}')
            location, arguments = self._at(descriptor, parent, leaf)
            os.unlink(location, **arguments)
            if descriptor is not None:
                os.fsync(descriptor)

    def list_records(self):
        with self.parent(_TRANSACTIONS + '/unused') as (descriptor, parent, _):
            return sorted(os.listdir(descriptor if descriptor is not None else parent))


@contextmanager
def _journal_lock(root):
    tree = _Tree(_root(root))
    fd = None
    locked = False
    try:
        with tree.parent(_JOURNAL + '/lock', create=True) as (descriptor, parent, leaf):
            location, arguments = tree._at(descriptor, parent, leaf)
            try:
                metadata = os.stat(location, follow_symlinks=False, **arguments)
            except FileNotFoundError:
                metadata = None
            if metadata is not None:
                _reject_link(metadata)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError('journal lock must be a regular file')
            fd = os.open(location, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
                         | getattr(os, 'O_BINARY', 0), 0o600, **arguments)
            opened = os.fstat(fd)
            current = os.stat(location, follow_symlinks=False, **arguments)
            _reject_link(current)
            if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(opened, current):
                raise ValueError('journal lock changed while opening')
            if opened.st_size == 0:
                os.write(fd, b'\0')
                os.fsync(fd)
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                raise ValueError('vault change journal is busy; retry after the other writer finishes') from exc
        tree.ensure_dir(_TRANSACTIONS)
        yield tree
    finally:
        if fd is not None:
            if locked:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        tree.close()


def _plan_id(payload):
    raw = _encode(payload)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError('serialized plan exceeds the 32 MiB limit')
    return hashlib.sha256(raw).hexdigest()


def make_plan(vault: Path, changes: list[dict], label: str) -> dict:
    """Preview exact UTF-8 replacements without creating files or a journal."""
    root = _root(vault)
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise ValueError('plan label must contain 1 to 200 characters')
    if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
        raise ValueError('plan must contain at most 100 changes')
    entries, seen, total = [], set(), 0
    tree = _Tree(root)
    try:
        for change in changes:
            if not isinstance(change, dict) or set(change) != {'path', 'content'}:
                raise ValueError('each change must contain only path and content')
            relative = _path(change['path'])
            key = unicodedata.normalize('NFC', relative).casefold()
            if key in seen:
                raise ValueError('duplicate or case-equivalent note paths')
            seen.add(key)
            after = _text_bytes(change['content'])
            before = tree.read(relative)
            try:
                previous = before.decode('utf-8') if before is not None else None
            except UnicodeError as exc:
                raise ValueError('existing note must contain valid UTF-8') from exc
            total += len(after) + (len(before) if before is not None else 0)
            if total > MAX_IMAGE_BYTES:
                raise ValueError('plan preimages and postimages exceed the 16 MiB limit')
            if before == after:
                continue
            diff = ''.join(difflib.unified_diff((previous or '').splitlines(keepends=True),
                           change['content'].splitlines(keepends=True),
                           fromfile=relative if before is not None else '/dev/null', tofile=relative))
            entries.append({'path': relative, 'before': previous, 'before_sha256': _hash(before),
                            'content': change['content'], 'after_sha256': _hash(after), 'diff': diff})
    finally:
        tree.close()
    payload = {'version': 1, 'vault': str(root), 'label': label, 'changes': entries}
    return dict(payload, id=_plan_id(payload))


def _validate_plan(root, plan, expected_id):
    if not isinstance(plan, dict) or set(plan) != _PLAN_KEYS:
        raise ValueError('invalid plan schema')
    if type(plan['version']) is not int or plan['version'] != 1 or plan['vault'] != str(root):
        raise ValueError('plan version or vault does not match')
    if not isinstance(expected_id, str) or not _HEX.fullmatch(expected_id) or plan['id'] != expected_id:
        raise ValueError('explicit approval must match the reviewed plan ID')
    if _plan_id({key: value for key, value in plan.items() if key != 'id'}) != expected_id:
        raise ValueError('plan changed after preview')
    if not isinstance(plan['label'], str) or not plan['label'].strip() or len(plan['label']) > 200:
        raise ValueError('invalid plan label')
    if not isinstance(plan['changes'], list) or len(plan['changes']) > MAX_CHANGES:
        raise ValueError('plan must contain at most 100 changes')
    seen, total = set(), 0
    for change in plan['changes']:
        if not isinstance(change, dict) or set(change) != _CHANGE_KEYS:
            raise ValueError('invalid change schema')
        relative = _path(change['path'])
        key = unicodedata.normalize('NFC', relative).casefold()
        if key in seen:
            raise ValueError('duplicate note paths')
        seen.add(key)
        before = _text_bytes(change['before']) if change['before'] is not None else None
        after = _text_bytes(change['content'])
        total += len(after) + (len(before) if before is not None else 0)
        if total > MAX_IMAGE_BYTES or before == after:
            raise ValueError('plan exceeds image limit or contains unchanged entries')
        if _hash(before) != change['before_sha256'] or _hash(after) != change['after_sha256']:
            raise ValueError('plan content hashes do not match')
        if not isinstance(change['diff'], str):
            raise ValueError('plan diff must be text')


def _images(change):
    return (change['before'].encode('utf-8') if change['before'] is not None else None,
            change['content'].encode('utf-8'))


def _preflight(tree, plan, kind):
    conflicts = []
    for change in plan['changes']:
        before, after = _images(change)
        actual = tree.read(change['path'])
        acceptable = (before,) if kind == 'apply' else (after,) if kind == 'undo' else (before, after)
        if actual not in acceptable:
            conflicts.append(change['path'])
    if conflicts:
        raise ValueError('content conflict: ' + ', '.join(conflicts))


def _record_path(identifier):
    if not isinstance(identifier, str) or not _TRANSACTION.fullmatch(identifier):
        raise ValueError('invalid transaction ID')
    return f'{_TRANSACTIONS}/{identifier}.json'


def _save_record(tree, record):
    relative = _record_path(record['transaction_id'])
    previous = tree.read(relative, MAX_PLAN_BYTES + 4096)
    tree.write(relative, _encode(record), previous, MAX_PLAN_BYTES + 4096)


def _load_record(tree, identifier):
    raw = tree.read(_record_path(identifier), MAX_PLAN_BYTES + 4096)
    if raw is None:
        raise ValueError('transaction not found')
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid transaction journal') from exc
    if (not isinstance(record, dict) or set(record) != {'transaction_id', 'status', 'plan'}
            or record['transaction_id'] != identifier or not isinstance(record['status'], str)
            or record['status'] not in _FINISHED | _IN_PROGRESS):
        raise ValueError('invalid transaction journal')
    _validate_plan(tree.root, record['plan'], record['plan'].get('id') if isinstance(record['plan'], dict) else None)
    return record


def _check_pending(tree):
    for name in tree.list_records():
        if name.endswith('.json') and _TRANSACTION.fullmatch(name[:-5]):
            record = _load_record(tree, name[:-5])
            if record['status'] in _IN_PROGRESS:
                raise ValueError(f'recovery required for transaction {record["transaction_id"]}')


def _result(record):
    return {'transaction_id': record['transaction_id'], 'status': record['status'],
            'paths': [change['path'] for change in record['plan']['changes']]}


def _restore(tree, record):
    _preflight(tree, record['plan'], 'recover')
    for change in reversed(record['plan']['changes']):
        before, after = _images(change)
        actual = tree.read(change['path'])
        if actual == before:
            continue
        if actual != after:
            raise ValueError(f'content conflict: {change["path"]}')
        if before is None:
            tree.delete(change['path'], after)
        else:
            tree.write(change['path'], before, after)
    record['status'] = 'undone' if record['status'] == 'undoing' else 'rolled_back'
    _save_record(tree, record)
    return _result(record)


def apply_plan(vault: Path, plan: dict, expected_id: str) -> dict:
    """Apply a specific reviewed ID after checking every original note."""
    root = _root(vault)
    plan = json.loads(_encode(plan))
    _validate_plan(root, plan, expected_id)
    if not plan['changes']:
        return {'transaction_id': None, 'status': 'unchanged', 'paths': []}
    with _journal_lock(root) as tree:
        _check_pending(tree)
        _preflight(tree, plan, 'apply')
        # Freeze caller-owned data before persisting or starting note mutations.
        record = {'transaction_id': uuid.uuid4().hex, 'status': 'prepared',
                  'plan': json.loads(_encode(plan))}
        _save_record(tree, record)
        try:
            for change in record['plan']['changes']:
                before, after = _images(change)
                tree.write(change['path'], after, before)
            record['status'] = 'applied'
            _save_record(tree, record)
        except Exception as exc:
            try:
                record['status'] = 'rolling_back'
                _save_record(tree, record)
                _restore(tree, record)
            except Exception as recovery_error:
                raise ValueError(f'apply failed; recovery required for transaction {record["transaction_id"]}: {recovery_error}') from exc
            raise ValueError(f'apply failed and was rolled back; transaction {record["transaction_id"]}') from exc
        return _result(record)


def undo(vault: Path, transaction_id: str) -> dict:
    """Undo only when every affected note still has its recorded postimage."""
    _record_path(transaction_id)
    with _journal_lock(_root(vault)) as tree:
        record = _load_record(tree, transaction_id)
        if record['status'] == 'undone':
            return _result(record)
        if record['status'] != 'applied':
            raise ValueError('transaction is not applied; use recover for interrupted work')
        _check_pending(tree)
        _preflight(tree, record['plan'], 'undo')
        record['status'] = 'undoing'
        _save_record(tree, record)
        try:
            return _restore(tree, record)
        except Exception as exc:
            raise ValueError(f'undo interrupted; recovery required for transaction {transaction_id}: {exc}') from exc


def recover(vault: Path, transaction_id: str) -> dict:
    """Finish rollback/undo after interruption, refusing all external edits."""
    _record_path(transaction_id)
    with _journal_lock(_root(vault)) as tree:
        record = _load_record(tree, transaction_id)
        if record['status'] in {'rolled_back', 'undone'}:
            return _result(record)
        if record['status'] == 'applied':
            raise ValueError('transaction completed successfully; use undo to reverse it')
        try:
            return _restore(tree, record)
        except Exception as exc:
            raise ValueError(f'recovery conflict or failure in transaction {transaction_id}: {exc}') from exc
