---
name: lead-research
description: Research company leads using web search, Handelsregister, Northdata, and Bundesanzeiger. Use when asked to find companies, research prospects, build lead lists, or look up German company registration/financial data.
---

# Lead Research

All tools at `http://host.docker.internal:8000`. Use `http_fetch` (NOT `http_request`).

**Full API reference**: See [references/api.md](references/api.md)
**Output formats**: See [references/output-format.md](references/output-format.md)

## Available Tools

| Tool            | Endpoint                       | Use for                             |
| --------------- | ------------------------------ | ----------------------------------- |
| Web search      | `POST /search`                 | Broad discovery, contacts, news     |
| Lead pipeline   | `POST /leads-discover`         | Automated batch discovery + scoring |
| Handelsregister | `POST /handelsregister/search` | Official German company registry    |
| Northdata KPIs  | `POST /northdata/kpis`         | Financials, management, WZ codes    |
| Bundesanzeiger  | `POST /bundesanzeiger/search`  | Annual reports                      |

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
4. Save list to `workspace/leads/MM_DD_YYYY/<category>-<location>.md` + CSV
5. Summarize top 3 in `reply.md`
