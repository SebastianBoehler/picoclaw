---
name: github-automation
description: "Clone a GitHub repo, do work on a branch, open a PR, and notify the user via message. Use this for on-demand coding tasks triggered by chat."
metadata: {"nanobot":{"emoji":"🤖","requires":{"bins":["git","gh"]},"install":[{"id":"brew-git","kind":"brew","formula":"git","bins":["git"],"label":"Install git (brew)"},{"id":"brew-gh","kind":"brew","formula":"gh","bins":["gh"],"label":"Install GitHub CLI (brew)"},{"id":"apt-git","kind":"apt","package":"git","bins":["git"],"label":"Install git (apt)"},{"id":"apt-gh","kind":"apt","package":"gh","bins":["gh"],"label":"Install GitHub CLI (apt)"}]}}
---

# GitHub Automation Skill

Use this skill when the user asks you to work on a GitHub repository: clone it, make changes, open a PR, and notify them.

## Prerequisites

- `git` must be on PATH
- `gh` CLI must be on PATH and authenticated (`gh auth status`)
- Git user identity must be configured (see setup below)

## Setup (run once if not already done)

```bash
gh auth status
git config --global user.email "bot@picoclaw.local"
git config --global user.name "PicoClaw Bot"
```

## Full Workflow

### Step 1 — Clone the repo

Clone into the workspace so files stay within the sandbox:

```bash
REPO="owner/repo-name"
WORK_DIR="/tmp/picoclaw-work/${REPO##*/}"
git clone "https://github.com/${REPO}.git" "$WORK_DIR"
```

If the repo was already cloned, pull latest instead:

```bash
git -C "$WORK_DIR" fetch origin
git -C "$WORK_DIR" checkout main
git -C "$WORK_DIR" pull origin main
```

### Step 2 — Create a feature branch

Use a descriptive, slug-friendly branch name based on the task:

```bash
BRANCH="picoclaw/$(date +%Y%m%d)-short-task-description"
git -C "$WORK_DIR" checkout -b "$BRANCH"
```

### Step 3 — Do the work

Use the `edit` or `filesystem` tools to read and modify files inside `$WORK_DIR`.
Use `exec` with `working_dir` set to `$WORK_DIR` to run tests, linters, or build commands.

Always verify changes compile/pass before committing:

```bash
# Example: run tests
cd "$WORK_DIR" && npm test
# or
cd "$WORK_DIR" && go test ./...
# or
cd "$WORK_DIR" && python -m pytest
```

### Step 4 — Commit

Stage and commit only the files you changed:

```bash
git -C "$WORK_DIR" add -A
git -C "$WORK_DIR" commit -m "feat: <short description of change>

<optional longer description of what was done and why>"
```

### Step 5 — Push the branch

```bash
git -C "$WORK_DIR" push origin "$BRANCH"
```

### Step 6 — Open a Pull Request

```bash
PR_URL=$(gh pr create \
  --repo "$REPO" \
  --head "$BRANCH" \
  --base main \
  --title "feat: <short title>" \
  --body "## Summary

<What was changed and why>

## Changes
- <bullet list of key changes>

---
*Opened automatically by PicoClaw*" \
  --json url --jq '.url')

echo "PR created: $PR_URL"
```

### Step 7 — Notify the user

After the PR is created, always send a message to the user:

```
Use the message tool with content:
"✅ PR opened: <PR title>
🔗 <PR_URL>
📁 Repo: <REPO>
🌿 Branch: <BRANCH>"
```

## Error Handling

- If `git push` fails due to auth: run `gh auth status` and re-authenticate
- If tests fail: fix the issue before committing, or note the failure in the PR body
- If the branch already exists: append a timestamp suffix to the branch name
- If `gh pr create` fails: check `gh auth status` and that the repo allows PRs

## Example Interaction

User: "Clone my repo sebastianboehler/sunderlabs and add a .editorconfig file"

You should:
1. Clone `sebastianboehler/sunderlabs` to `/tmp/picoclaw-work/sunderlabs`
2. Create branch `picoclaw/20260219-add-editorconfig`
3. Write the `.editorconfig` file
4. Commit: `chore: add .editorconfig`
5. Push and open PR
6. Message user with the PR link

## Tips

- Always read existing files before editing to understand conventions
- Keep PRs small and focused — one task per PR
- Use `gh pr checks <PR_NUMBER> --repo <REPO>` to monitor CI after opening the PR
- If the user wants you to monitor CI, use the `cron` tool to check back in 5 minutes
