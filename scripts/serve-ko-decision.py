#!/usr/bin/env python3
"""Run the optional Korean decision server from a source checkout."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain_openkit.ko_decision_server import main


if __name__ == "__main__":
    raise SystemExit(main())
