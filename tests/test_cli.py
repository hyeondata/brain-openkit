import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from brain_openkit.cli import main


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        (self.vault / "note.md").write_text("# 검색\n\n한국어 로컬 검색과 인덱스.\n", encoding="utf-8")

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(list(args))
        return status, out.getvalue(), err.getvalue()

    def common(self):
        return ["--vault", str(self.vault), "--cache-dir", str(self.root / "cache"), "--json"]

    def test_index_search_and_empty_results_are_machine_readable(self):
        before = (self.vault / "note.md").read_bytes()
        status, out, err = self.run_cli("index", *self.common())
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["indexed"], 1)
        status, out, err = self.run_cli("search", "로컬", *self.common())
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out)["results"][0]["path"], "note.md")
        status, out, _ = self.run_cli("search", "absentxyz", *self.common())
        self.assertEqual(json.loads(out)["results"], [])
        self.assertEqual((self.vault / "note.md").read_bytes(), before)

    def test_invalid_vault_is_nonzero_structured_error(self):
        status, out, _ = self.run_cli("index", "--vault", str(self.root / "missing"), "--json")
        self.assertNotEqual(status, 0)
        self.assertIn("error", json.loads(out))

    def test_config_relative_paths_are_resolved_from_config_location(self):
        config = self.root / "settings.json"
        config.write_text(json.dumps({"vault": "vault", "cache_dir": "cache", "provider": "none"}))
        status, out, err = self.run_cli("search", "로컬", "--config", str(config), "--json")
        self.assertEqual(status, 0, err or out)
        self.assertEqual(json.loads(out)["results"][0]["path"], "note.md")

    def test_config_keys_cannot_store_credentials(self):
        config = self.root / "settings.json"
        config.write_text('{"api_key":"private-test-key"}')
        status, out, err = self.run_cli("search", "x", "--config", str(config), "--json")
        self.assertNotEqual(status, 0)
        self.assertNotIn("private-test-key", out + err)

    def test_classify_requires_a_decision_provider(self):
        taxonomy = self.root / "taxonomy.json"
        taxonomy.write_text('{"categories":{"research":"Research"}}')
        status, out, _ = self.run_cli("classify", "note.md", "--taxonomy", str(taxonomy),
                                     "--provider", "none", *self.common())
        self.assertNotEqual(status, 0)
        self.assertIn("error", json.loads(out))

    def test_json_configuration_types_are_validated(self):
        config = self.root / "settings.json"
        for payload in [{"vault": 4}, {"timeout": False}, {"timeout": 10**1000}, {"limit": 1.5}, {"max_tokens": "bad"}, {"provider": "jev"}]:
            config.write_text(json.dumps(payload))
            status, out, _ = self.run_cli("search", "x", "--config", str(config), "--json")
            self.assertNotEqual(status, 0)
            self.assertIn("error", json.loads(out))

    def test_argument_errors_obey_json_output_mode(self):
        cases = [
            ["search", "needle", "--limit", "no", "--json"],
            ["classify", "note.md", "--json"],
            ["search", "needle", "--unknown", "--json"],
            ["missing-command", "--json"],
        ]
        for args in cases:
            with self.subTest(args=args):
                status, out, err = self.run_cli(*args)
                self.assertEqual(status, 2)
                self.assertIn("error", json.loads(out))
                self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
