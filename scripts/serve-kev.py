#!/usr/bin/env python3
"""Start Brain OpenKit's default Kev checkpoint using the installed Kev runtime.

Run this script with the Python interpreter from the separate Kev environment.
The first start can download public Hugging Face weights. See docs/local-models.md.
"""

import argparse
import importlib.util
import os
import subprocess
import sys


DEFAULT_CHECKPOINT = "jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--run", default=DEFAULT_CHECKPOINT, help="HF checkpoint with revision, or local checkpoint path")
    parser.add_argument("--host", default="127.0.0.1", help="Server bind address")
    parser.add_argument("--port", type=int, default=8009, help="Server port")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not args.run.strip() or not args.host.strip():
        parser.error("run and host must not be blank")
    if importlib.util.find_spec("kev") is None:
        parser.error("Kev runtime is not installed in this Python environment; use the Kev environment's Python (docs/local-models.md)")
    # Upstream otherwise substitutes its smoke checkpoint for a missing local
    # path. Keep the requested checkpoint explicit even on that failure path.
    command = [sys.executable, "-m", "kev.serve", "--run", args.run,
               "--fallback", args.run, "--host", args.host, "--port", str(args.port)]
    if os.name == "nt":
        # Windows CRT exec does not retain the child status and can split
        # arguments with spaces. subprocess handles quoting and waits for exit.
        try:
            return subprocess.run(command).returncode
        except KeyboardInterrupt:
            return 130
    os.execv(sys.executable, command)


if __name__ == "__main__":
    raise SystemExit(main())
