---
name: kanban
description: View, create, and update Kanban tasks on the Sunderlabs team board via HTTP.
---

# Kanban Board Skill

The Sunderlabs Kanban board tracks tasks across the team. You can view, create, and update tasks via HTTP.

## Base URL

```
http://host.docker.internal:3100/api/picoclaw/kanban
```

## List all tasks

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban" method="GET"
```

Returns a JSON array of task objects. Each task has:

- `_id` — MongoDB ID (use this for PATCH/DELETE)
- `title` — short task title
- `description` — full description
- `status` — `todo` | `in_progress` | `done` | `blocked`
- `persona` — `max` | `researcher` | `backend-dev` | `marketing` | `lead-gen` | `analyst`
- `priority` — `low` | `medium` | `high`
- `tags` — array of strings
- `result` — completion summary (set when done/blocked)

## Create a task

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban" method="POST" body="{\"title\": \"Task title\", \"description\": \"What needs to be done\", \"status\": \"todo\", \"persona\": \"max\", \"priority\": \"medium\", \"tags\": [\"research\"]}"
```

## Update a task (status, result, etc.)

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban/<task_id>" method="PATCH" body="{\"status\": \"done\", \"result\": \"Brief summary of what was done\"}"
```

Valid status transitions: `todo` → `in_progress` → `done` | `blocked`

## Delete a task

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban/<task_id>" method="DELETE"
```

## Common workflows

### Check what's on the board

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban" method="GET"
```

Filter the result for `status == "todo"` to see pending work.

### Add a task for yourself and mark in progress

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban" method="POST" body="{\"title\": \"Research AI startups Berlin\", \"status\": \"in_progress\", \"persona\": \"max\", \"priority\": \"high\"}"
```

### Mark a task done with a result summary

```
http_fetch url="http://host.docker.internal:3100/api/picoclaw/kanban/<task_id>" method="PATCH" body="{\"status\": \"done\", \"result\": \"Found 12 leads, saved to leads/02_19_2026/ai-startups-berlin.csv\"}"
```
