#!/bin/sh
# agent_entrypoint.sh — Picoclaw task container setup helper.
#
# NOTE: This script is NOT the container ENTRYPOINT.
# The container runs:  python3 telegram_gateway.py  (or email_gateway.py)
# which calls `picoclaw agent -m <prompt>` as a subprocess after this setup.
#
# This file documents the env vars consumed and the workspace layout.
# The actual persona switching + private workspace creation happens in
# run_task_mode() inside each gateway's Python file, before picoclaw agent runs.
#
# ── Env vars consumed by task containers ──────────────────────────────────────
#   PICOCLAW_PERSONA        — persona name: max (default), researcher,
#                             backend-dev, marketing, lead-gen, analyst
#                             → copies /home/picoclaw/personas/<name>/IDENTITY.md
#                               into workspace/IDENTITY.md before agent starts
#   PICOCLAW_TASK_ID        — unique hex task ID (set by gateway)
#   PICOCLAW_TASK_MODE      — "1" when running as a task container
#   PICOCLAW_DEBUG          — "1" to enable picoclaw --debug flag
#
# ── Workspace layout ──────────────────────────────────────────────────────────
#
#   SHARED volume  (picoclaw_picoclaw-workspace)
#   mounted at:    /home/picoclaw/.picoclaw/workspace/
#   ├── .staged/                    # config.json + github_app.pem (read-only by agents)
#   ├── IDENTITY.md                 # active persona — overwritten per task
#   ├── SOUL.md / AGENT.md / ...    # shared agent context files
#   ├── memory/                     # long-term agent memory (shared, persistent)
#   ├── sessions/                   # session history (cleared per task to avoid poisoning)
#   ├── plans/                      # task plans (auto-cleaned after task)
#   ├── research/                   # saved research outputs (persistent, shared)
#   ├── leads/                      # lead lists (persistent, shared)
#   ├── reply-files/                # files to attach to replies (per task_id subfolder)
#   │   └── <task_id>/
#   └── tasks/
#       ├── <task_id>.json          # task input file (deleted before agent runs)
#       └── <task_id>/              # PRIVATE scratch space — only this container writes here
#           ├── scratch.md          # working notes
#           ├── raw/                # raw API responses, downloads
#           └── processed/          # cleaned/parsed data
#
#   Path convention:
#     Shared persistent:  workspace/<category>/          (research/, leads/, memory/)
#     Per-task private:   workspace/tasks/<task_id>/     (scratch, intermediates)
#     Reply target:       workspace/tasks/<task_id>_reply.md  (telegram)
#                         workspace/reply.md                   (email/kanban)
#
# ── Future flags (not yet implemented) ────────────────────────────────────────
#
#   PICOCLAW_MODEL          — override the LLM model for this task
#                             # would patch config.json agents.defaults.model before agent starts
#
#   PICOCLAW_TOOLS_DISABLED — comma-separated tool names to disable
#                             # e.g. "exec,web_fetch" — would write a tools override file
#
#   PICOCLAW_MCP_CONFIG     — JSON string with MCP server config to inject
#                             # would write to workspace/mcp.json before agent starts
#
#   PICOCLAW_SKILLS         — comma-separated skill names to enable for this task
#                             # would symlink from /home/picoclaw/skills/ into workspace/skills/
#
#   PICOCLAW_MEMORY_NS      — memory namespace (default: shared)
#                             # would point agent at workspace/memory/<ns>/ instead of shared
#
#   PICOCLAW_MAX_ITERATIONS — cap on agent tool-call iterations
#                             # would be passed as a flag once picoclaw agent supports it
#
# ── Implementation reference (Python, in run_task_mode) ───────────────────────
#
#   persona = os.environ.get("PICOCLAW_PERSONA", "max")
#   if persona != "max":
#       shutil.copy2(f"/home/picoclaw/personas/{persona}/IDENTITY.md",
#                    f"{workspace}/IDENTITY.md")
#
#   private_dir = os.path.join(workspace, "tasks", task_id)
#   os.makedirs(private_dir, exist_ok=True)
#
#   # Future: model override
#   # model = os.environ.get("PICOCLAW_MODEL")
#   # if model:
#   #     patch_config_model(workspace, model)
#
#   # Future: tools disabled
#   # tools_off = os.environ.get("PICOCLAW_TOOLS_DISABLED", "")
#   # if tools_off:
#   #     write_tools_override(workspace, tools_off.split(","))
#
#   # Future: MCP config
#   # mcp_cfg = os.environ.get("PICOCLAW_MCP_CONFIG")
#   # if mcp_cfg:
#   #     with open(f"{workspace}/mcp.json", "w") as f: f.write(mcp_cfg)
#
#   # Future: skills
#   # skills = os.environ.get("PICOCLAW_SKILLS", "")
#   # if skills:
#   #     enable_skills(workspace, skills.split(","))

