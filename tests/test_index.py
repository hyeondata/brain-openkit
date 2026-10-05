import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from brain_openkit.index import Index


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.cache = self.root / 'cache'
        self.index = Index(self.vault, self.cache)
        self.addCleanup(self.index.close)

    def note(self, name, text):
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_korean_substring_and_normalized_words(self):
        self.note('회의.md', '# 업무 기록\n프로젝트회의에서 ＡＰＩ를 논의했습니다.\n')
        self.note('garden.md', '# Garden\nFlowers and rain.\n')
        self.index.update()
        self.assertEqual(['회의.md'], [h.chunk.path for h in self.index.search('회의')])
        self.assertEqual(['회의.md'], [h.chunk.path for h in self.index.search('API')])
        self.assertEqual([], self.index.search('unfindablexyz'))
        self.assertEqual([], self.index.search('   '))

    def test_metadata_search_and_deterministic_positive_results(self):
        self.note('topics/quasar.md', '# Observation\nDistant light.\n')
        self.note('b.md', '# Twin\nsharedword\n')
        self.note('a.md', '# Twin\nsharedword\n')
        self.index.update()
        self.assertEqual('topics/quasar.md', self.index.search('quasar')[0].chunk.path)
        self.assertEqual('topics/quasar.md', self.index.search('Observation')[0].chunk.path)
        hits = self.index.search('sharedword')
        self.assertEqual(['a.md', 'b.md'], [h.chunk.path for h in hits])
        self.assertTrue(all(h.bm25_score > 0 for h in hits))

    def test_content_hash_detects_same_size_same_mtime_changes_and_deletion(self):
        path = self.note('note.md', 'alpha\n')
        before = path.stat()
        self.assertEqual(1, self.index.update()['indexed'])
        self.assertEqual(1, self.index.update()['unchanged'])
        path.write_text('omega\n', encoding='utf-8')
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(1, self.index.update()['indexed'])
        self.assertEqual([], self.index.search('alpha'))
        self.assertEqual('note.md', self.index.search('omega')[0].chunk.path)
        path.unlink()
        self.assertEqual(1, self.index.update()['deleted'])
        self.assertEqual([], self.index.search('omega'))

    def test_invalid_utf8_and_oversized_replacements_remove_stale_evidence(self):
        path = self.note('note.md', 'evidence\n')
        self.index.update()
        path.write_bytes(b'\xff')
        report = self.index.update()
        self.assertEqual(1, len(report['errors']))
        self.assertEqual([], self.index.search('evidence'))
        path.write_text('restored', encoding='utf-8')
        self.index.update()
        path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
        self.assertEqual(1, len(self.index.update()['errors']))
        self.assertEqual([], self.index.search('restored'))

    def test_excludes_hidden_paths_symlinks_and_configured_cache_directory(self):
        self.note('.obsidian/settings.md', 'secretword')
        self.note('.git/objects.md', 'secretword')
        self.note('.cache/note.md', 'secretword')
        self.note('node_modules/package.md', 'secretword')
        good = self.note('visible.md', 'publicword')
        try:
            (self.vault / 'alias.md').symlink_to(good)
            (self.vault / 'shortcut').symlink_to(self.root, target_is_directory=True)
        except OSError:
            pass
        own_cache = self.vault / 'runtime'
        own_cache.mkdir()
        (own_cache / 'cached.md').write_text('secretword', encoding='utf-8')
        index = Index(self.vault, own_cache)
        self.addCleanup(index.close)
        report = index.update()
        self.assertEqual(1, report['indexed'])
        self.assertEqual([], index.search('secretword'))
        self.assertEqual(['visible.md'], [h.chunk.path for h in index.search('publicword')])

    def test_shared_cache_keeps_vaults_independent_and_survives_reopen(self):
        self.note('same.md', 'firstword')
        second_vault = self.root / 'second'
        second_vault.mkdir()
        (second_vault / 'same.md').write_text('secondword', encoding='utf-8')
        second = Index(second_vault, self.cache)
        self.addCleanup(second.close)
        self.index.update()
        second.update()
        self.assertEqual([], self.index.search('secondword'))
        self.assertEqual([], second.search('firstword'))
        self.index.close()
        reopened = Index(self.vault, self.cache)
        self.addCleanup(reopened.close)
        self.assertEqual('same.md', reopened.search('firstword')[0].chunk.path)
        self.assertEqual(1, reopened.update()['unchanged'])

    def test_invalid_schema_rebuilds_instead_of_serving_stale_cache(self):
        self.note('note.md', 'originalword')
        self.index.update()
        self.index.close()
        database = next(self.cache.glob('*.sqlite3'))
        conn = sqlite3.connect(database)
        try:
            conn.execute('PRAGMA user_version = 999')
        finally:
            conn.close()
        reopened = Index(self.vault, self.cache)
        self.addCleanup(reopened.close)
        self.assertEqual([], reopened.search('originalword'))
        self.assertEqual(1, reopened.update()['indexed'])
        self.assertEqual('note.md', reopened.search('originalword')[0].chunk.path)

    def test_old_line_number_cache_is_rebuilt_before_serving_citations(self):
        (self.vault / 'note.md').write_bytes('alpha\u2028beta\n\n# Target\nneedle\n'.encode('utf-8'))
        self.index.update()
        self.index.close()
        conn = sqlite3.connect(next(self.cache.glob('*.sqlite3')))
        try:
            conn.execute('PRAGMA user_version = 1')
        finally:
            conn.close()
        reopened = Index(self.vault, self.cache)
        self.addCleanup(reopened.close)
        self.assertEqual([], reopened.search('needle'))
        self.assertEqual(1, reopened.update()['indexed'])
        hit = reopened.search('needle')[0]
        self.assertEqual((3, 4, '# Target\nneedle\n'),
                         (hit.chunk.start_line, hit.chunk.end_line, hit.chunk.text))

    def test_rejects_invalid_vault_and_query_limits(self):
        with self.assertRaises(ValueError):
            Index(self.root / 'missing', self.cache)
        file_path = self.root / 'file'
        file_path.write_text('text')
        with self.assertRaises(ValueError):
            Index(file_path, self.cache)
        with self.assertRaises(ValueError):
            self.index.search('x', limit=0)
        with self.assertRaises(ValueError):
            self.index.search('x' * 8001)

    def test_unreadable_note_is_reported_and_removed_from_cache(self):
        path = self.note('note.md', 'evidence')
        self.index.update()
        try:
            path.chmod(0)
            if os.access(path, os.R_OK):
                self.skipTest('process can still read mode-000 files')
            report = self.index.update()
            self.assertEqual('note.md', report['errors'][0]['path'])
            self.assertEqual(1, report['deleted'])
            self.assertEqual([], self.index.search('evidence'))
        finally:
            path.chmod(0o600)

    def test_cache_owned_by_another_vault_fails_before_serving_results(self):
        self.note('note.md', 'privateword')
        self.index.update()
        self.index.close()
        conn = sqlite3.connect(next(self.cache.glob('*.sqlite3')))
        try:
            conn.execute("UPDATE ownership SET vault = ?", (str(self.root / 'other'),))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(ValueError, 'another vault'):
            Index(self.vault, self.cache)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_windows_junction_is_not_walked_or_used_as_cache(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'private.md').write_text('outside-secret', encoding='utf-8')
        junction = self.vault / 'linked'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            report = self.index.update()
            self.assertEqual(report['indexed'], 0)
            self.assertEqual(self.index.search('outside-secret'), [])
            with self.assertRaises(ValueError):
                Index(self.vault, junction)
        finally:
            junction.rmdir()


if __name__ == '__main__':
    unittest.main()
