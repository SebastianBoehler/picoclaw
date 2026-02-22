---
name: github-agent
description: Work with GitHub repos — clone private repos, commit changes, push branches, create PRs, review code, run gh CLI commands. Use when asked to make code changes, open PRs, search repos, or interact with GitHub.
---

# GitHub — Private Repo Access & Pull Requests

**Detailed workflows**: See [references/workflow.md](references/workflow.md)

## Authentication

`GH_TOKEN` and `GITHUB_TOKEN` are pre-injected by the gateway — no file reading needed. The `gh` CLI picks them up automatically.

```bash
gh auth status  # verify before starting
```

## Rules — ALWAYS follow these

1. **NEVER push directly to `main`** — branch-protected
2. **Always create a feature branch**: `agent/<task-slug>`
3. **Always open a PR** — task is NOT done until a PR exists
4. **PR title**: `[Agent] <short description>`
5. **Chain all git commands** — each `exec` call is a fresh shell: `cd /tmp/repo && git add -A && git commit ...`

## Quick Workflow

```bash
# Clone
gh repo clone SebastianBoehler/sunderlabs /tmp/sunderlabs

# Branch + change + commit (one exec call)
cd /tmp/sunderlabs && git checkout -b agent/<slug> && git add -A && git commit -m "[Agent] description"

# Push + PR (one exec call)
cd /tmp/sunderlabs && git push origin agent/<slug> && gh pr create \
  --title "[Agent] description" --base main --head agent/<slug> \
  --body "## What\n...\n\n## Why\n..."
```

## Repos

- `SebastianBoehler/sunderlabs` — main monorepo (Next.js, Python API, picoclaw, workflows)

## Cannot do

- Push to `main` (branch protection)
- Merge PRs (owner approval required)
