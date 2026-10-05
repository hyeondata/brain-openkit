"""Exercise a relocated plugin as a source distribution without site packages."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "brain-init", "brain-search", "brain-organize", "brain-ingest",
    "brain-save", "brain-lint", "brain-fold", "brain-research",
}


class PackagingTests(unittest.TestCase):
    def test_hosts_reference_existing_shared_skills(self):
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(claude["name"], "brain-openkit")
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual((ROOT / codex["skills"]).resolve(), ROOT / "skills")
        discovered = set()
        for path in (ROOT / "skills").glob("*/SKILL.md"):
            frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
            fields = dict(line.split(":", 1) for line in frontmatter.strip().splitlines())
            self.assertEqual(fields["name"].strip(), path.parent.name)
            self.assertTrue(fields["description"].strip())
            discovered.add(path.parent.name)
        self.assertEqual(discovered, SKILLS)

    def test_marketplaces_package_the_complete_local_product(self):
        claude = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        codex = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(claude["plugins"][0]["source"], "./")
        self.assertEqual(codex["plugins"][0]["source"], {"source": "local", "path": "./"})
        for catalog in (claude, codex):
            self.assertEqual(catalog["plugins"][0]["name"], "brain-openkit")

    def test_relocated_runner_works_without_installation_and_preserves_notes(self):
        with tempfile.TemporaryDirectory(prefix="brain plugin ") as directory:
            temporary = Path(directory)
            product = temporary / "plugin cache with spaces"
            product.mkdir()
            for name in ("src", "scripts", "skills", ".claude-plugin", ".codex-plugin"):
                shutil.copytree(ROOT / name, product / name, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
            vault = temporary / "user vault 한글"
            vault.mkdir()
            note = vault / "기록.md"
            original = "# 검색 기록\r\n\r\n로컬 검색은 원문 위치를 보존합니다.\r\n".encode()
            note.write_bytes(original)
            runner = product / "scripts/brain-openkit.py"
            args = [sys.executable, "-I", "-S", str(runner)]
            version = subprocess.run(args + ["--version"], capture_output=True, text=True, encoding="utf-8", cwd=vault)
            self.assertEqual(version.returncode, 0, version.stderr)
            manifest = json.loads((product / ".claude-plugin/plugin.json").read_text())
            self.assertIn(manifest["version"], version.stdout)
            result = subprocess.run(args + ["search", "로컬 검색", "--vault", str(vault), "--cache-dir", str(temporary / "cache"), "--json"], capture_output=True, text=True, encoding="utf-8", cwd=vault)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["results"][0]["path"], "기록.md")
            self.assertEqual(note.read_bytes(), original)
            self.assertFalse(any(product.rglob("__pycache__")))
            self.assertEqual({p.name for p in vault.iterdir()}, {"기록.md"})

    def test_shared_runtime_reference_resolves_from_every_skill(self):
        for name in SKILLS:
            skill = ROOT / "skills" / name / "SKILL.md"
            reference = skill.parent / "../references/runtime.md"
            self.assertTrue(reference.is_file(), str(reference))
            self.assertTrue((skill.resolve().parents[2] / "scripts/brain-openkit.py").is_file())

    def test_incomplete_cache_reports_missing_core_without_importing_other_install(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Path(directory) / "scripts/brain-openkit.py"
            runner.parent.mkdir()
            shutil.copyfile(ROOT / "scripts/brain-openkit.py", runner)
            result = subprocess.run([sys.executable, "-I", "-S", str(runner), "--version"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
            self.assertIn("bundled core is missing", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
