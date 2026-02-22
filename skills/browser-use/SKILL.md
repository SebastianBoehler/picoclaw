---
name: browser-use
description: Control a real Chromium browser to automate web tasks — navigate pages, click, fill forms, extract data, take screenshots, scrape content. Use when asked to browse the web interactively, fill out forms, log into sites, scrape structured data, monitor pages, or perform any task that requires a real browser (not just HTTP fetch). Triggers on: "open browser", "go to website", "click", "fill form", "scrape", "screenshot", "automate browser", "web automation", "browse to", "log in to site".
---

# Browser-Use

Automate real Chromium browser sessions via `/app/scripts/browser_use_tool.py` (baked into the agent image).
Use `exec` to run it directly — no sidecar needed.

**Full API reference**: See [references/api.md](references/api.md)
**Task examples**: See [references/examples.md](references/examples.md)

## Quick Start

```bash
python3 /app/scripts/browser_use_tool.py \
  --task "Go to https://example.com and extract the page title" \
  --output /home/picoclaw/.picoclaw/workspace/browser/result.json \
  --max-steps 20
```

Result JSON is printed to stdout AND written to `--output`.

## CLI Flags

| Flag                  | Default  | Description                                 |
| --------------------- | -------- | ------------------------------------------- |
| `--task`              | required | Natural language task for the browser agent |
| `--output`            | none     | Path to write JSON result file              |
| `--max-steps`         | 30       | Max browser actions before stopping         |
| `--headless`          | true     | Headless mode (always true in Docker)       |
| `--allowed-domains`   | all      | Comma-separated domain whitelist            |
| `--save-screenshot`   | none     | Path to save final screenshot PNG           |
| `--save-conversation` | none     | Path to save full conversation JSON         |

## Result Format

```json
{
  "success": true,
  "final_result": "Extracted text or completion message",
  "urls_visited": ["https://..."],
  "steps": 5,
  "duration_seconds": 12.4,
  "errors": [],
  "screenshot_path": null,
  "extracted_content": ["..."]
}
```

## Common Workflows

### Scrape data from a website

```bash
python3 /app/scripts/browser_use_tool.py \
  --task "Go to https://site.com/products and extract all product names and prices as a JSON list" \
  --output /home/picoclaw/.picoclaw/workspace/browser/products.json \
  --max-steps 15
```

### Fill a form

```bash
python3 /app/scripts/browser_use_tool.py \
  --task "Go to https://site.com/contact, fill Name='Test', Email='test@test.com', Message='Hello', click Submit, confirm success message" \
  --max-steps 10
```

### Take a screenshot

```bash
python3 /app/scripts/browser_use_tool.py \
  --task "Navigate to https://example.com" \
  --save-screenshot /home/picoclaw/.picoclaw/workspace/screenshots/example.png \
  --max-steps 3
```

### Domain-restricted research

```bash
python3 /app/scripts/browser_use_tool.py \
  --task "Search for Python async best practices and summarize the top 3 results" \
  --allowed-domains "docs.python.org,realpython.com" \
  --max-steps 20
```

## Rules

1. **Use `max_steps` conservatively** — 10-15 for simple tasks, 30 for complex flows
2. **Always write `--output`** to `workspace/browser/<slug>.json`
3. **Summarize findings** in `reply.md` — include `final_result` and `urls_visited`
4. **Screenshots** go to `workspace/screenshots/` — reference path in reply
5. **On failure** (`success: false`) — check `errors[]` and retry with a more specific task description
6. **Env var** `OPENROUTER_API_KEY` must be set — it is injected via the container environment

## Alternatives for Market Data

If `OPENROUTER_API_KEY` is unavailable or browser-use fails, use the **`web_search` skill** instead — it requires no extra API key and works for most market research tasks:

- **Price/market data**: Use `web_search` with queries like `"Bitcoin price site:coinmarketcap.com"` or `"DAX aktuell"` — faster and more reliable than browser automation
- **Company info**: `web_search` against `site:finance.yahoo.com` or `site:statista.com`
- **News/trends**: `web_search` with date-filtered queries
- **Structured scraping** (tables, forms, login-gated data): browser-use is required — no alternative

**Decision rule**: If the task is read-only data retrieval from a public page, try `web_search` first. Only use browser-use when interaction (clicks, forms, login) is needed.
