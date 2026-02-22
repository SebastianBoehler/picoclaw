---
name: telegram-agent
description: Understand and work with the Picoclaw Telegram gateway — multi-agent group chat system with coordinator, inline agents (Luna, Felix, Mira, Kai), and Max as the task agent who spawns Docker containers. Use when asked about the Telegram bot, agent roster, coordinator logic, or when Max needs to execute a task received via Telegram.
---

# Telegram Gateway — Multi-Agent System

**Agent roster, system prompts, routing examples**: See [references/agents.md](references/agents.md)

## Architecture

```
User message → Coordinator (LLM) → picks agent(s) → inline reply OR task container (Max only)
```

| Agent    | Role                                      | Spawns container? |
| -------- | ----------------------------------------- | ----------------- |
| Max 🧑‍💻   | Developer — code, research, GitHub, leads | **YES**           |
| Luna 🌙  | Marketing                                 | No                |
| Felix 🔍 | First Principles                          | No                |
| Mira ⚡  | Critic                                    | No                |
| Kai 📋   | Planner                                   | No                |

## Coordinator Output

```json
{ "agents": ["max"], "is_task": true, "casual": false, "discuss": false }
```

- `is_task: true` → Max spawns a Docker container
- `casual: true` → 1-2 sentence replies only
- `discuss: true` → multi-round discussion before task

## Task Execution (Max)

Container env: `PICOCLAW_TASK_MODE=1`, `PICOCLAW_TASK_ID=<uuid>`, `PICOCLAW_TASK_TO=<chat_id>`

Reply written to: `~/.picoclaw/workspace/tasks/<task_id>_reply.md`

File attachments: save to `~/.picoclaw/workspace/attachments/<task_id>/` — gateway sends via `sendDocument`

## Docker Commands

```bash
docker compose --profile telegram-gateway build picoclaw-telegram-gateway
docker compose --profile telegram-gateway up -d --force-recreate picoclaw-telegram-gateway
docker logs picoclaw-telegram-gateway -f
```

## Key Env Vars

```
TELEGRAM_BOT_TOKEN        ALLOWED_USERNAMES
OPENROUTER_API_KEY        ROUTER_MODEL (default: google/gemini-2.5-flash)
PICOCLAW_BASE_IMAGE       PICOCLAW_WORKSPACE_VOLUME
```
