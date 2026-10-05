import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


def entry(kind, content, uuid, **fields):
    return {"type": kind, "uuid": uuid,
            "message": {"role": kind, "content": content}, **fields}


class ConversationHookTests(unittest.TestCase):
    def setUp(self):
        try:
            self.hooks = importlib.import_module("brain_openkit.conversation_hooks")
        except ImportError:
            self.fail("The conversation hook adapter has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_claude_text_preserves_bytes_but_excludes_injected_and_private_blocks(self):
        records = [
            entry("user", "  질문\r\n", "u1"),
            entry("assistant", [{"type": "thinking", "thinking": "PRIVATE"},
                                {"type": "text", "text": " 답변\n"},
                                {"type": "tool_use", "input": {"secret": "PRIVATE"}}], "a1"),
            entry("user", "SKILL INJECTION", "u2", isMeta=True),
            entry("user", "COMPACTION", "u3", isCompactSummary=True),
            entry("assistant", "SUBAGENT", "a2", isSidechain=True),
            entry("user", "SYNTHETIC", "u4", isSynthetic=True),
            {"type": "system", "content": "SYSTEM"},
        ]
        self.assertEqual(self.hooks.parse_claude_transcript(records), [
            {"role": "user", "text": "  질문\r\n"},
            {"role": "assistant", "text": " 답변\n"},
        ])

    def test_duplicate_uuid_is_removed_but_identical_distinct_messages_remain(self):
        first = entry("assistant", [{"type": "text", "text": "same"}], "a1")
        second = entry("assistant", [{"type": "text", "text": "same"}], "a2")
        self.assertEqual(self.hooks.parse_claude_transcript([first, first, second]), [
            {"role": "assistant", "text": "same"},
            {"role": "assistant", "text": "same"},
        ])

    def test_tool_output_is_opt_in_and_does_not_include_thinking_or_tool_inputs(self):
        records = [entry("user", [{"type": "tool_result", "content": [
            {"type": "text", "text": "TOOL RESULT"},
            {"type": "image", "source": {"data": "BASE64"}},
        ]}], "tool1")]
        self.assertEqual(self.hooks.parse_claude_transcript(records), [])
        self.assertEqual(self.hooks.parse_claude_transcript(records, include_tool_output=True), [
            {"role": "tool", "text": "TOOL RESULT"},
        ])

    def test_complete_lines_survive_a_partial_tail_and_next_read_recovers_it(self):
        path = self.root / "transcript.jsonl"
        first = entry("user", "one", "u1")
        second = entry("assistant", [{"type": "text", "text": "two"}], "a1")
        prefix = json.dumps(first) + "\n"
        tail = json.dumps(second)
        path.write_text(prefix + tail[:20])
        self.assertEqual(self.hooks.read_jsonl(path, allow_partial=True), [first])
        with self.assertRaises(ValueError):
            self.hooks.read_jsonl(path)
        path.write_text(prefix + tail + "\n")
        self.assertEqual(self.hooks.read_jsonl(path), [first, second])

    def test_corrupt_complete_record_is_not_silently_dropped(self):
        path = self.root / "transcript.jsonl"
        path.write_text('{"type":broken}\n' + json.dumps(entry("user", "later", "u1")) + '\n')
        with self.assertRaises(ValueError):
            self.hooks.read_jsonl(path)

    def test_reader_rejects_oversized_transcript_before_processing(self):
        path = self.root / "large.jsonl"
        path.write_bytes(b" " * 101)
        with self.assertRaises(ValueError):
            self.hooks.read_jsonl(path, max_bytes=100)

    def configure(self, **changes):
        core = importlib.import_module("brain_openkit.conversations")
        core.configure(self.root, enabled=True, **changes)

    def transcript(self):
        path = self.root / "transcript.jsonl"
        path.write_text(json.dumps(entry("user", "original question", "u1")) + "\n")
        return path

    def script(self, payload, *, cwd=None, explicit_vault=True):
        script = Path(__file__).resolve().parents[1] / "scripts/conversation-hook.py"
        environment = dict(os.environ)
        environment.pop("BRAIN_OPENKIT_VAULT", None)
        if explicit_vault:
            environment["BRAIN_OPENKIT_VAULT"] = str(self.root)
        return subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                              text=True, capture_output=True, env=environment,
                              cwd=cwd or self.root, timeout=5)

    def test_disabled_capture_never_opens_or_even_coerces_transcript_path(self):
        self.assertTrue(callable(getattr(self.hooks, "capture_transcript", None)))
        class ForbiddenPath:
            def __fspath__(self):
                raise AssertionError("disabled adapter touched transcript")
        result = self.hooks.capture_transcript(self.root, "claude", "session", ForbiddenPath())
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stop_pending_then_session_end_saves_exactly_once_without_provisional_tail(self):
        self.assertTrue(callable(getattr(self.hooks, "capture_transcript", None)))
        self.configure()
        path = self.transcript()
        result = self.hooks.capture_transcript(self.root, "claude", "session", path,
                    last_assistant_message="final answer", retry_delays=())
        self.assertEqual(result["status"], "pending_transcript")
        self.assertFalse((self.root / "Inbox/Conversations").exists())
        with path.open("a") as output:
            output.write(json.dumps(entry("assistant", [{"type": "text", "text": "final answer"}], "a1")) + "\n")
        saved = self.hooks.capture_transcript(self.root, "claude", "session", path)
        self.assertEqual(saved["status"], "saved")
        archive = self.root / saved["path"]
        before = archive.read_bytes()
        replay = self.hooks.capture_transcript(self.root, "claude", "session", path,
                                             last_assistant_message="final answer")
        self.assertEqual(replay["status"], "unchanged")
        self.assertEqual(archive.read_bytes(), before)
        self.assertEqual(before.count(b"final answer"), 1)

    def test_hook_defaults_off_without_creating_files_and_exits_zero(self):
        result = self.script({"hook_event_name": "Stop", "session_id": "session",
                              "cwd": str(self.root), "transcript_path": "/does/not/exist"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_hook_does_not_discover_enabled_ancestor_configuration(self):
        self.assertTrue(callable(getattr(self.hooks, "capture_transcript", None)))
        self.configure()
        child = self.root / "unconfigured-child"
        child.mkdir()
        result = self.script({"hook_event_name": "Stop", "session_id": "session",
                              "cwd": str(child), "transcript_path": "/does/not/exist"},
                             cwd=child, explicit_vault=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(list(child.iterdir()), [])

    def test_hook_capacity_warning_is_pathless_and_does_not_continue_the_model(self):
        self.assertTrue(callable(getattr(self.hooks, "capture_transcript", None)))
        self.configure(max_bytes=1)
        path = self.transcript()
        result = self.script({"hook_event_name": "SessionEnd", "session_id": "session",
                              "cwd": str(self.root), "transcript_path": str(path)})
        self.assertEqual(result.returncode, 0)
        warning = json.loads(result.stdout)
        self.assertEqual(set(warning), {"systemMessage"})
        self.assertIn("limit", warning["systemMessage"])
        self.assertNotIn(str(self.root), result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertFalse(list((self.root / "Inbox/Conversations").glob("*.md")))

    def test_unrelated_hook_event_cannot_capture(self):
        self.assertTrue(callable(getattr(self.hooks, "capture_transcript", None)))
        self.configure()
        path = self.transcript()
        result = self.script({"hook_event_name": "UserPromptSubmit", "session_id": "session",
                              "cwd": str(self.root), "transcript_path": str(path)})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / "Inbox/Conversations").exists())

    def test_conflicting_duplicate_uuid_is_rejected_instead_of_hiding_changed_history(self):
        with self.assertRaises(ValueError):
            self.hooks.parse_claude_transcript([
                entry("user", "original", "u1"), entry("user", "changed", "u1")])

    def test_inline_tool_output_keeps_original_block_order(self):
        records = [entry("user", [{"type": "tool_result", "content": "tool"},
                                  {"type": "text", "text": "followup"}], "u1")]
        self.assertEqual(self.hooks.parse_claude_transcript(records, include_tool_output=True),
                         [{"role": "tool", "text": "tool"}, {"role": "user", "text": "followup"}])

    def test_adjacent_text_blocks_form_the_complete_last_assistant_message(self):
        self.assertEqual(self.hooks.parse_claude_transcript([
            entry("assistant", [{"type": "text", "text": "hello "},
                                {"type": "text", "text": "world"}], "a1")]),
                         [{"role": "assistant", "text": "hello world"}])

    def test_reader_rejects_symlink_hardlink_and_symlink_parent(self):
        source = self.transcript()
        aliases = [self.root / "symlink.jsonl", self.root / "hardlink.jsonl"]
        aliases[0].symlink_to(source)
        os.link(source, aliases[1])
        for alias in [source, *aliases]:
            with self.subTest(alias=alias.name), self.assertRaises(ValueError):
                self.hooks.read_jsonl(alias)
        aliases[1].unlink()
        directory_alias = self.root / "parent-link"
        directory_alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.hooks.read_jsonl(directory_alias / source.name)

    @unittest.skipUnless(sys.platform == "darwin", "macOS system directory aliases")
    def test_reader_accepts_macos_system_var_alias_without_following_custom_links(self):
        source = self.transcript()
        if not str(source).startswith("/private/var/"):
            self.skipTest("temporary directory is not below the macOS var alias")
        alias = Path(str(source).replace("/private/var/", "/var/", 1))
        self.assertEqual(self.hooks.read_jsonl(alias), [entry("user", "original question", "u1")])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO")
    def test_hook_rejects_fifo_without_waiting_for_a_writer(self):
        self.configure()
        fifo = self.root / "fifo.jsonl"
        os.mkfifo(fifo)
        try:
            result = self.script({"hook_event_name": "SessionEnd", "session_id": "session",
                                  "cwd": str(self.root), "transcript_path": str(fifo)})
        except subprocess.TimeoutExpired:
            self.fail("hook blocked while opening a non-regular transcript")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(set(json.loads(result.stdout)), {"systemMessage"})
        self.assertFalse((self.root / "Inbox/Conversations").exists())

    def test_capture_rejects_wrong_session_identity(self):
        self.configure()
        path = self.root / "transcript.jsonl"
        path.write_text(json.dumps(entry("user", "wrong session", "u1", sessionId="different")) + "\n")
        result = self.hooks.capture_transcript(self.root, "claude", "session", path)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse((self.root / "Inbox/Conversations").exists())

    def test_codex_session_end_without_turn_id_uses_transcript_host_and_identity(self):
        self.configure()
        path = self.root / "codex.jsonl"
        records = [
            {"type": "session_meta", "payload": {"id": "session", "session_id": "session"}},
            {"type": "event_msg", "payload": {"type": "item_completed", "thread_id": "session",
                "item": {"type": "UserMessage", "id": "u1", "content": [{"type": "text", "text": "codex question"}]}}},
        ]
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        result = self.hooks.handle_hook({"hook_event_name": "SessionEnd", "session_id": "session",
                                         "cwd": str(self.root), "transcript_path": str(path)}, environ={})
        self.assertEqual(result["status"], "saved")
        self.assertTrue(Path(result["path"]).name.startswith("codex-"))
        self.assertIn(b"codex question", (self.root / result["path"]).read_bytes())

    @unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/python3").exists(), "macOS legacy Python")
    def test_legacy_bootstrap_is_silent_when_off_and_can_use_explicit_python(self):
        script = Path(__file__).resolve().parents[1] / "scripts/conversation-hook.py"
        payload = {"hook_event_name": "Stop", "session_id": "session", "cwd": str(self.root),
                   "transcript_path": str(self.root / "missing.jsonl")}
        environment = dict(os.environ, BRAIN_OPENKIT_VAULT=str(self.root))
        environment.pop("BRAIN_OPENKIT_PYTHON", None)
        off = subprocess.run(["/usr/bin/python3", str(script)], input=json.dumps(payload),
                             capture_output=True, text=True, env=environment, timeout=5)
        self.assertEqual(off.returncode, 0)
        self.assertEqual(off.stdout, "")
        self.configure()
        payload["transcript_path"] = str(self.transcript())
        environment["BRAIN_OPENKIT_PYTHON"] = sys.executable
        on = subprocess.run(["/usr/bin/python3", str(script)], input=json.dumps(payload),
                            capture_output=True, text=True, env=environment, timeout=5)
        self.assertEqual(on.returncode, 0, on.stderr)
        self.assertEqual(on.stdout, "")
        self.assertEqual(len(list((self.root / "Inbox/Conversations").glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
