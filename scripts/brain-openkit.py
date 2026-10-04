#!/usr/bin/env python3
"""Run the bundled core from a checkout or plugin cache without installation."""

import sys
from pathlib import Path


if sys.version_info < (3, 11):
    print("Brain OpenKit requires Python 3.11 or newer.", file=sys.stderr)
    raise SystemExit(2)

# Plugin caches can be read-only. Keep generated files out of the product tree.
sys.dont_write_bytecode = True
source = Path(__file__).resolve().parents[1] / "src"
if not (source / "brain_openkit" / "cli.py").is_file():
    print("Brain OpenKit installation is incomplete: bundled core is missing.", file=sys.stderr)
    raise SystemExit(2)
sys.path.insert(0, str(source))

from brain_openkit.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
