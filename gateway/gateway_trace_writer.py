#!/usr/bin/env python3
"""
gateway_trace_writer.py

Legacy entrypoint kept for compatibility with docker-compose service commands.
It no longer parses logs or writes traces from Python.

Tracing is emitted directly by the Go runtime into PostgreSQL.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/picoclaw")
try:
    from gh_auth import init_gh_token
except Exception:
    init_gh_token = None  # type: ignore


def main() -> None:
    if init_gh_token is not None:
        try:
            init_gh_token(start_refresh_thread=True)
        except Exception as exc:
            print(f"[gateway] GH token init failed: {exc}", file=sys.stderr, flush=True)

    picoclaw_bin = os.environ.get("PICOCLAW_BIN", "picoclaw")
    os.execvp(picoclaw_bin, [picoclaw_bin, "gateway"] + sys.argv[1:])


if __name__ == "__main__":
    main()
