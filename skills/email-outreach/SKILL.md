---
name: email-outreach
description: Draft and send outreach emails to leads or third parties via SMTP. Use when asked to contact companies, send cold emails, follow up with prospects, or send any email to an external address (not the reply to the task sender).
---

# Email Outreach

**Templates & best practices**: See [references/templates.md](references/templates.md)

## Key Distinction

- **Task reply** (to the person who sent the email/message) → write to `reply.md`
- **Outreach** (to leads, third parties) → use `send_outbound_email.py` (this skill)

## Whitelist

Outbound emails are **hard-blocked** unless the recipient is in `OUTBOUND_EMAIL_WHITELIST`.
If a send is blocked (exit code 1), report this in `reply.md` — do NOT try to bypass it.

## Send an Email

Use the `send_outbound_email.py` script via `exec`:

```bash
python3 /home/picoclaw/send_outbound_email.py \
  --to "contact@targetcompany.com" \
  --subject "Zusammenarbeit — Sunderlabs" \
  --body "Your email body text here"
```

To use a file as the body (recommended for longer emails — write it first):

```bash
# Step 1: write the draft to a temp file
# (use write_file tool to create /tmp/draft.md)

# Step 2: send it
python3 /home/picoclaw/send_outbound_email.py \
  --to "contact@targetcompany.com" \
  --subject "Zusammenarbeit — Sunderlabs" \
  --body /tmp/draft.md
```

With attachments:

```bash
python3 /home/picoclaw/send_outbound_email.py \
  --to "contact@targetcompany.com" \
  --subject "Angebot — Sunderlabs" \
  --body /tmp/draft.md \
  --attach /tmp/proposal.pdf /tmp/deck.pptx
```

Exit codes:

- `0` — sent successfully
- `1` — recipient blocked by whitelist (report to user, do not retry)
- `2` — missing args or env vars
- `3` — SMTP error (retry once after 10s)

## Workflow

1. Research the lead (use lead-research skill)
2. Personalize — reference something real about the company
3. Draft → show in `reply.md` and ask for approval (unless `AUTONOMOUS_OUTREACH=true`)
4. Send via `send_outbound_email.py`
5. Outreach log is auto-updated at `workspace/leads/outreach-log.md`

## Hard Rules

- Max 50 recipients/day
- Always personalize — no mass blasts
- Never send without approval unless `AUTONOMOUS_OUTREACH=true`
- If blocked by whitelist, report it — never try inline SMTP as a workaround
