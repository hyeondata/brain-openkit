#!/usr/bin/env python3
"""Run the local opt-in conversation hook from a plugin or source installation."""

import json
import os
from pathlib import Path
import stat
import sys


sys.dont_write_bytecode = True


def enabled_for_bootstrap_warning():
    """Old interpreters may inspect opt-in, but must stay silent when disabled."""
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return False
        payload = json.loads(raw)
        if payload.get("hook_event_name") not in ("Stop", "SessionEnd"):
            return False
        selected = os.environ.get("BRAIN_OPENKIT_VAULT") or payload.get("cwd")
        config = Path(selected) / ".brain-openkit/conversations.json"
        for component in (config, *config.parents):
            metadata = component.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
                return False
        metadata = config.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > 16384:
            return False
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(config, flags), "rb") as stream:
            if not os.path.samestat(metadata, os.fstat(stream.fileno())):
                return False
            return json.loads(stream.read(16385)).get("enabled") is True
    except Exception:
        return False


requested = os.environ.get("BRAIN_OPENKIT_PYTHON")
if requested and Path(requested).resolve() != Path(sys.executable).resolve():
    try:
        if not Path(requested).is_absolute():
            raise ValueError("absolute interpreter required")
        environment = dict(os.environ)
        environment.pop("BRAIN_OPENKIT_PYTHON", None)
        os.execve(requested, [requested, str(Path(__file__).resolve())], environment)
    except (OSError, ValueError):
        if enabled_for_bootstrap_warning():
            print(json.dumps({"systemMessage": "Brain OpenKit conversation auto-save cannot start the configured Python interpreter."}))
        raise SystemExit(0)

if sys.version_info < (3, 11):
    if enabled_for_bootstrap_warning():
        print(json.dumps({"systemMessage": "Brain OpenKit conversation auto-save requires Python 3.11 or newer; set BRAIN_OPENKIT_PYTHON to its absolute executable path."}))
    raise SystemExit(0)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from brain_openkit.conversation_hooks import main
except ImportError:
    print(json.dumps({"systemMessage": "Brain OpenKit conversation auto-save installation is incomplete."}))
    raise SystemExit(0)


if __name__ == "__main__":
    raise SystemExit(main())
