#!/usr/bin/env python3
"""
browser_use_tool.py — Picoclaw browser automation CLI

Runs a browser-use Agent to complete a natural language browser task.
Outputs a JSON result to stdout and optionally to a file.

Usage:
    python browser_use_tool.py --task "Go to https://example.com and extract the title" \
        --output /workspace/result.json \
        --max-steps 20
"""

import argparse
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path


def _build_llm():
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("BROWSER_USE_MODEL", "x-ai/grok-4-fast")
    if not openrouter_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")
    from browser_use.llm import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.0,
    )


async def run_browser_task(
    task: str,
    max_steps: int = 30,
    headless: bool = True,
    allowed_domains: list[str] | None = None,
    save_screenshot: str | None = None,
    save_conversation: str | None = None,
) -> dict:
    from browser_use import Agent
    from browser_use.browser import BrowserProfile

    chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None
    profile_kwargs: dict = dict(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    )
    if chromium_path:
        profile_kwargs["executable_path"] = chromium_path
    if allowed_domains:
        profile_kwargs["allowed_domains"] = allowed_domains

    browser_profile = BrowserProfile(**profile_kwargs)
    llm = _build_llm()

    agent_kwargs: dict = dict(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
        max_steps=max_steps,
        use_vision="auto",
        max_failures=3,
        calculate_cost=False,
    )
    if save_conversation:
        agent_kwargs["save_conversation_path"] = save_conversation

    agent = Agent(**agent_kwargs)
    history = await agent.run()

    screenshot_path = None
    if save_screenshot:
        import base64
        screenshots = history.screenshots()
        if screenshots:
            out = Path(save_screenshot)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(screenshots[-1]))
            screenshot_path = str(out)

    errors = [str(e) for e in (history.errors() or []) if e is not None]

    return {
        "success": history.is_done() and not history.has_errors(),
        "final_result": history.final_result() or "",
        "urls_visited": history.urls() or [],
        "steps": history.number_of_steps(),
        "duration_seconds": round(history.total_duration_seconds(), 2),
        "errors": errors,
        "screenshot_path": screenshot_path,
        "extracted_content": history.extracted_content() or [],
    }


def main():
    parser = argparse.ArgumentParser(description="Picoclaw browser automation via browser-use")
    parser.add_argument("--task", required=True, help="Natural language task for the browser agent")
    parser.add_argument("--output", default=None, help="Path to write JSON result file")
    parser.add_argument("--max-steps", type=int, default=30, help="Max browser actions (default: 30)")
    parser.add_argument("--headless", type=lambda x: x.lower() != "false", default=True,
                        help="Run headless (default: true)")
    parser.add_argument("--allowed-domains", default=None,
                        help="Comma-separated domain whitelist (e.g. 'github.com,google.com')")
    parser.add_argument("--save-screenshot", default=None, help="Path to save final screenshot PNG")
    parser.add_argument("--save-conversation", default=None, help="Path to save full conversation JSON")

    args = parser.parse_args()

    allowed_domains = None
    if args.allowed_domains:
        allowed_domains = [d.strip() for d in args.allowed_domains.split(",") if d.strip()]

    try:
        result = asyncio.run(run_browser_task(
            task=args.task,
            max_steps=args.max_steps,
            headless=args.headless,
            allowed_domains=allowed_domains,
            save_screenshot=args.save_screenshot,
            save_conversation=args.save_conversation,
        ))
    except Exception as e:
        result = {
            "success": False,
            "final_result": "",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    print(output_json)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
