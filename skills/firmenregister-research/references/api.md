# Firmenregister Research — API Reference

Base URL: `http://host.docker.internal:8000`
Tool: `http_fetch` (NOT `http_request`)

---

## 1. Web Search

```
http_fetch url="http://host.docker.internal:8000/search" method="POST" body="{\"query\": \"Autohaus GmbH Baden-Württemberg Geschäftsführer Kontakt\", \"max_results\": 10, \"max_tokens\": 4096}"
```

Response: `{ "ok": true, "result": "..." }` — LLM text grounded in live web results.

---

## 2. Handelsregister Search

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

`keyword_mode`:
- `"all"` — all keywords must match (default)
- `"min"` — at least one keyword
- `"exact"` — exact name match

**Search tips:**
- Try with city first; retry without city if no results
- Strip legal suffix (GmbH, AG, & Co. KG) for broader results
- Use first word only as fallback

---

## 3. Lead Discovery Pipeline

```
http_fetch url="http://host.docker.internal:8000/leads-discover" method="POST" body="{
  \"category\": \"Autohaus\",
  \"location\": \"Baden-Württemberg\",
  \"limit\": 20,
  \"icp\": \"Car dealerships 10-100 employees, family-owned\",
  \"use_llm_scoring\": true,
  \"handelsregister_enrich\": true
}"
```

Returns immediately: `{ "ok": true, "batch_id": "...", "status": "started" }`

Poll every 30s:
```
http_fetch url="http://host.docker.internal:8000/leads-discover/{batch_id}" method="GET"
```

List recent batches:
```
http_fetch url="http://host.docker.internal:8000/leads-discover?limit=10" method="GET"
```

---

## 4. Northdata KPI Enrichment

Requires `NORTHDATA_API_KEY`. Returns `{ "ok": false, "reason": "no_api_key" }` if not set — skip gracefully.

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

## 5. Bundesanzeiger (Annual Reports)

```
http_fetch url="http://host.docker.internal:8000/bundesanzeiger/search" method="POST" body="{
  \"company_name\": \"Muster GmbH\",
  \"city\": \"München\"
}"
```

Returns links to published Jahresabschlüsse from bundesanzeiger.de.

---

## Gotchas

- **Rate limiting**: Handelsregister blocks rapid requests — wait 2–3s between lookups
- **City variants**: Try `München` / `Munich`, `Köln` / `Cologne`
- **No HR result**: Sole traders (Einzelunternehmen) often not registered
- **Northdata**: Only works for companies with published financials (GmbH/AG above threshold)
- **ICP specificity**: "family-owned Autohaus, 10-50 employees, no online booking" scores better than "car dealer"
- **Deduplication**: Pipeline deduplicates by LinkedIn URL or name+location — safe to re-run
