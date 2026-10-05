"""Run the launcher against a tiny module fixture, without model downloads."""

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


LAUNCHER = Path(__file__).resolve().parents[1] / "scripts/serve-kev.py"


class KevLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        package = self.root / "kev"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "serve.py").write_text(
            "import json, os, sys\n"
            "print(json.dumps(sys.argv[1:]))\n"
            "sys.exit(int(os.environ.get('FIXTURE_EXIT', '0')))\n", encoding="utf-8")
        self.env = {**os.environ, "PYTHONPATH": str(self.root)}

    def run_launcher(self, *args, isolated=False):
        return subprocess.run([sys.executable, *(["-I", "-S"] if isolated else []),
                               str(LAUNCHER), *args], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_default_launch_selects_pinned_08_weights_and_loopback_endpoint(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(result.stdout)
        self.assertEqual(args, [
            "--run", "jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f",
            "--fallback", "jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f",
            "--host", "127.0.0.1", "--port", "8009",
        ])

    def test_checkpoint_override_is_one_argument_and_cannot_fall_back_to_another_model(self):
        checkpoint = "local weights/legacy checkpoint"
        result = self.run_launcher("--run", checkpoint, "--host", "::1", "--port", "18009")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["--run", checkpoint, "--fallback", checkpoint,
                                                   "--host", "::1", "--port", "18009"])

    def test_help_works_without_installing_the_optional_runtime(self):
        result = self.run_launcher("--help", isolated=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--run", result.stdout)

    def test_missing_runtime_explains_how_to_run_from_the_kev_environment(self):
        result = self.run_launcher(isolated=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Kev runtime", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_port_does_not_launch_the_server(self):
        for port in ("0", "65536", "invalid"):
            with self.subTest(port=port):
                result = self.run_launcher("--port", port)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")

    def test_server_failure_remains_a_nonzero_exit(self):
        self.env["FIXTURE_EXIT"] = "7"
        result = self.run_launcher()
        self.assertEqual(result.returncode, 7, result.stderr)

    def test_windows_waits_for_the_server_and_propagates_its_failure(self):
        (self.root / "kev/serve.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
        launch = runpy.run_path(str(LAUNCHER))["main"]
        with patch("os.name", "nt"), patch("sys.argv", [str(LAUNCHER)]), \
                patch("sys.path", [str(self.root), *sys.path]), patch.dict(os.environ, self.env), \
                patch("os.execv", side_effect=AssertionError("Windows CRT exec cannot propagate exit status")):
            self.assertEqual(launch(), 7)


if __name__ == "__main__":
    unittest.main()
