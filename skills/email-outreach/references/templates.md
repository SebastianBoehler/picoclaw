# Email Outreach — Templates & Best Practices

## German Cold Outreach Template (B2B)

```
Subject: [Specific hook] — Sunderlabs

Sehr geehrte/r [Name / Damen und Herren],

[1 sentence: why this specific company caught your attention — reference something real: recent expansion, industry, location, specific product/service]

[1-2 sentences: what Sunderlabs offers and why it's relevant to them specifically]

[1 sentence: clear CTA — call, demo, or reply]

Mit freundlichen Grüßen,
Sebastian Boehler
Sunderlabs UG
sunderlabs.com | contact@sunderlabs.com
```

### Example — Web Agency

```
Subject: KI-Automatisierung für Webagenturen — Sunderlabs

Sehr geehrte Damen und Herren,

Ihre Agentur in München fällt mir durch die starke Fokussierung auf mittelständische Kunden auf — genau die Zielgruppe, die aktuell am meisten von KI-gestützten Workflows profitiert.

Sunderlabs entwickelt Automatisierungslösungen für Agenturen: von KI-gestützter Content-Erstellung bis hin zu automatisierten Lead-Pipelines, die sich nahtlos in bestehende Prozesse integrieren.

Hätten Sie 15 Minuten für ein kurzes Gespräch diese Woche?

Mit freundlichen Grüßen,
Sebastian Boehler
Sunderlabs UG
sunderlabs.com
```

### Example — Property Management

```
Subject: Digitalisierung Immobilienverwaltung — Sunderlabs

Sehr geehrte/r [Name],

Ich bin auf Ihr Unternehmen gestoßen und sehe, dass Sie im Bereich Immobilienverwaltung in [Stadt] tätig sind — ein Bereich, der aktuell stark von KI-Automatisierung profitiert.

Wir bei Sunderlabs helfen Immobilienunternehmen, Routineaufgaben (Mieterkorrespondenz, Dokumentenverarbeitung, Lead-Qualifizierung) zu automatisieren und so Kapazitäten für das Kerngeschäft freizusetzen.

Darf ich Ihnen in 10 Minuten zeigen, was konkret möglich wäre?

Mit freundlichen Grüßen,
Sebastian Boehler
Sunderlabs UG
sunderlabs.com
```

---

## Follow-Up Template (after no reply, 5-7 days later)

```
Subject: Re: [original subject]

Guten Tag [Name],

ich wollte kurz nachfragen, ob meine letzte Nachricht angekommen ist.

[One new piece of value or context — a relevant case study, stat, or observation about their industry]

Falls das Timing gerade nicht passt, kein Problem — ich melde mich gerne in einem Monat nochmal.

Viele Grüße,
Sebastian Boehler
```

---

## Subject Line Formulas

Good (specific):
- `KI-Automatisierung für [Branche] — Sunderlabs`
- `Leads für [Branche] in [Stadt] — Frage`
- `[Company Name] + Sunderlabs — kurze Frage`

Bad (generic):
- `Zusammenarbeit`
- `Anfrage`
- `Kontaktaufnahme`

---

## Rules

- Max 5 sentences in body
- Always personalize — reference something real about the company
- Language: German for DE/AT/CH, English for international
- Never send to more than 50 per day
- Always log to outreach log
- Never send without approval unless `AUTONOMOUS_OUTREACH=true`

---

## Outreach Log

Append to: `/home/picoclaw/.picoclaw/workspace/leads/outreach-log.md`

```markdown
## [YYYY-MM-DD] — [Company Name]

- **To**: contact@company.com
- **Subject**: [subject line used]
- **Status**: Sent / Draft / Replied / Bounced
- **Notes**: [any response, follow-up date, or context]
```
