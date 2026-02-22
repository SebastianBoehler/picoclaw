# Lead Research — Output Formats

## Lead List

Save to: `/home/picoclaw/.picoclaw/workspace/leads/MM_DD_YYYY/<category>-<location>.md`

```markdown
---
task: Lead Research — [Category] in [Location]
status: done
started: YYYY-MM-DD
---

# Lead List: [Category] in [Location] — [Date]

**Total found**: N | **With email**: N | **With HR data**: N

---

## 1. [Company Name] — Score: 8.5/10

- **Type**: GmbH
- **Reg**: HRB 12345, Amtsgericht München
- **Address**: Musterstraße 1, 80331 München
- **Directors**: Max Mustermann (Geschäftsführer)
- **Website**: https://example.com
- **Email**: info@example.com
- **Phone**: +49 89 123456
- **Revenue**: ~€5M (2023)
- **Employees**: ~50
- **ICP fit**: Strong — family-owned, no CRM visible, recently expanded
- **Notes**: 2nd location opened 2024

---

## 2. [Company Name] — Score: 7.0/10
...
```

Also export a CSV to: `/home/picoclaw/.picoclaw/workspace/leads/MM_DD_YYYY/<category>-<location>.csv`

```csv
name,type,register_number,court,address,directors,website,email,phone,revenue,employees,score,icp_fit
"Muster Immobilien GmbH","GmbH","HRB 12345","Amtsgericht München","Musterstraße 1, 80331 München","Max Mustermann","https://example.com","info@example.com","+49 89 123456","~€5M","~50","8.5","Strong"
```

---

## Company Research

Save to: `/home/picoclaw/.picoclaw/workspace/research/MM_DD_YYYY/<company-slug>.md`

```markdown
---
task: Company Research — [Company Name]
status: done
---

# [Company Name]

## Registration
- **HR Number**: HRB 12345
- **Court**: Amtsgericht München
- **Status**: active
- **Legal form**: GmbH

## Management
- Max Mustermann — Geschäftsführer (since 2015)

## Financials (latest year)
- **Revenue**: €4.2M
- **Employees**: 48
- **Equity**: €1.1M

## Web Presence
- **Website**: https://example.com
- **LinkedIn**: https://linkedin.com/company/...

## Notes
[Key findings, news, context]
```

---

## Reply Summary Format

Always include in `reply.md`:

```markdown
## Lead Research Results — [Category] in [Location]

Found **N leads** (N with email, N with HR data).

### Top 3 Leads

1. **[Company]** — Score 8.5/10 — [one-line reason]
2. **[Company]** — Score 7.8/10 — [one-line reason]
3. **[Company]** — Score 7.2/10 — [one-line reason]

Full list saved to: `leads/MM_DD_YYYY/<category>-<location>.md`
CSV export: `leads/MM_DD_YYYY/<category>-<location>.csv`
```
