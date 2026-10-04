import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from brain_openkit.vault import chunk_markdown, read_note, validate_vault


class ChunkMarkdownTests(unittest.TestCase):
    def test_citations_are_verbatim_crlf_slices_and_title_ignores_code(self):
        text = '---\r\ntitle: "회의 기록"\r\n---\r\n\r\n# 실제 제목\r\n첫 문단입니다.\r\n\r\n```md\r\n# 코드의 제목\r\n\r\n본문\r\n```\r\n\r\n## 결정\r\n기록을 남깁니다.\r\n'
        chunks = chunk_markdown(text, '회의/note.md', max_chars=75)
        self.assertGreater(len(chunks), 1)
        self.assertEqual('회의 기록', chunks[0].title)
        self.assertTrue(all(chunk.path == '회의/note.md' for chunk in chunks))
        source_lines = text.splitlines(keepends=True)
        for chunk in chunks:
            self.assertEqual(''.join(source_lines[chunk.start_line - 1:chunk.end_line]), chunk.text)
        self.assertEqual(text, ''.join(chunk.text for chunk in chunks))
        self.assertTrue(any('```md\r\n# 코드의 제목\r\n\r\n본문\r\n```' in c.text for c in chunks))

    def test_heading_boundary_keeps_concrete_line_numbers(self):
        chunks = chunk_markdown('# 첫째\nalpha\n\n## 둘째\nbeta\n', 'note.md')
        self.assertEqual([(1, 3, '# 첫째\nalpha\n\n'), (4, 5, '## 둘째\nbeta\n')],
                         [(c.start_line, c.end_line, c.text) for c in chunks])
        self.assertEqual(['첫째', '첫째'], [c.title for c in chunks])

    def test_unicode_separators_and_controls_are_not_markdown_line_breaks(self):
        for separator in ['\u2028', '\u2029', '\v', '\f', '\x85', '\x1c', '\x1d', '\x1e']:
            with self.subTest(separator=repr(separator)):
                text = f'alpha{separator}beta\n\n# Target\nneedle\n'
                chunks = chunk_markdown(text, 'note.md')
                self.assertEqual(
                    [(1, 2, f'alpha{separator}beta\n\n'), (3, 4, '# Target\nneedle\n')],
                    [(c.start_line, c.end_line, c.text) for c in chunks],
                )

    def test_lf_crlf_and_bare_cr_have_the_same_source_line_numbers(self):
        for newline in ['\n', '\r\n', '\r']:
            with self.subTest(newline=repr(newline)):
                chunks = chunk_markdown(f'alpha{newline}{newline}# Target{newline}needle', 'note.md')
                self.assertEqual(
                    [(1, 2, f'alpha{newline}{newline}'), (3, 4, f'# Target{newline}needle')],
                    [(c.start_line, c.end_line, c.text) for c in chunks],
                )

    def test_long_line_is_never_silently_truncated(self):
        text = '가' * 1500 + '\r\nshort\r\n'
        chunks = chunk_markdown(text, 'long.md', max_chars=40)
        self.assertEqual((1, 1, '가' * 1500 + '\r\n'),
                         (chunks[0].start_line, chunks[0].end_line, chunks[0].text))
        self.assertEqual(text, ''.join(c.text for c in chunks))

    def test_empty_content_and_invalid_budget(self):
        self.assertEqual([], chunk_markdown('', 'empty.md'))
        self.assertEqual([], chunk_markdown(' \n\r\n', 'empty.md'))
        with self.assertRaises(ValueError):
            chunk_markdown('text', 'note.md', max_chars=0)


class ReadNoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / 'vault'
        self.vault.mkdir()

    def test_utf8_source_bytes_unchanged(self):
        path = self.vault / '한글.md'
        source = '# 회의\r\n기록입니다.\r\n'.encode()
        path.write_bytes(source)
        chunks = read_note(self.vault, path)
        self.assertEqual('한글.md', chunks[0].path)
        self.assertEqual(source, ''.join(c.text for c in chunks).encode())
        self.assertEqual(source, path.read_bytes())

    def test_rejects_outside_and_symlink_notes(self):
        outside = Path(self.tmp.name) / 'outside.md'
        outside.write_text('private text', encoding='utf-8')
        with self.assertRaises(ValueError):
            read_note(self.vault, outside)
        alias = self.vault / 'alias.md'
        try:
            alias.symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            read_note(self.vault, alias)
        (self.vault / 'directory').symlink_to(outside.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            read_note(self.vault, self.vault / 'directory' / 'outside.md')

    def test_rejects_invalid_utf8_and_oversized_notes(self):
        path = self.vault / 'bad.md'
        path.write_bytes(b'bad\xff')
        with self.assertRaises(UnicodeDecodeError):
            read_note(self.vault, path)
        path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            read_note(self.vault, path)

    def test_rejects_missing_vault_before_reading(self):
        with self.assertRaises(ValueError):
            read_note(self.vault / 'missing', Path('note.md'))

    def test_direct_reads_do_not_bypass_metadata_exclusions(self):
        for relative in ['.obsidian/private.md', '.git/private.md', 'node_modules/private.md', 'secret.txt']:
            with self.subTest(relative=relative):
                path = self.vault / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('not a user note', encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_note(self.vault, path)

    def test_reparse_root_is_rejected_before_resolving_its_target(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch.object(Path, 'lstat', return_value=metadata):
            with self.assertRaises(ValueError):
                validate_vault(self.vault)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction behavior')
    def test_windows_junction_roots_and_note_ancestors_are_excluded(self):
        external = Path(self.tmp.name) / 'external'
        external.mkdir()
        (external / 'private.md').write_bytes(b'private\n')
        junction = self.vault / 'alias'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)],
                       check=True, capture_output=True)
        self.addCleanup(os.rmdir, junction)
        with self.assertRaises(ValueError):
            validate_vault(junction)
        with self.assertRaises(ValueError):
            read_note(self.vault, Path('alias/private.md'))


if __name__ == '__main__':
    unittest.main()
