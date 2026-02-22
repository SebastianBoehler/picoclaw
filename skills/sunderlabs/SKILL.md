---
name: sunderlabs
description: Control Sunderlabs Studio from the command line. Use when asked to manage leads, generate content (memes, carousels, social posts), manage releases, list entities, or interact with the Sunderlabs platform. CLI is at /home/picoclaw/sunderlabs_cli.py.
---

# Sunderlabs CLI

All commands use: `python3 /home/picoclaw/sunderlabs_cli.py <group> <cmd> [options]`

`SUNDERLABS_API_URL` is already set in your environment (points to the Studio API).

---

## Leads

```bash
# List leads
python3 /home/picoclaw/sunderlabs_cli.py leads list [--status new|contacted|qualified|disqualified] [--q QUERY] [--limit N]

# Get lead detail
python3 /home/picoclaw/sunderlabs_cli.py leads get <id>

# Create lead
python3 /home/picoclaw/sunderlabs_cli.py leads create --name "Name" [--company C] [--title T] [--email E] [--linkedin URL] [--source SRC] [--score N] [--notes TEXT]

# Update lead
python3 /home/picoclaw/sunderlabs_cli.py leads update <id> [--status S] [--score N] [--notes TEXT] [--tags tag1,tag2]

# Delete lead
python3 /home/picoclaw/sunderlabs_cli.py leads delete <id>

# Start lead discovery pipeline (async batch)
python3 /home/picoclaw/sunderlabs_cli.py leads discover --category "Steuerberater" --location "München" [--limit 20] [--icp "SME with 10-50 employees"] [--enrich]

# Check batch status
python3 /home/picoclaw/sunderlabs_cli.py leads batch-status <batch_id>

# List recent batches
python3 /home/picoclaw/sunderlabs_cli.py leads batch
```

## Content Generation

```bash
# Generate meme
python3 /home/picoclaw/sunderlabs_cli.py meme generate --entity <slug> --topic "topic text" [--style STYLE]

# Generate carousel
python3 /home/picoclaw/sunderlabs_cli.py carousel generate --entity <slug> --topic "topic text" [--slides N]

# Generate social post
python3 /home/picoclaw/sunderlabs_cli.py social generate --entity <slug> --topic "topic text"
```

## Releases (Music)

```bash
# List releases for an artist
python3 /home/picoclaw/sunderlabs_cli.py release list --artist <artist-slug>

# List release assets
python3 /home/picoclaw/sunderlabs_cli.py release assets --artist <slug> --release <slug> [--refresh]

# Run release pipeline
python3 /home/picoclaw/sunderlabs_cli.py release run --artist <slug> --release <slug>
```

## Entities

```bash
# List entities (artists, influencers, meme accounts, etc.)
python3 /home/picoclaw/sunderlabs_cli.py entities list [--type artist|influencer|meme_account]

# Get entity detail
python3 /home/picoclaw/sunderlabs_cli.py entities get <slug>
```

## Kanban (shortcut — prefer kanban.py directly)

```bash
python3 /home/picoclaw/sunderlabs_cli.py kanban list [--assignee A] [--status S]
python3 /home/picoclaw/sunderlabs_cli.py kanban create --title "Title" [--assignee A] [--description D]
python3 /home/picoclaw/sunderlabs_cli.py kanban update <id> [--status todo|in_progress|done|blocked] [--rex-approved]
python3 /home/picoclaw/sunderlabs_cli.py kanban poll --assignee <persona>
python3 /home/picoclaw/sunderlabs_cli.py kanban handoff <id> --to <persona>
```

## Config check

```bash
python3 /home/picoclaw/sunderlabs_cli.py config show
```

---

## Workflows

### Research + save leads from discovery batch

1. `leads discover --category "..." --location "..." --icp "..."` → get `batch_id`
2. Poll every 30s: `leads batch-status <batch_id>` until `status: completed`
3. `leads list --source discovery --limit 50` → review top leads
4. Save summary to `shared/output/task-<id>/leads.md`

### Check what entities exist before generating content

1. `entities list` → pick the right slug
2. `entities get <slug>` → confirm name, type, tags
3. Then call `meme generate` / `carousel generate` / `social generate`
