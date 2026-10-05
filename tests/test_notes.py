import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from brain_openkit.changes import apply_plan, undo
from brain_openkit.notes import (
    lint, plan_fold, plan_ingest, plan_init, plan_organize, plan_save,
)
from brain_openkit.workflows import search


class NoteWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()

    def write(self, path, content):
        target = self.vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode('utf-8'))
        return target

    def apply(self, plan):
        return apply_plan(self.vault, plan, plan['id'])

    def test_adopt_preserves_existing_index_and_links_existing_notes(self):
        before = '# My index\r\nPersonal introduction.\r\n'
        self.write('Index.md', before)
        self.write('Projects/회의.md', '# 회의\n결정\n')
        plan = plan_init(self.vault)
        self.assertEqual(before.encode(), (self.vault / 'Index.md').read_bytes())
        self.apply(plan)
        index = (self.vault / 'Index.md').read_bytes().decode()
        self.assertTrue(index.startswith(before))
        self.assertIn('[[Projects/회의]]', index)
        self.assertNotIn('\n', index.replace('\r\n', ''))
        self.assertEqual([], plan_init(self.vault)['changes'])

    def test_ingest_captures_exact_bytes_and_duplicate_keeps_later_edits(self):
        source = self.root / 'source.txt'
        raw = '# 원본\r\n검색은 로컬에서 수행합니다.\r\n'
        source.write_bytes(raw.encode())
        plan = plan_ingest(self.vault, source, '로컬 검색', source_url='https://example.org/source')
        self.assertEqual([], list(self.vault.iterdir()))
        self.apply(plan)
        captures = list((self.vault / 'Sources').glob('*.md'))
        self.assertEqual(1, len(captures))
        self.assertEqual(raw.encode(), captures[0].read_bytes())
        note = self.vault / 'Notes/로컬-검색.md'
        generated = note.read_bytes().decode()
        self.assertIn(hashlib.sha256(raw.encode()).hexdigest(), generated)
        self.assertIn(json.dumps(str(source), ensure_ascii=False), generated)
        self.assertIn('https://example.org/source', generated)
        self.assertIn(f'[[Sources/{captures[0].stem}]]', generated)
        self.assertIn('검색은 로컬에서 수행합니다.', generated)
        note.write_bytes((generated + '\nMy later edit.\n').encode())
        self.assertEqual([], plan_ingest(self.vault, source, '로컬 검색', source_url='https://example.org/source')['changes'])
        self.assertTrue(note.read_bytes().endswith(b'My later edit.\n'))

    def test_ingest_rejects_title_collision_and_changed_immutable_capture(self):
        source = self.root / 'source.txt'
        source.write_bytes(b'original\n')
        self.apply(plan_ingest(self.vault, source, 'Subject'))
        capture = next((self.vault / 'Sources').glob('*.md'))
        capture.write_bytes(b'external edit\n')
        with self.assertRaises(ValueError):
            plan_ingest(self.vault, source, 'Subject')
        source.write_bytes(b'new source\n')
        with self.assertRaises(ValueError):
            plan_ingest(self.vault, source, 'Subject')

    def test_host_draft_is_saved_with_provenance_and_safe_source_fence(self):
        source = self.root / 'source.txt'
        source.write_bytes(b'```\n[[Missing]]\n```\n')
        self.apply(plan_ingest(self.vault, source, 'Draft', draft='# Selected insight\nHost prose.\n'))
        note = (self.vault / 'Notes/Draft.md').read_bytes().decode()
        self.assertIn('# Selected insight\nHost prose.\n', note)
        self.assertIn('[[Sources/', note)
        self.assertNotIn('[[Missing]]', note)

    def test_organize_preserves_unknown_metadata_crlf_and_is_idempotent(self):
        before = ('---\r\ntitle: "회의"\r\ncustom:\r\n  nested: keep\r\n'
                  'tags:\r\n  - existing\r\n---\r\n# 회의\r\n원문.\r\n')
        self.write('meeting.md', before)
        self.write('Projects/Target.md', '# Target\n')
        plan = plan_organize(self.vault, 'meeting.md', category='Research', tags=['new', 'existing'], links=['Projects/Target.md'])
        self.apply(plan)
        after = (self.vault / 'meeting.md').read_bytes().decode()
        self.assertIn('custom:\r\n  nested: keep\r\n', after)
        self.assertIn('category: "Research"\r\n', after)
        self.assertIn('tags: ["existing", "new"]\r\n', after)
        self.assertIn('# 회의\r\n원문.\r\n', after)
        self.assertIn('[[Projects/Target]]', after)
        self.assertNotIn('\n', after.replace('\r\n', ''))
        self.assertEqual([], plan_organize(self.vault, 'meeting.md', category='Research', tags=['new'], links=['Projects/Target'])['changes'])

    def test_organize_rejects_ambiguous_metadata_and_unresolved_links(self):
        for frontmatter in ['---\ntags: one\ntags: two\n---\n', '---\ntags: {nested: value}\n---\n', '---\ncategory: old\n']:
            with self.subTest(frontmatter=frontmatter):
                self.write('note.md', frontmatter + 'Body\n')
                with self.assertRaises(ValueError):
                    plan_organize(self.vault, 'note.md', tags=['new'])
        self.write('note.md', 'Body\n')
        self.write('a/Same.md', 'A\n')
        self.write('b/Same.md', 'B\n')
        for target in ['Missing', 'Same', '../outside', '.obsidian/private']:
            with self.subTest(target=target), self.assertRaises(ValueError):
                plan_organize(self.vault, 'note.md', links=[target])

    def test_save_and_fold_link_sources_and_preserve_children(self):
        first = '# First\r\nOne source fact.\r\n'
        second = '# Second\nAnother source fact.\n'
        self.write('First.md', first)
        self.write('Second.md', second)
        self.apply(plan_save(self.vault, 'Notes/Selected.md', '# Selected\nA selected insight.\n', sources=['First']))
        self.assertIn('[[First]]', (self.vault / 'Notes/Selected.md').read_text())
        self.apply(plan_fold(self.vault, ['First.md', 'Second.md'], 'Notes/Overview.md', 'Overview'))
        overview = (self.vault / 'Notes/Overview.md').read_bytes().decode()
        self.assertIn('[[First]]', overview)
        self.assertIn('[[Second]]', overview)
        self.assertIn('lines 1–2', overview)
        self.assertIn('One source fact.', overview)
        self.assertEqual(first.encode(), (self.vault / 'First.md').read_bytes())
        self.assertEqual(second.encode(), (self.vault / 'Second.md').read_bytes())
        with self.assertRaises(ValueError):
            plan_fold(self.vault, ['First.md'], 'First.md', 'Overwrite child')

    def test_fold_is_additive_to_existing_destination_and_repeat_is_noop(self):
        self.write('First.md', '# First\nSource fact.\n')
        self.write('Overview.md', '# Existing overview\nMy analysis.\n')
        self.apply(plan_fold(self.vault, ['First.md'], 'Overview.md', 'Overview'))
        text = (self.vault / 'Overview.md').read_bytes().decode()
        self.assertTrue(text.startswith('# Existing overview\nMy analysis.\n'))
        self.assertIn('Source fact.', text)
        self.assertEqual([], plan_fold(self.vault, ['First.md'], 'Overview.md', 'Overview')['changes'])

    def test_notes_with_dots_and_ambiguous_short_links_get_canonical_index_links(self):
        self.write('Index.md', '# Index\n[[Same]]\n')
        self.write('a/Same.md', 'First\n')
        self.write('b/Same.md', 'Second\n')
        self.write('v1.2.md', 'Version\n')
        self.apply(plan_init(self.vault))
        text = (self.vault / 'Index.md').read_bytes().decode()
        self.assertIn('[[a/Same]]', text)
        self.assertIn('[[b/Same]]', text)
        self.assertNotIn('v1.2', [entry['target'] for entry in lint(self.vault)['broken_links']])

    def test_frontmatter_updates_preserve_comments(self):
        self.write('note.md', '---\ntags:\n  - existing\n# Keep my explanation.\n\ncustom: retained\n---\nBody\n')
        self.apply(plan_organize(self.vault, 'note.md', tags=['new']))
        self.assertIn('# Keep my explanation.\n\ncustom: retained\n', (self.vault / 'note.md').read_bytes().decode())

    def test_quoted_keys_and_nested_tag_sequences_cannot_be_silently_rewritten(self):
        for content in ['---\n"tags": [old]\n---\nBody\n',
                        "---\n'category': old\n---\nBody\n",
                        '---\ntags:\n  - old\n    - nested\n---\nBody\n']:
            with self.subTest(content=content):
                self.write('note.md', content)
                with self.assertRaises(ValueError):
                    plan_organize(self.vault, 'note.md', category='new', tags=['new'])
                self.assertEqual(content.encode(), (self.vault / 'note.md').read_bytes())

    def test_frontmatter_updates_preserve_inline_comments(self):
        self.write('note.md', '---\ntags: # overall explanation\n  - old # keep tag explanation\ncategory: "C#" # keep category explanation\n---\nBody\n')
        self.apply(plan_organize(self.vault, 'note.md', category='Research', tags=['new']))
        text = (self.vault / 'note.md').read_bytes().decode()
        for comment in ['# overall explanation', '# keep tag explanation', '# keep category explanation']:
            self.assertIn(comment, text)
        self.assertEqual([], plan_organize(self.vault, 'note.md', category='Research', tags=['new'])['changes'])

    def test_lowercase_index_is_adopted_without_replacement_or_second_index(self):
        self.write('index.md', '# My existing index\nPersonal content.\n')
        self.write('note.md', 'Content\n')
        self.apply(plan_init(self.vault))
        self.assertEqual(['index.md', 'note.md'], sorted(path.name for path in self.vault.glob('*.md')))
        text = (self.vault / 'index.md').read_bytes().decode()
        self.assertTrue(text.startswith('# My existing index\nPersonal content.\n'))
        self.assertIn('[[note]]', text)

    def test_symbolic_links_are_excluded_from_lint_and_cannot_be_references(self):
        self.write('note.md', '[[alias]]\n')
        external = self.root / 'external.md'
        external.write_bytes(b'private\n')
        try:
            (self.vault / 'alias.md').symlink_to(external)
            (self.vault / 'external-dir').symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        report = lint(self.vault)
        self.assertEqual(1, report['notes'])
        self.assertEqual(['alias'], [entry['target'] for entry in report['broken_links']])
        with self.assertRaises(ValueError):
            plan_organize(self.vault, 'note.md', links=['alias'])
        with self.assertRaises(ValueError):
            plan_ingest(self.vault, self.vault / 'alias.md', 'Captured')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction behavior')
    def test_windows_junction_is_excluded_from_lint_index_and_fold(self):
        self.write('note.md', 'Local content\n')
        external = self.root / 'external'
        external.mkdir()
        (external / 'private.md').write_bytes(b'private\n')
        junction = self.vault / 'alias'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)],
                       check=True, capture_output=True)
        self.addCleanup(os.rmdir, junction)
        self.assertEqual(1, lint(self.vault)['notes'])
        self.apply(plan_init(self.vault))
        self.assertNotIn('private', (self.vault / 'Index.md').read_bytes().decode())
        with self.assertRaises(ValueError):
            plan_fold(self.vault, ['alias/private.md'], 'Overview.md', 'Overview')

    def test_unrepresentable_wikilink_names_fail_before_producing_broken_index(self):
        for name in ['bad#heading.md', 'bad[bracket].md']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                plan_save(self.vault, name, 'Content\n')

    def test_empty_and_repeated_tags_do_not_modify_existing_note(self):
        self.write('note.md', '---\ntags: [one, two]\n---\nBody\n')
        self.assertEqual([], plan_organize(self.vault, 'note.md', tags=[])['changes'])
        self.assertEqual([], plan_organize(self.vault, 'note.md', tags=['two'])['changes'])

    def test_root_symlink_and_invalid_source_url_are_rejected(self):
        source = self.root / 'source.txt'
        source.write_bytes(b'source\n')
        for url in ['file:///etc/passwd', 'https://user:secret@example.com/', 'https://example.com/\nInjected']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                plan_ingest(self.vault, source, 'Bad URL', source_url=url)
        try:
            (self.root / 'alias').symlink_to(self.vault, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            plan_init(self.root / 'alias')

    def test_inaccessible_directories_are_reported_and_block_incomplete_plans(self):
        hidden = self.write('Private/note.md', 'Private note\n').parent
        hidden.chmod(0)
        self.addCleanup(hidden.chmod, 0o700)
        if os.access(hidden, os.R_OK | os.X_OK):
            self.skipTest('directory permissions are not enforced for this user/platform')
        report = lint(self.vault)
        self.assertEqual(['Private'], [entry['path'] for entry in report['metadata_errors']])
        with self.assertRaises(ValueError):
            plan_init(self.vault)
        with self.assertRaises(ValueError):
            plan_save(self.vault, 'New.md', 'New note\n')

    def test_unstatable_entries_are_reported_without_aborting_lint(self):
        hidden = self.write('Private/note.md', 'Private note\n').parent
        hidden.chmod(0o400)
        self.addCleanup(hidden.chmod, 0o700)
        if os.access(hidden, os.X_OK):
            self.skipTest('directory permissions are not enforced for this user/platform')
        report = lint(self.vault)
        self.assertTrue(report['metadata_errors'])
        self.assertEqual(0, report['notes'])
        with self.assertRaises(ValueError):
            plan_init(self.vault)

    def test_lint_reports_links_orphans_and_metadata_without_reading_excluded(self):
        self.write('Index.md', '[[Good]]\n[[Same]]\n[[Missing|alias]]\n')
        self.write('Good.md', '---\ntags: ["valid"]\n---\n# Good\n[[Index#Header]]\n`[[Ignored]]`\n```md\n[[Ignored too]]\n```\n')
        self.write('a/Same.md', 'A\n')
        self.write('b/Same.md', 'B\n')
        self.write('Bad.md', '---\ntags: one\ntags: two\n---\n')
        self.write('.obsidian/private.md', '[[Secret]]\n')
        self.write('node_modules/dependency.md', '[[Dependency]]\n')
        report = lint(self.vault)
        self.assertEqual([('Index.md', 'Missing')], [(v['path'], v['target']) for v in report['broken_links']])
        self.assertEqual(['Same'], [v['target'] for v in report['ambiguous_links']])
        self.assertEqual(['Bad.md', 'a/Same.md', 'b/Same.md'], report['orphans'])
        self.assertEqual(['Bad.md'], [v['path'] for v in report['metadata_errors']])
        self.assertEqual(5, report['notes'])

    def test_literal_html_comment_in_code_does_not_hide_real_broken_links(self):
        self.write('note.md', '# HTML syntax\n\n```html\n<!--\n```\n\nActual link: [[Missing]]\n')
        self.assertEqual([{'path': 'note.md', 'target': 'Missing', 'line': 7}], lint(self.vault)['broken_links'])
        self.write('note.md', '`<!--`\n[[Missing]]\n<!-- [[Ignored]] -->\n')
        self.assertEqual([{'path': 'note.md', 'target': 'Missing', 'line': 2}], lint(self.vault)['broken_links'])

    def test_workflow_loop_search_and_undo_restores_preimage(self):
        self.apply(plan_init(self.vault))
        source = self.root / 'reading.md'
        source.write_bytes('# Local\n서울 로컬 검색 실험 기록.\n'.encode())
        self.apply(plan_ingest(self.vault, source, 'Local search'))
        result = search(self.vault, '서울 검색', cache_dir=self.root / 'cache')
        self.assertTrue(result['results'])
        before = (self.vault / 'Notes/Local-search.md').read_bytes()
        transaction = self.apply(plan_organize(self.vault, 'Notes/Local-search.md', category='Research', tags=['검색']))
        self.assertEqual([], lint(self.vault)['broken_links'])
        undo(self.vault, transaction['transaction_id'])
        self.assertEqual(before, (self.vault / 'Notes/Local-search.md').read_bytes())

    def test_source_and_destination_validation_rejects_invalid_or_unsafe_data(self):
        source = self.root / 'source.txt'
        source.write_bytes(b'bad\xff')
        with self.assertRaises(UnicodeDecodeError):
            plan_ingest(self.vault, source, 'Bad')
        source.write_bytes(b'safe\n')
        for title in ['', 'bad\nheading']:
            with self.subTest(title=title), self.assertRaises(ValueError):
                plan_ingest(self.vault, source, title)
        for path in ['../escape.md', '.obsidian/private.md', 'Sources/overwrite.md']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                plan_save(self.vault, path, 'changed\n')


if __name__ == '__main__':
    unittest.main()
