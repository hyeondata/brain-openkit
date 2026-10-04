import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit import changes


class ChangeJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / 'vault'
        self.vault.mkdir()

    def plan(self, entries):
        return changes.make_plan(self.vault, entries, 'test')

    def apply(self, plan):
        return changes.apply_plan(self.vault, plan, plan['id'])

    def test_preview_apply_and_undo_preserve_exact_utf8_bytes(self):
        original = '# 원본\r\n본문\r\n'.encode()
        (self.vault / 'old.md').write_bytes(original)
        plan = self.plan([{'path': 'old.md', 'content': '# 수정\r\n새 내용\r\n'},
                          {'path': 'Notes/new.md', 'content': '# 새 노트\n내용\n'}])
        self.assertEqual(original, (self.vault / 'old.md').read_bytes())
        self.assertFalse((self.vault / '.brain-openkit').exists())
        self.assertIn('-본문', plan['changes'][0]['diff'])
        self.assertIn('+새 내용', plan['changes'][0]['diff'])
        self.assertEqual('# 원본\r\n본문\r\n', plan['changes'][0]['before'])
        result = self.apply(json.loads(json.dumps(plan)))
        self.assertEqual('applied', result['status'])
        self.assertEqual('# 수정\r\n새 내용\r\n'.encode(), (self.vault / 'old.md').read_bytes())
        self.assertEqual('# 새 노트\n내용\n'.encode(), (self.vault / 'Notes/new.md').read_bytes())
        undone = changes.undo(self.vault, result['transaction_id'])
        self.assertEqual('undone', undone['status'])
        self.assertEqual(original, (self.vault / 'old.md').read_bytes())
        self.assertFalse((self.vault / 'Notes/new.md').exists())

    def test_noop_plan_does_not_create_a_journal(self):
        (self.vault / 'note.md').write_bytes(b'same\r\n')
        for entries in [[], [{'path': 'note.md', 'content': 'same\r\n'}]]:
            plan = self.plan(entries)
            self.assertEqual([], plan['changes'])
            self.assertEqual({'transaction_id': None, 'status': 'unchanged', 'paths': []}, self.apply(plan))
        self.assertFalse((self.vault / '.brain-openkit').exists())

    def test_approval_and_plan_integrity_are_checked_before_mutation(self):
        plan = self.plan([{'path': 'note.md', 'content': 'reviewed\n'}])
        with self.assertRaises(ValueError):
            changes.apply_plan(self.vault, plan, '0' * 64)
        altered = copy.deepcopy(plan)
        altered['changes'][0]['content'] = 'unreviewed\n'
        with self.assertRaises(ValueError):
            self.apply(altered)
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        with self.assertRaises(ValueError):
            changes.apply_plan(other, plan, plan['id'])
        self.assertFalse((self.vault / 'note.md').exists())

    def test_all_files_preflight_before_any_file_changes(self):
        (self.vault / 'a.md').write_bytes(b'old a\n')
        (self.vault / 'b.md').write_bytes(b'old b\n')
        plan = self.plan([{'path': 'a.md', 'content': 'new a\n'}, {'path': 'b.md', 'content': 'new b\n'}])
        (self.vault / 'b.md').write_bytes(b'external edit\n')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.apply(plan)
        self.assertEqual(b'old a\n', (self.vault / 'a.md').read_bytes())
        self.assertEqual(b'external edit\n', (self.vault / 'b.md').read_bytes())

    def test_undo_preflights_new_and_changed_files_without_overwriting_edits(self):
        (self.vault / 'a.md').write_bytes(b'old\n')
        result = self.apply(self.plan([{'path': 'a.md', 'content': 'new\n'}, {'path': 'b.md', 'content': 'created\n'}]))
        (self.vault / 'b.md').write_bytes(b'external\n')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            changes.undo(self.vault, result['transaction_id'])
        self.assertEqual(b'new\n', (self.vault / 'a.md').read_bytes())
        self.assertEqual(b'external\n', (self.vault / 'b.md').read_bytes())

    def test_failed_second_replace_rolls_back_first_and_preserves_newlines(self):
        (self.vault / 'a.md').write_bytes(b'old a\r\n')
        (self.vault / 'b.md').write_bytes(b'old b\r\n')
        plan = self.plan([{'path': 'a.md', 'content': 'new a\n'}, {'path': 'b.md', 'content': 'new b\n'}])
        real_replace = os.replace

        def fail_second(source, destination, **kwargs):
            if Path(destination).name == 'b.md':
                raise OSError('simulated disk error')
            return real_replace(source, destination, **kwargs)

        with patch.object(changes.os, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, 'rolled back'):
                self.apply(plan)
        self.assertEqual(b'old a\r\n', (self.vault / 'a.md').read_bytes())
        self.assertEqual(b'old b\r\n', (self.vault / 'b.md').read_bytes())
        records = list((self.vault / '.brain-openkit/transactions').glob('*.json'))
        self.assertEqual(1, len(records))
        self.assertEqual('rolled_back', json.loads(records[0].read_text())['status'])

    def test_crashed_process_releases_lock_and_recovery_restores_snapshot(self):
        (self.vault / 'a.md').write_bytes(b'old a\r\n')
        (self.vault / 'b.md').write_bytes(b'old b\r\n')
        plan = self.plan([{'path': 'a.md', 'content': 'new a\n'}, {'path': 'b.md', 'content': 'new b\n'}])
        plan_file = Path(self.tmp.name) / 'plan.json'
        plan_file.write_text(json.dumps(plan), encoding='utf-8')
        script = '''import json, os, sys
from pathlib import Path
from brain_openkit import changes
real_replace = os.replace
def crash_after_replace(source, destination, **kwargs):
    real_replace(source, destination, **kwargs)
    if Path(destination).name == 'a.md':
        os._exit(73)
changes.os.replace = crash_after_replace
plan = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
changes.apply_plan(Path(sys.argv[1]), plan, plan["id"])
'''
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
        completed = subprocess.run([sys.executable, '-c', script, str(self.vault), str(plan_file)],
                                   env=environment, capture_output=True, timeout=20)
        self.assertEqual(73, completed.returncode, completed.stderr.decode(errors='replace'))
        self.assertEqual(b'new a\n', (self.vault / 'a.md').read_bytes())
        record_file = next((self.vault / '.brain-openkit/transactions').glob('*.json'))
        result = changes.recover(self.vault, record_file.stem)
        self.assertEqual('rolled_back', result['status'])
        self.assertEqual(b'old a\r\n', (self.vault / 'a.md').read_bytes())
        self.assertEqual(b'old b\r\n', (self.vault / 'b.md').read_bytes())
        self.assertEqual(result, changes.recover(self.vault, record_file.stem))

    def test_interrupted_undo_can_be_completed_without_losing_preimages(self):
        (self.vault / 'a.md').write_bytes(b'old a\n')
        result = self.apply(self.plan([{'path': 'a.md', 'content': 'new a\n'}, {'path': 'b.md', 'content': 'new b\n'}]))
        real_replace = os.replace

        def interrupt_after_restore(source, destination, **kwargs):
            real_replace(source, destination, **kwargs)
            if Path(destination).name == 'a.md':
                raise KeyboardInterrupt()

        with patch.object(changes.os, 'replace', side_effect=interrupt_after_restore):
            with self.assertRaises(KeyboardInterrupt):
                changes.undo(self.vault, result['transaction_id'])
        recovered = changes.recover(self.vault, result['transaction_id'])
        self.assertEqual('undone', recovered['status'])
        self.assertEqual(b'old a\n', (self.vault / 'a.md').read_bytes())
        self.assertFalse((self.vault / 'b.md').exists())

    def test_recovery_rejects_external_edits_after_interruption(self):
        (self.vault / 'a.md').write_bytes(b'old a\n')
        plan = self.plan([{'path': 'a.md', 'content': 'new a\n'}])
        real_replace = os.replace

        def interrupt(source, destination, **kwargs):
            real_replace(source, destination, **kwargs)
            if Path(destination).name == 'a.md':
                raise KeyboardInterrupt()

        with patch.object(changes.os, 'replace', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.apply(plan)
        transaction = next((self.vault / '.brain-openkit/transactions').glob('*.json')).stem
        (self.vault / 'a.md').write_bytes(b'external\n')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            changes.recover(self.vault, transaction)
        self.assertEqual(b'external\n', (self.vault / 'a.md').read_bytes())

    def test_unsafe_and_nonportable_paths_are_rejected(self):
        for path in ['../outside.md', '/absolute.md', 'x/../../n.md', '.obsidian/n.md',
                     '.brain-openkit/n.md', 'node_modules/n.md', '__pycache__/n.md',
                     'x.txt', 'a\\b.md', 'C:/n.md', 'a//n.md', './n.md',
                     'NUL.md', 'foo./n.md', 'x:stream.md', 'trailing .md ', 'n\x00.md']:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.plan([{'path': path, 'content': 'new'}])
        with self.assertRaises(ValueError):
            self.plan([{'path': 'A.md', 'content': 'one'}, {'path': 'a.md', 'content': 'two'}])

    def test_symlink_swapped_after_preview_cannot_escape_vault(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'note.md').write_bytes(b'private\n')
        plan = self.plan([{'path': 'Notes/note.md', 'content': 'replace\n'}])
        try:
            (self.vault / 'Notes').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual(b'private\n', (outside / 'note.md').read_bytes())

    def test_journal_symlink_is_rejected(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        plan = self.plan([{'path': 'note.md', 'content': 'new\n'}])
        try:
            (self.vault / '.brain-openkit').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual([], list(outside.iterdir()))

    def test_limits_and_invalid_utf8_fail_before_creating_notes(self):
        for entries in [[{'path': 'note.md', 'content': 'x' * (2 * 1024 * 1024 + 1)}],
                        [{'path': f'{i}.md', 'content': 'x'} for i in range(101)],
                        [{'path': 'note.md', 'content': '\ud800'}]]:
            with self.subTest(count=len(entries)):
                with self.assertRaises(ValueError):
                    self.plan(entries)
        (self.vault / 'bad.md').write_bytes(b'bad\xff')
        with self.assertRaises(ValueError):
            self.plan([{'path': 'bad.md', 'content': 'new'}])

    def test_exclusive_lock_prevents_interleaved_writers(self):
        plan = self.plan([{'path': 'note.md', 'content': 'new\n'}])
        with changes._journal_lock(self.vault):
            with self.assertRaisesRegex(ValueError, 'busy'):
                self.apply(plan)
        self.assertFalse((self.vault / 'note.md').exists())
        self.assertEqual('applied', self.apply(plan)['status'])

    def test_recovery_never_treats_successful_apply_as_interrupted(self):
        result = self.apply(self.plan([{'path': 'note.md', 'content': 'new\n'}]))
        with self.assertRaisesRegex(ValueError, 'undo'):
            changes.recover(self.vault, result['transaction_id'])
        self.assertEqual(b'new\n', (self.vault / 'note.md').read_bytes())

    def test_invalid_transaction_identifiers_do_not_read_outside_journal(self):
        for identifier in ['../secret', '/tmp/secret', 'x.json', '', '0' * 33]:
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):
                    changes.undo(self.vault, identifier)

    def test_snapshot_is_durable_before_first_note_replace(self):
        (self.vault / 'a.md').write_bytes(b'original\r\n')
        plan = self.plan([{'path': 'a.md', 'content': 'new\n'}])
        real_replace = os.replace

        def inspect_snapshot(source, destination, **kwargs):
            if Path(destination).name == 'a.md':
                record = json.loads(next((self.vault / '.brain-openkit/transactions').glob('*.json')).read_bytes())
                self.assertEqual('prepared', record['status'])
                self.assertEqual('original\r\n', record['plan']['changes'][0]['before'])
                self.assertEqual(b'original\r\n', (self.vault / 'a.md').read_bytes())
            return real_replace(source, destination, **kwargs)

        with patch.object(changes.os, 'replace', side_effect=inspect_snapshot):
            self.apply(plan)
        self.assertEqual(b'new\n', (self.vault / 'a.md').read_bytes())

    def test_unfinished_transaction_blocks_a_new_write_until_recovery(self):
        plan = self.plan([{'path': 'a.md', 'content': 'new\n'}])
        real_replace = os.replace

        def interrupt(source, destination, **kwargs):
            real_replace(source, destination, **kwargs)
            if Path(destination).name == 'a.md':
                raise KeyboardInterrupt()

        with patch.object(changes.os, 'replace', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.apply(plan)
        pending = next((self.vault / '.brain-openkit/transactions').glob('*.json')).stem
        next_plan = self.plan([{'path': 'b.md', 'content': 'next\n'}])
        with self.assertRaisesRegex(ValueError, pending):
            self.apply(next_plan)
        self.assertFalse((self.vault / 'b.md').exists())
        changes.recover(self.vault, pending)
        self.assertEqual('applied', self.apply(next_plan)['status'])

    def test_tampered_journal_cannot_replace_notes_during_undo(self):
        (self.vault / 'a.md').write_bytes(b'old\n')
        result = self.apply(self.plan([{'path': 'a.md', 'content': 'new\n'}]))
        record_file = self.vault / '.brain-openkit/transactions' / (result['transaction_id'] + '.json')
        record = json.loads(record_file.read_bytes())
        record['plan']['changes'][0]['before'] = 'unreviewed\n'
        record_file.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed after preview'):
            changes.undo(self.vault, result['transaction_id'])
        self.assertEqual(b'new\n', (self.vault / 'a.md').read_bytes())

    def test_case_variant_of_protected_directory_is_rejected(self):
        for path in ['NODE_MODULES/private.md', '__PYCACHE__/private.md']:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.plan([{'path': path, 'content': 'new\n'}])

    def test_existing_case_alias_is_rejected_on_every_platform(self):
        (self.vault / 'Index.md').write_bytes(b'original\n')
        with self.assertRaises(ValueError):
            self.plan([{'path': 'index.md', 'content': 'new\n'}])
        self.assertEqual(b'original\n', (self.vault / 'Index.md').read_bytes())

    def test_combined_image_size_is_bounded(self):
        with self.assertRaisesRegex(ValueError, '16 MiB'):
            self.plan([{'path': f'{i}.md', 'content': 'x' * (2 * 1024 * 1024)} for i in range(9)])

    def test_malformed_journal_status_fails_as_validation_without_note_changes(self):
        result = self.apply(self.plan([{'path': 'a.md', 'content': 'new\n'}]))
        record_file = self.vault / '.brain-openkit/transactions' / (result['transaction_id'] + '.json')
        record = json.loads(record_file.read_bytes())
        record['status'] = []
        record_file.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'invalid transaction journal'):
            changes.undo(self.vault, result['transaction_id'])
        self.assertEqual(b'new\n', (self.vault / 'a.md').read_bytes())

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_windows_junction_vault_root_is_rejected_before_resolution(self):
        junction = Path(self.tmp.name) / 'junction'
        completed = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(self.vault)],
                                   capture_output=True, timeout=10)
        if completed.returncode:
            self.skipTest('junction creation unavailable')
        self.addCleanup(junction.rmdir)
        with self.assertRaisesRegex(ValueError, 'reparse'):
            changes.make_plan(junction, [{'path': 'a.md', 'content': 'new\n'}], 'unsafe root')
        self.assertFalse((self.vault / 'a.md').exists())


if __name__ == '__main__':
    unittest.main()
