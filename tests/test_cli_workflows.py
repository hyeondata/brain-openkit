import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brain_openkit.cli import main


class WorkflowCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            status = main([*args, '--vault', str(self.vault), '--json'])
        return status, json.loads(output.getvalue())

    def apply(self, path, plan):
        status, result = self.run_cli('apply', str(path), '--approve', plan['id'])
        self.assertEqual(status, 0, result)
        return result

    def test_preview_apply_ingest_search_save_and_undo(self):
        plan_path = self.root / 'init.json'
        status, plan = self.run_cli('init', '--plan', str(plan_path))
        self.assertEqual(status, 0, plan)
        self.assertFalse((self.vault / 'Index.md').exists())
        self.apply(plan_path, plan)
        source = self.root / 'source.txt'
        source.write_bytes('한국어 검색과 원문 보존.\r\n'.encode())
        plan_path = self.root / 'ingest.json'
        status, plan = self.run_cli('ingest', str(source), '--title', '검색 기록', '--plan', str(plan_path))
        self.assertEqual(status, 0, plan)
        self.apply(plan_path, plan)
        self.assertEqual(next((self.vault / 'Sources').glob('*.md')).read_bytes(), source.read_bytes())
        status, report = self.run_cli('search', '검색', '--cache-dir', str(self.root / 'cache'))
        self.assertEqual(status, 0, report)
        self.assertTrue(report['results'])
        draft = self.root / 'draft.md'
        draft.write_bytes('# 결정\r\n\r\n원문을 유지한다.\r\n'.encode())
        plan_path = self.root / 'save.json'
        status, plan = self.run_cli('save', str(draft), '--path', 'Notes/decision.md', '--plan', str(plan_path))
        self.assertEqual(status, 0, plan)
        applied = self.apply(plan_path, plan)
        self.assertTrue((self.vault / 'Notes/decision.md').is_file())
        status, result = self.run_cli('undo', applied['transaction_id'])
        self.assertEqual(status, 0, result)
        self.assertFalse((self.vault / 'Notes/decision.md').exists())

    def test_plan_files_must_be_external_and_not_overwrite_existing(self):
        for path in (self.vault / 'plan.json', self.root / 'existing.json'):
            if path.name == 'existing.json':
                path.write_bytes(b'original')
            status, result = self.run_cli('init', '--plan', str(path))
            self.assertEqual(status, 2, result)
            if path.name == 'existing.json':
                self.assertEqual(path.read_bytes(), b'original')
        self.assertFalse((self.vault / 'Index.md').exists())

    def test_wrong_approval_refuses_to_write(self):
        path = self.root / 'plan.json'
        status, plan = self.run_cli('init', '--plan', str(path))
        self.assertEqual(status, 0, plan)
        status, result = self.run_cli('apply', str(path), '--approve', 'wrong')
        self.assertEqual(status, 2, result)
        self.assertFalse((self.vault / 'Index.md').exists())

    def test_jev_selection_without_key_fails_locally(self):
        with patch.dict(os.environ, {}, clear=True):
            status, result = self.run_cli('doctor', '--provider', 'jev')
        self.assertEqual(status, 2)
        self.assertIn('missing_api_key', result['error']['message'])

    def test_provider_specific_configuration_and_environment_key_priority(self):
        config = self.root / 'providers.json'
        config.write_text(json.dumps({'provider': 'jev', 'jev_model': 'jev-test',
                                      'jev_base_url': 'https://jev.example',
                                      'laya_base_url': 'http://127.0.0.1:18999'}))
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'primary', 'JEV_API_KEY': 'alias'}, clear=True):
            with patch('brain_openkit.jev.JevProvider') as provider:
                provider.return_value.name = 'jev'
                provider.return_value.health.return_value = {'status': 'ok', 'models': []}
                status, report = self.run_cli('doctor', '--config', str(config))
                self.assertEqual(status, 0, report)
                self.assertEqual(report['provider'], 'jev')
                self.assertFalse(report['inference_verified'])
                self.assertEqual(provider.call_args.kwargs['api_key'], 'primary')
                self.assertEqual(provider.call_args.kwargs['base_url'], 'https://jev.example')
                self.assertEqual(provider.call_args.kwargs['model'], 'jev-test')
                provider.return_value.choose.assert_not_called()
            with patch('brain_openkit.cli.LayaProvider') as provider:
                provider.return_value.name = 'laya'
                provider.return_value.health.return_value = {'status': 'ok'}
                status, report = self.run_cli('doctor', '--config', str(config), '--provider', 'laya')
                self.assertEqual(status, 0, report)
                self.assertEqual(provider.call_args.kwargs['base_url'], 'http://127.0.0.1:18999')


if __name__ == '__main__':
    unittest.main()
