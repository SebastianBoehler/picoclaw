---
name: code-search
description: Search and navigate codebases — find functions, trace data flow, locate files, do refactors across many files. Use when working on code tasks in cloned repos or the picoclaw workspace.
---

# Code Search & Codebase Navigation

Use this skill when working on code tasks: finding functions, tracing data flow, understanding a codebase, locating files, or doing refactors across many files.

## Available tools

| Tool           | Command                            | Best for                           |
| -------------- | ---------------------------------- | ---------------------------------- |
| `rg` (ripgrep) | `rg PATTERN [PATH]`                | Fast regex search across files     |
| `fd`           | `fd PATTERN [PATH]`                | Find files by name/extension       |
| `grep`         | `grep -r PATTERN [PATH]`           | Fallback regex search              |
| `find`         | `find PATH -name PATTERN`          | Find files with complex filters    |
| `jq`           | `jq '.key' file.json`              | Parse and query JSON               |
| `git`          | `git log`, `git diff`, `git blame` | History, changes, authorship       |
| `sed`          | `sed 's/old/new/g' file`           | In-place text substitution         |
| `awk`          | `awk '{print $1}' file`            | Column extraction, text processing |
| `diff`         | `diff file1 file2`                 | Compare files                      |
| `wc`           | `wc -l file`                       | Count lines                        |
| `file`         | `file path`                        | Detect file type                   |

## Workflow: Understand a codebase

```bash
# 1. Get the lay of the land
fd . /workspace --type f --extension ts --extension py | head -40

# 2. Find where something is defined
rg "function sendReply\|def send_reply\|sendReply" /workspace -l

# 3. Read the file
cat /workspace/path/to/file.py

# 4. Trace callers
rg "send_reply" /workspace --type py -n

# 5. Check recent changes
git -C /workspace log --oneline -20
git -C /workspace diff HEAD~1
```

## Workflow: Find and fix across files

```bash
# Find all files containing a pattern
rg "old_function_name" /workspace -l

# Preview matches with context
rg "old_function_name" /workspace -n -C 3

# Replace across files (sed, one file at a time)
sed -i 's/old_function_name/new_function_name/g' path/to/file.py

# Verify change
rg "new_function_name" path/to/file.py
```

## Workflow: Understand a specific function

```bash
# Find definition
rg "def process_inbox\|function processInbox" /workspace -n

# Find all callers
rg "process_inbox\|processInbox" /workspace -n --type py

# Check git blame for context
git -C /workspace blame path/to/file.py -L 50,80
```

## Key ripgrep flags

```
-l          list matching files only
-n          show line numbers
-C 3        3 lines of context around match
-i          case-insensitive
-t py       filter by file type (py, ts, js, go, md, json...)
-g "*.ts"   glob filter
--no-ignore search gitignored files too
-w          whole word match
```

## Key fd flags

```
-t f        files only
-t d        directories only
-e ts       by extension
-H          include hidden files
--max-depth 3
```

## Key jq patterns

```bash
# Pretty print
jq '.' file.json

# Extract field
jq '.name' file.json

# Array items
jq '.[].id' file.json

# Filter array
jq '[.[] | select(.status == "running")]' file.json

# Count
jq 'length' file.json
```

## Key git patterns

```bash
# What changed recently
git -C /path log --oneline -20

# Diff unstaged
git -C /path diff

# Diff specific file
git -C /path diff HEAD path/to/file

# Who wrote this line
git -C /path blame path/to/file -L 10,20

# Search commit messages
git -C /path log --oneline --grep="fix"

# Find when a string was introduced
git -C /path log -S "function_name" --oneline
```

## Sunderlabs workspace paths

When working on Sunderlabs projects via exec, key paths:

- Workspace root: `/home/picoclaw/.picoclaw/workspace/`
- Plans: `/home/picoclaw/.picoclaw/workspace/plans/`
- Leads: `/home/picoclaw/.picoclaw/workspace/leads/`
- Research: `/home/picoclaw/.picoclaw/workspace/research/`
- Tasks: `/home/picoclaw/.picoclaw/workspace/tasks/`
- Attachments: `/home/picoclaw/.picoclaw/workspace/attachments/<task_id>/`
- Memory: `/home/picoclaw/.picoclaw/workspace/memory/MEMORY.md`
- Staged config: `/home/picoclaw/.picoclaw/workspace/.staged/config.json`

### Gateway source files (in container)

- Email gateway: `/home/picoclaw/email_gateway.py`
- Telegram gateway: `/home/picoclaw/telegram_gateway.py`
- Skills: `/home/picoclaw/.picoclaw/skills/`

For cloned repos, use `/tmp/` as scratch space:

```bash
git clone https://github.com/org/repo /tmp/repo
cd /tmp/repo && rg "pattern" .
```
