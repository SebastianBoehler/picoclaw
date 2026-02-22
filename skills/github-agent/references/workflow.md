# GitHub Agent — Detailed Workflows

## Critical Rule: Fresh Shell Per exec Call

Each `exec` tool call starts in a **fresh shell** — `cd` does NOT persist between calls.
Always chain directory changes with commands in a single exec call:

```bash
# CORRECT — all in one exec call
cd /tmp/sunderlabs && git checkout -b agent/my-feature && git add -A && git commit -m "[Agent] description"

# WRONG — cd in one call, git in next (won't work)
cd /tmp/sunderlabs
git add -A  # This runs in /home/picoclaw, not /tmp/sunderlabs
```

---

## Full PR Workflow

```bash
# Step 1: Clone (one exec call)
gh repo clone SebastianBoehler/sunderlabs /tmp/sunderlabs

# Step 2: Create branch + make changes (one exec call)
cd /tmp/sunderlabs && git checkout -b agent/<task-slug> && \
  echo "# change" >> path/to/file.py && \
  git add -A && \
  git commit -m "[Agent] <description of change>"

# Step 3: Push + open PR (one exec call)
cd /tmp/sunderlabs && git push origin agent/<task-slug> && \
  gh pr create \
    --title "[Agent] <description>" \
    --body "## What
<what was changed>

## Why
<reason for change>

## Notes
<any caveats or follow-up needed>" \
    --base main \
    --head agent/<task-slug>
```

---

## Verify Auth Before Starting

```bash
gh auth status
gh api user --jq .login
echo "Token: ${GH_TOKEN:0:10}..."
```

If auth fails, the token may have expired. Check `GITHUB_TOKEN` env var.

---

## Multi-File Changes

```bash
cd /tmp/sunderlabs && git checkout -b agent/<task-slug>

# Make multiple file changes
cd /tmp/sunderlabs && \
  sed -i 's/old_value/new_value/g' path/to/file1.py && \
  echo "new content" > path/to/file2.ts && \
  git add -A && \
  git commit -m "[Agent] <description>"
```

---

## Check Existing PRs Before Starting

```bash
# List open PRs
gh pr list --repo SebastianBoehler/sunderlabs --state open

# Check if a branch already exists
cd /tmp/sunderlabs && git fetch origin && git branch -r | grep agent/
```

If a branch already exists for this task, update it instead of creating a new one:

```bash
cd /tmp/sunderlabs && \
  git checkout agent/<existing-slug> && \
  git pull origin main --rebase && \
  # make changes
  git add -A && git commit -m "[Agent] update" && \
  git push origin agent/<existing-slug>
```

---

## Read Files From Repo Without Full Clone

```bash
# Read a single file
gh api repos/SebastianBoehler/sunderlabs/contents/path/to/file.py \
  --jq '.content' | base64 -d

# List directory contents
gh api repos/SebastianBoehler/sunderlabs/contents/nextjs/lib \
  --jq '.[].name'
```

---

## Monorepo Structure (sunderlabs)

```
sunderlabs/
├── nextjs/          # Next.js frontend (Vercel)
│   ├── app/         # App router pages + API routes
│   ├── components/  # React components
│   └── lib/         # Shared utilities, types, DB helpers
├── python/          # Python FastAPI backend
│   └── api/routes/  # API route handlers
├── workflows/       # Content generation pipelines
│   ├── carousel/    # LinkedIn carousel pipeline
│   ├── meme/        # Meme generation pipeline
│   ├── social/      # Social post pipeline
│   └── leads/       # Lead discovery pipeline
├── picoclaw/        # Agent gateway (email + Telegram)
│   ├── gateway/     # email_gateway.py, telegram_gateway.py
│   └── skills/      # Agent skill files
└── scripts/         # Utility scripts
```

---

## PR Body Template

```markdown
## What
[Concise description of what was changed]

## Why
[Reason — what problem does this solve or what feature does it add]

## Changes
- `path/to/file1.py` — [what changed]
- `path/to/file2.ts` — [what changed]

## Notes
[Any caveats, follow-up tasks, or things to watch out for]
[If this is a partial fix, note what's still needed]
```
