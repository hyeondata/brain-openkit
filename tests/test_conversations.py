import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit import changes, notes

if importlib.util.find_spec('brain_openkit.conversations'):
    from brain_openkit import conversations
else:
    conversations = None


class ConversationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(conversations, 'conversation archive core is not implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / 'vault'
        self.vault.mkdir()
        self.first = [{'role': 'user', 'text': '원문\r\n[[not-a-link]]\n```\nkeep this'}]
        self.second = self.first + [{'role': 'assistant', 'text': 'Saved response.'}]

    def enable(self, **kwargs):
        return conversations.configure(self.vault, enabled=True, **kwargs)

    def capture(self, messages=None, session='session-a', **kwargs):
        return conversations.capture(self.vault, 'claude', session,
                                     self.first if messages is None else messages, **kwargs)

    def files(self):
        return {str(p.relative_to(self.vault)): p.read_bytes()
                for p in self.vault.rglob('*') if p.is_file()}

    def test_disabled_and_status_do_not_create_files_or_inspect_messages(self):
        class Unreadable:
            def __iter__(self):
                raise AssertionError('disabled capture must not inspect messages')
        result = conversations.capture(self.vault, 'claude', 'session', Unreadable())
        self.assertEqual('disabled', result['status'])
        self.assertFalse(conversations.status(self.vault)['enabled'])
        self.assertEqual([], list(self.vault.iterdir()))

    def test_full_snapshots_update_one_file_and_duplicate_is_byte_identical(self):
        self.enable()
        result = self.capture(now='2026-10-05T00:00:00Z')
        path = self.vault / result['path']
        self.assertEqual('saved', result['status'])
        self.assertEqual('claude-' + hashlib.sha256(b'session-a').hexdigest() + '.md', path.name)
        self.assertIn(self.first[0]['text'].encode(), path.read_bytes())
        self.assertIn(b'````text\n', path.read_bytes())
        original = path.read_bytes()
        self.assertEqual('unchanged', self.capture(now='2026-10-06T00:00:00Z')['status'])
        self.assertEqual(original, path.read_bytes())
        self.assertEqual('saved', self.capture(self.second, now='2026-10-06T00:00:00Z')['status'])
        self.assertIn(b'Saved response.', path.read_bytes())
        self.assertEqual(1, len(list((self.vault / 'Inbox/Conversations').glob('*.md'))))
        self.assertEqual([], list((self.vault / '.brain-openkit/transactions').glob('*.json')))

    def test_shortened_replaced_and_edited_snapshots_preserve_existing_file(self):
        self.enable()
        result = self.capture(self.second)
        before = self.files()
        for messages in [self.first, [{'role': 'user', 'text': 'different'}]]:
            self.assertEqual('history_conflict', self.capture(messages)['reason'])
            self.assertEqual(before, self.files())
        path = self.vault / result['path']
        path.write_bytes(path.read_bytes() + b'Human addition\n')
        edited = self.files()
        self.assertEqual('edited', self.capture(self.second + [{'role': 'user', 'text': 'next'}])['reason'])
        self.assertEqual(edited, self.files())

    def test_header_edit_is_preserved_even_when_body_is_unchanged(self):
        self.enable()
        result = self.capture(now='2026-10-05T00:00:00Z')
        path = self.vault / result['path']
        raw = path.read_bytes().replace(b'2026-10-05', b'2020-10-05')
        path.write_bytes(raw)
        self.assertEqual('edited', self.capture(self.second)['reason'])
        self.assertEqual(raw, path.read_bytes())

    def test_capacity_accounts_for_unmanaged_nested_files_and_stops_without_deleting(self):
        self.enable(max_bytes=4096)
        result = self.capture()
        folder = self.vault / 'Inbox/Conversations/other'
        folder.mkdir()
        (folder / 'unmanaged.bin').write_bytes(b'x' * 4096)
        before = self.files()
        self.assertEqual('size_limit', self.capture(self.second)['reason'])
        self.assertEqual(before, self.files())
        info = conversations.status(self.vault)
        self.assertEqual(sum(len(raw) for raw in before.values()), info['used_bytes'])
        self.assertTrue(info['capacity_exceeded'])
        self.assertTrue((self.vault / result['path']).exists())

    def test_session_limit_and_large_messages_do_not_replace_prior_snapshot(self):
        self.enable()
        self.capture()
        before = self.files()
        result = self.capture(self.second + [{'role': 'user', 'text': 'x' * (2 * 1024 * 1024)}])
        self.assertEqual('session_limit', result['reason'])
        self.assertEqual(before, self.files())

    def test_tool_output_is_excluded_unless_explicitly_enabled(self):
        self.enable()
        messages = self.first + [{'role': 'tool', 'text': 'tool secret'}]
        result = self.capture(messages)
        self.assertNotIn(b'tool secret', (self.vault / result['path']).read_bytes())
        self.assertEqual('unchanged', self.capture(messages)['status'])
        conversations.configure(self.vault, include_tool_output=True)
        result = self.capture(messages)
        self.assertEqual('saved', result['status'])
        self.assertIn(b'tool secret', (self.vault / result['path']).read_bytes())

    def test_disabling_preserves_archive_and_does_not_validate_payload(self):
        self.enable()
        self.capture()
        conversations.configure(self.vault, enabled=False)
        before = self.files()
        self.assertEqual('disabled', self.capture(object())['status'])
        self.assertEqual(before, self.files())

    def test_retention_requires_configuration_and_preview_does_not_mutate(self):
        self.enable()
        old = self.capture(now='2026-01-01T00:00:00Z')
        before = self.files()
        self.assertEqual([], conversations.prune(self.vault, now='2026-10-05T00:00:00Z')['paths'])
        self.assertEqual(before, self.files())
        conversations.configure(self.vault, retention_days=30)
        before = self.files()
        preview = conversations.prune(self.vault, now='2026-10-05T00:00:00Z')
        self.assertEqual([old['path']], preview['paths'])
        self.assertEqual(before, self.files())
        applied = conversations.prune(self.vault, apply=True, now='2026-10-05T00:00:00Z')
        self.assertEqual([old['path']], applied['paths'])
        self.assertFalse((self.vault / old['path']).exists())

    def test_retention_preserves_user_edited_unmanaged_and_recent_files(self):
        self.enable(retention_days=30)
        edited = self.capture(now='2026-01-01T00:00:00Z')
        path = self.vault / edited['path']
        path.write_bytes(path.read_bytes() + b'my edit')
        self.capture(session='recent', now='2026-10-04T00:00:00Z')
        (path.parent / 'manual.md').write_bytes(b'Manual content')
        before = self.files()
        self.assertEqual([], conversations.prune(self.vault, apply=True, now='2026-10-05T00:00:00Z')['paths'])
        self.assertEqual(before, self.files())

    def test_auto_prune_is_separate_opt_in_and_can_free_space_for_capture(self):
        self.enable(retention_days=30)
        old = self.capture(now='2026-01-01T00:00:00Z')
        used = conversations.status(self.vault)['used_bytes']
        conversations.configure(self.vault, max_bytes=used + 100)
        self.assertEqual('size_limit', self.capture(session='new', now='2026-10-05T00:00:00Z')['reason'])
        self.assertTrue((self.vault / old['path']).exists())
        conversations.configure(self.vault, auto_prune=True)
        result = self.capture(session='new', now='2026-10-05T00:00:00Z')
        self.assertEqual('saved', result['status'])
        self.assertEqual([old['path']], result['pruned'])
        self.assertFalse((self.vault / old['path']).exists())

    def test_config_rejects_unknown_and_invalid_fields_without_writes(self):
        for fields in [{'unknown': True}, {'enabled': 1}, {'max_bytes': True},
                       {'max_bytes': 0}, {'retention_days': -1}, {'retention_days': 1.5},
                       {'auto_prune': True}, {'include_tool_output': 'yes'}]:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):
                    conversations.configure(self.vault, **fields)
                self.assertEqual([], list(self.vault.iterdir()))

    def test_symlink_paths_and_unsafe_host_cannot_escape_the_vault(self):
        self.enable()
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        try:
            (self.vault / 'Inbox').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            self.capture()
        self.assertEqual([], list(outside.iterdir()))
        (self.vault / 'Inbox').unlink()
        with self.assertRaises(ValueError):
            conversations.capture(self.vault, '../escape', 'session', self.first)
        safe = self.capture(session='../../outside')
        self.assertEqual('Inbox/Conversations', Path(safe['path']).parent.as_posix())

    def test_symlink_config_and_archive_entries_are_rejected(self):
        outside = Path(self.tmp.name) / 'outside.json'
        outside.write_text('{}')
        (self.vault / '.brain-openkit').mkdir()
        try:
            (self.vault / '.brain-openkit/conversations.json').symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            conversations.status(self.vault)
        self.assertEqual('{}', outside.read_text())

    def test_competing_writer_is_rejected_without_lost_updates(self):
        self.enable()
        self.capture()
        before = self.files()
        with changes._journal_lock(self.vault):
            with self.assertRaisesRegex(ValueError, 'busy'):
                self.capture(self.second)
        self.assertEqual(before, self.files())
        self.assertEqual('saved', self.capture(self.second)['status'])

    def test_failure_before_atomic_replace_keeps_complete_old_snapshot(self):
        self.enable()
        self.capture()
        before = self.files()
        with patch.object(changes.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaisesRegex(OSError, 'disk error'):
                self.capture(self.second)
        self.assertEqual(before, self.files())

    def test_clock_rollback_cannot_make_an_updated_session_eligible_for_deletion(self):
        self.enable(retention_days=30)
        saved = self.capture(now='2026-10-05T00:00:00Z')
        self.capture(self.second, now='2026-01-01T00:00:00Z')
        result = conversations.prune(self.vault, now='2026-10-06T00:00:00Z')
        self.assertEqual([], result['paths'])
        self.assertTrue((self.vault / saved['path']).exists())

    def test_rendered_fences_cannot_bypass_the_session_limit_or_make_links(self):
        self.enable()
        self.capture()
        self.assertEqual([], notes.lint(self.vault)['broken_links'])
        before = self.files()
        result = self.capture(self.first + [{'role': 'assistant', 'text': '`' * (1024 * 1024)}])
        self.assertEqual('session_limit', result['reason'])
        self.assertEqual(before, self.files())

    def test_hidden_orphan_temp_files_are_included_in_quota(self):
        self.enable(max_bytes=4096)
        saved = self.capture()
        orphan = (self.vault / saved['path']).parent / '.brain-openkit-orphan.tmp'
        orphan.write_bytes(b'x' * 4096)
        before = self.files()
        self.assertEqual('size_limit', self.capture(self.second)['reason'])
        self.assertEqual(before, self.files())

    def test_hardlinked_empty_lock_does_not_modify_the_external_file(self):
        external = Path(self.tmp.name) / 'external-empty'
        external.write_bytes(b'')
        runtime = self.vault / '.brain-openkit'
        runtime.mkdir()
        try:
            os.link(external, runtime / 'lock')
        except OSError:
            self.skipTest('hardlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'hardlink'):
            self.enable()
        self.assertEqual(b'', external.read_bytes())
        self.assertFalse((runtime / 'conversations.json').exists())

    def test_preview_without_configuration_has_no_side_effects(self):
        self.assertEqual([], conversations.prune(self.vault)['paths'])
        self.assertEqual([], conversations.prune(self.vault, apply=True)['paths'])
        self.assertEqual([], list(self.vault.iterdir()))

    def test_conflicting_history_does_not_trigger_automatic_retention(self):
        self.enable(retention_days=30, auto_prune=True)
        old = self.capture(session='old', now='2026-01-01T00:00:00Z')
        self.capture(self.second, now='2026-01-01T00:00:00Z')
        before = self.files()
        result = self.capture(self.first, now='2026-10-05T00:00:00Z')
        self.assertEqual('history_conflict', result['reason'])
        self.assertEqual(before, self.files())
        self.assertTrue((self.vault / old['path']).exists())

    def test_unsafe_archive_does_not_partially_apply_configuration(self):
        self.enable()
        conversations.configure(self.vault, enabled=False)
        outside = Path(self.tmp.name) / 'outside-archive'
        outside.mkdir()
        try:
            (self.vault / 'Inbox').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        before = (self.vault / '.brain-openkit/conversations.json').read_bytes()
        with self.assertRaises(ValueError):
            self.enable()
        self.assertEqual(before, (self.vault / '.brain-openkit/conversations.json').read_bytes())

    def test_failed_quota_check_does_not_delete_expired_notes(self):
        self.enable(retention_days=30, auto_prune=True)
        self.capture(session='old', now='2026-01-01T00:00:00Z')
        conversations.configure(self.vault, max_bytes=1000)
        before = self.files()
        result = self.capture([{'role': 'user', 'text': 'x' * 2000}],
                              session='new', now='2026-10-05T00:00:00Z')
        self.assertEqual('size_limit', result['reason'])
        self.assertEqual(before, self.files())


if __name__ == '__main__':
    unittest.main()
