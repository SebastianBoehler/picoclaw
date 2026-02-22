---
name: firmenregister-research
description: Deep research on German companies using Handelsregister, Northdata, Bundesanzeiger, and web search. Use when asked to look up a specific German company's registration data, financials, directors, or annual reports. For building lead lists, prefer the lead-research skill.
---

# Firmenregister Research & Lead Generation

**Full API reference**: See [references/api.md](references/api.md)

All tools at `http://host.docker.internal:8000`. Use `http_fetch` (NOT `http_request`).

## Available Tools

| Tool            | Endpoint                       | Use for                         |
| --------------- | ------------------------------ | ------------------------------- |
| Web search      | `POST /search`                 | Broad discovery, contacts, news |
| Handelsregister | `POST /handelsregister/search` | Official company registry       |
| Lead pipeline   | `POST /leads-discover`         | Automated batch discovery       |
| Northdata KPIs  | `POST /northdata/kpis`         | Financials, management          |
| Bundesanzeiger  | `POST /bundesanzeiger/search`  | Annual reports                  |

## Workflows

### Quick company lookup

1. `POST /handelsregister/search` → official name, register number, court
2. `POST /search` → website, contact, LinkedIn, news
3. `POST /northdata/kpis` → financials (skip gracefully if no API key)
4. Save to `workspace/research/MM_DD_YYYY/<company-slug>.md`

### Lead generation campaign

1. `POST /leads-discover` with category + location + ICP → get `batch_id`
2. Poll `GET /leads-discover/{batch_id}` every 30s until `status: "completed"`
3. For top leads: verify with `/handelsregister/search`, enrich with `/northdata/kpis`
4. Save list to `workspace/leads/MM_DD_YYYY/<category>-<location>.md`
