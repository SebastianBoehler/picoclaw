#!/usr/bin/env python3
"""
use_browser.py — Picoclaw browser automation helper.

Thin wrapper around /app/scripts/browser_use_tool.py.
Runs a natural-language browser task using browser-use + Playwright Chromium
(baked into the agent image — no sidecar needed).

Usage (from agent exec):
    python3 /home/picoclaw/use_browser.py \
        --task "Go to https://example.com and extract the main heading" \
        --output /home/picoclaw/.picoclaw/workspace/tasks/<task_id>/browser_result.json \
        [--max-steps 20] \
        [--allowed-domains "example.com,google.com"] \
        [--save-screenshot /path/to/screenshot.png]

Output (stdout + optional --output file):
    JSON with keys:
      success          bool
      final_result     str   — agent's final answer / extracted content
      urls_visited     list  — all URLs the browser visited
      steps            int   — number of browser actions taken
      duration_seconds float
      errors           list  — any errors encountered
      screenshot_path  str   — path to screenshot if --save-screenshot used

Exit codes:
    0  — task completed successfully
    1  — task failed or browser error

Required env vars (set automatically in agent containers):
    OPENROUTER_API_KEY   — LLM for browser-use agent
    BROWSER_USE_MODEL    — model to use (default: x-ai/grok-4-fast)
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH — set in Dockerfile.agent
"""

import os
import sys
import subprocess

TOOL = "/app/scripts/browser_use_tool.py"


def main():
    # Pass all args straight through to browser_use_tool.py
    cmd = [sys.executable, TOOL] + sys.argv[1:]
    result = subprocess.run(cmd, env=os.environ.copy())
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
