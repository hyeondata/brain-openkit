import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from brain_openkit.cli import main


class ConversationCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / 'Vault with spaces'
        self.vault.mkdir()

    def run_cli(self, action, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['conversations', action, '--vault', str(self.vault), '--json', *args])
        self.assertEqual(err.getvalue(), '')
        return code, json.loads(out.getvalue())

    def test_disabled_capture_never_reads_missing_transcript_or_creates_files(self):
        code, result = self.run_cli('capture', '--host', 'claude', '--session-id', 'example',
                                    '--transcript', str(self.root / 'missing.jsonl'))
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'disabled')
        self.assertEqual(list(self.vault.iterdir()), [])

    def test_enable_capture_search_and_disable(self):
        code, result = self.run_cli('configure', '--enable')
        self.assertEqual(code, 0, result)
        transcript = self.root / 'synthetic.jsonl'
        rows = [
            {'type': 'user', 'uuid': 'u1', 'message': {'role': 'user', 'content': '청록나침반 결정을 기억해'}},
            {'type': 'assistant', 'uuid': 'a1', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': '다음 실험은 금요일입니다.'}]}},
        ]
        transcript.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        code, result = self.run_cli('capture', '--host', 'claude', '--session-id', 'synthetic-cli', '--transcript', str(transcript))
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'saved')
        files = list((self.vault / 'Inbox' / 'Conversations').glob('*.md'))
        self.assertEqual(len(files), 1)
        self.assertIn('청록나침반', files[0].read_text(encoding='utf-8'))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['search', '청록나침반', '--vault', str(self.vault), '--cache-dir', str(self.root / 'cache'), '--json'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out.getvalue())['results'])
        before = files[0].read_bytes()
        self.assertEqual(self.run_cli('configure', '--disable')[0], 0)
        self.assertEqual(self.run_cli('capture', '--host', 'claude', '--session-id', 'synthetic-cli', '--transcript', str(transcript))[1]['status'], 'disabled')
        self.assertEqual(files[0].read_bytes(), before)

    def test_retention_requires_separate_auto_prune_opt_in(self):
        self.assertEqual(self.run_cli('configure', '--enable', '--retention-days', '30')[0], 0)
        settings = json.loads((self.vault / '.brain-openkit' / 'conversations.json').read_text())
        self.assertFalse(settings['auto_prune'])
        self.assertEqual(settings['retention_days'], 30)
        self.assertEqual(self.run_cli('prune')[0], 0)

    def test_enabled_capture_reports_pending_as_nonzero_without_an_archive(self):
        self.assertEqual(self.run_cli('configure', '--enable')[0], 0)
        code, result = self.run_cli('capture', '--host', 'claude', '--session-id', 'not-ready',
                                    '--transcript', str(self.root / 'missing.jsonl'))
        self.assertEqual(code, 3, result)
        self.assertEqual(result['status'], 'pending_transcript')
        self.assertFalse((self.vault / 'Inbox').exists())

    def test_bad_options_are_structured_errors(self):
        for args in [('--max-bytes', '-1'), ('--retention-days', '-2'), ('--auto-prune',), ('--enable', '--disable')]:
            with self.subTest(args=args):
                code, result = self.run_cli('configure', *args)
                self.assertEqual(code, 2)
                self.assertIn('error', result)


if __name__ == '__main__':
    unittest.main()
