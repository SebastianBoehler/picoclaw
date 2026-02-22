# Lead Research — API Reference

Base URL: `http://host.docker.internal:8000`
Tool: `http_fetch` (NOT `http_request`)

---

## Web Search

```
http_fetch url="http://host.docker.internal:8000/search" method="POST" body="{\"query\": \"YOUR QUERY\", \"max_results\": 10}"
```

Response: `{ "ok": true, "result": "..." }` — LLM text grounded in live web results.

Use for: finding companies by category, contact details, LinkedIn profiles, news, recent events.

---

## Lead Discovery Pipeline

### Start a batch
```
http_fetch url="http://host.docker.internal:8000/leads-discover" method="POST" body="{
  \"category\": \"Immobilienverwaltung\",
  \"location\": \"München\",
  \"limit\": 20,
  \"icp\": \"Property management companies 10-200 employees looking to modernize\",
  \"use_llm_scoring\": true,
  \"handelsregister_enrich\": true
}"
```

Response: `{ "ok": true, "batch_id": "20240219-142300", "status": "started" }`

### Poll for results (every 30s)
```
http_fetch url="http://host.docker.internal:8000/leads-discover/{batch_id}" method="GET"
```

When `status: "completed"`, returns list of leads with:
- `name`, `address`, `website`, `emails[]`, `phones[]`
- `score` (0-100), `icp_fit_notes`
- `hr_register_number`, `hr_court` (if `handelsregister_enrich: true`)

### List recent batches
```
http_fetch url="http://host.docker.internal:8000/leads-discover?limit=10" method="GET"
```

---

## Handelsregister Search

```
http_fetch url="http://host.docker.internal:8000/handelsregister/search" method="POST" body="{
  \"name\": \"Muster Immobilien GmbH\",
  \"city\": \"München\",
  \"keyword_mode\": \"all\"
}"
```

Response fields:
- `hr_name` — official registered name
- `hr_register_number` — e.g. `HRB 12345`
- `hr_court` — e.g. `Amtsgericht München`
- `hr_city` — registered city
- `hr_status` — `active` or `deleted`

`keyword_mode` options:
- `"all"` — all keywords must match (default, strictest)
- `"min"` — at least one keyword
- `"exact"` — exact name match

**Search tips:**
- Try with city first; retry without city if no results
- Strip legal suffix (GmbH, AG, & Co. KG) for broader results
- Use first word only as fallback: `"Muster"` instead of `"Muster Immobilien GmbH"`

---

## Northdata KPI Enrichment

Requires `NORTHDATA_API_KEY` env var. Returns `{ "ok": false, "reason": "no_api_key" }` if not set — skip gracefully.

```
http_fetch url="http://host.docker.internal:8000/northdata/kpis" method="POST" body="{
  \"company_name\": \"Muster Immobilien GmbH\",
  \"register_number\": \"HRB 12345\",
  \"city\": \"München\"
}"
```

Response fields:
- `financials` — multi-year: Bilanzsumme, Umsatz, Gewinn, Eigenkapital, Mitarbeiter
- `latest_kpis` — flat dict of most recent year
- `segment_codes` — WZ/NACE industry codes
- `management` — Geschäftsführer / directors list
- `history` — name/address changes

---

## Bundesanzeiger (Annual Reports)

```
http_fetch url="http://host.docker.internal:8000/bundesanzeiger/search" method="POST" body="{
  \"company_name\": \"Muster GmbH\",
  \"city\": \"München\"
}"
```

Returns links to published Jahresabschlüsse (annual reports) from bundesanzeiger.de.

---

## Gotchas

- **Rate limiting**: Handelsregister blocks rapid requests — wait 2–3s between lookups
- **City variants**: Try `München` / `Munich`, `Köln` / `Cologne`
- **No HR result**: Sole traders (Einzelunternehmen) and very small businesses often not registered
- **Northdata**: Only works for companies with published financials (GmbH/AG above threshold)
- **Deduplication**: Pipeline deduplicates by LinkedIn URL or name+location — safe to re-run
