#!/usr/bin/env python3
"""
Picoclaw Kanban Gateway
Polls MongoDB for scheduled kanban tasks, spawns agent containers to execute them.

Runs every POLL_INTERVAL seconds (default: 1800 = 30 min).
Supports cron expressions and ISO datetime one-shot schedules.

Required env vars:
  MONGODB_URI          - MongoDB connection string
  POLL_INTERVAL        - Seconds between polls (default: 1800)
"""

import os
import time
import logging
import json
import threading
from datetime import datetime, timezone

from gh_auth import init_gh_token
from agent_env import build_agent_env as _build_agent_env_gh
from kanban import kanban_finish

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("kanban-gateway")

MONGODB_URI   = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/agency")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "1800"))

# Docker / agent container config (same as email gateway)
PICOCLAW_BASE_IMAGE      = os.environ.get("PICOCLAW_BASE_IMAGE", "picoclaw-agent")
_AGENT_IMAGE             = os.environ.get("PICOCLAW_AGENT_IMAGE", PICOCLAW_BASE_IMAGE)
PICOCLAW_WORKSPACE_VOLUME = os.environ.get("PICOCLAW_WORKSPACE_VOLUME", "picoclaw_picoclaw-workspace")
PICOCLAW_TRACES_DB_URL   = os.environ.get("PICOCLAW_TRACES_DB_URL", "")
PICOCLAW_BIN             = os.environ.get("PICOCLAW_BIN", "picoclaw")
PICOCLAW_DEBUG           = os.environ.get("PICOCLAW_DEBUG", "").lower() in ("1", "true", "yes")


_DOCKER_CLIENT = None


def _get_docker():
    global _DOCKER_CLIENT
    if _DOCKER_CLIENT is None:
        import docker
        _DOCKER_CLIENT = docker.from_env()
    return _DOCKER_CLIENT


def _get_mongo_col():
    from pymongo import MongoClient
    client = MongoClient(MONGODB_URI)
    db_name = MONGODB_URI.rstrip("/").split("/")[-1].split("?")[0] or "agency"
    return client[db_name]["kanban_tasks"]


def _task_query(task_id: str) -> dict:
    """Build a MongoDB query that matches by ObjectId or raw string _id."""
    from bson import ObjectId
    try:
        return {"_id": ObjectId(task_id)}
    except Exception:
        return {"_id": task_id}


def _cron_is_due(cron_expr: str, now: datetime, last_run: datetime | None) -> bool:
    """Check if a cron expression is due relative to now and last_run."""
    try:
        from croniter import croniter
        if last_run is None:
            # Never run — always due on first encounter
            return True
        else:
            it = croniter(cron_expr, last_run.replace(tzinfo=timezone.utc))
            nxt = it.get_next(datetime)
            return nxt <= now
    except Exception as e:
        log.warning(f"cron parse error '{cron_expr}': {e}")
        return False


def _iso_is_due(iso_str: str, now: datetime) -> bool:
    """Check if an ISO datetime one-shot schedule is due."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now
    except Exception:
        return False


def _schedule_is_due(schedule: str, now: datetime, last_run: datetime | None) -> bool:
    s = schedule.strip()
    if not s:
        return False
    # Cron: 5 or 6 space-separated fields
    parts = s.split()
    if len(parts) in (5, 6) and not s.startswith("20"):
        return _cron_is_due(s, now, last_run)
    # ISO datetime one-shot
    return _iso_is_due(s, now)


def _build_agent_env() -> dict:
    return _build_agent_env_gh()


def _spawn_task_container(task_id: str, task_doc: dict) -> str:
    """Spawn a dedicated Docker container for this kanban task. Returns container short_id."""
    import uuid
    client = _get_docker()

    persona = task_doc.get("persona", "max")
    title   = task_doc.get("title", "Untitled task")
    desc    = task_doc.get("description", "")

    run_id = uuid.uuid4().hex[:12]

    prompt = (
        f"You are an autonomous AI assistant executing a scheduled kanban task.\n\n"
        f"## Task\n**{title}**\n\n"
        f"{desc}\n\n"
        f"## Hard Rules\n"
        f"- Complete the task fully — do not stop early\n"
        f"- NEVER ask clarifying questions — assume and proceed\n"
        f"- Your LAST action MUST write a concise result summary to:\n"
        f"  /home/picoclaw/.picoclaw/workspace/reply.md\n"
        f"- The task is NOT complete until reply.md is written\n"
    )

    workspace = os.path.expanduser("~/.picoclaw/workspace")
    task_file = os.path.join(workspace, "tasks", f"{run_id}.json")
    os.makedirs(os.path.dirname(task_file), exist_ok=True)
    with open(task_file, "w") as f:
        json.dump({
            "task_id":    run_id,
            "sender":     "sebastian@sunderlabs.com",
            "subject":    f"[Kanban] {title}",
            "message_id": f"kanban-{task_id}",
            "prompt":     prompt,
            "persona":    persona,
        }, f)

    agent_env = _build_agent_env()
    agent_env["PICOCLAW_TASK_ID"]         = run_id
    agent_env["PICOCLAW_TASK_MODE"]       = "1"
    agent_env["PICOCLAW_CONTAINER_START"] = str(time.time())
    agent_env["PICOCLAW_CONFIG_PATH"]     = "/home/picoclaw/.picoclaw/workspace/.staged/config.json"
    agent_env["PICOCLAW_PEM_PATH"]        = "/home/picoclaw/.picoclaw/workspace/.staged/github_app.pem"
    agent_env["GITHUB_APP_PRIVATE_KEY"]   = "/home/picoclaw/.picoclaw/workspace/.staged/github_app.pem"
    agent_env["PICOCLAW_TASK_TO"]         = "sebastian@sunderlabs.com"
    agent_env["PICOCLAW_TASK_SUBJECT"]    = f"[Kanban] {title}"
    agent_env["PICOCLAW_TASK_MESSAGE_ID"] = f"kanban-{task_id}"
    agent_env["PICOCLAW_PERSONA"]         = persona

    container_name = f"picoclaw-kanban-{run_id}"
    container = client.containers.run(
        _AGENT_IMAGE,
        name=container_name,
        command=["python3", "/home/picoclaw/task_runner.py"],
        environment=agent_env,
        volumes={
            PICOCLAW_WORKSPACE_VOLUME: {"bind": "/home/picoclaw/.picoclaw/workspace", "mode": "rw"},
        },
        labels={
            "picoclaw": "true",
            "picoclaw.role": "agent",
            "picoclaw.task_id": run_id,
            "picoclaw.task_subject": f"[Kanban] {title}"[:128],
            "picoclaw.task_from": "kanban-gateway",
            "picoclaw.persona": persona,
            "picoclaw.kanban_task_id": str(task_id),
        },
        detach=True,
        remove=True,
    )
    log.info(f"Kanban container spawned: {container_name} ({container.short_id}) task_id={task_id}")
    return run_id, container.short_id


def _wait_and_collect(container_short_id: str, run_id: str, mongo_task_id: str) -> None:
    """Background thread: wait for container to finish, collect result, update MongoDB."""
    import docker as _docker
    import tempfile
    client = _get_docker()

    # Poll until container exits (max 30 min)
    deadline = time.time() + 1800
    exit_code = None
    while time.time() < deadline:
        try:
            c = client.containers.get(container_short_id)
            if c.status in ("exited", "dead"):
                exit_code = c.attrs.get("State", {}).get("ExitCode", -1)
                break
        except Exception:
            break
        time.sleep(15)

    # Collect result: reply.md > agent's final Response line > raw stdout tail
    import tarfile, io, re as _re
    result = ""

    # 1. Try reply.md from the workspace volume
    try:
        c = client.containers.get(container_short_id)
        bits, _ = c.get_archive("/home/picoclaw/.picoclaw/workspace/reply.md")
        buf = io.BytesIO(b"".join(bits))
        with tarfile.open(fileobj=buf) as tar:
            result = tar.extractfile(tar.getmembers()[0]).read().decode("utf-8", errors="replace").strip()
        log.info(f"Result from reply.md for run {run_id} ({len(result)} chars)")
    except Exception:
        pass

    # 2. Extract agent's final "Response:" line from stdout
    if not result:
        try:
            c = client.containers.get(container_short_id)
            raw = c.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            raw = _re.sub(r"\x1b\[[0-9;]*m", "", raw)
            # Match: agent: Response: <text> {agent_id=...}
            matches = _re.findall(r"agent: Response: (.+?) \{agent_id=", raw, _re.DOTALL)
            if matches:
                result = matches[-1].strip()
                log.info(f"Result from agent Response line for run {run_id} ({len(result)} chars)")
            elif exit_code not in (0, None):
                result = raw.strip()[-2000:]
                log.error(f"Kanban container {container_short_id} exited code {exit_code}:\n{result}")
        except Exception as e:
            log.warning(f"Could not capture result for {container_short_id}: {e}")

    # Update MongoDB task: status → done, result, last_run_at
    from kanban import kanban_update
    kanban_update(mongo_task_id, {
        "status":       "done",
        "result":       result or "(completed — no result written)",
        "last_run_at":  datetime.now(timezone.utc),
        "container_id": container_short_id,
    })
    log.info(f"Kanban task {mongo_task_id} marked done")

    # Remove container
    try:
        c = client.containers.get(container_short_id)
        c.remove(force=True)
    except Exception:
        pass


def _get_active_persona_slugs() -> set:
    """
    Return the set of persona slugs that have a running 24/7 persona container.
    These personas self-poll via HEARTBEAT.md — the gateway should skip them.
    """
    try:
        client = _get_docker()
        containers = client.containers.list(
            filters={"label": "picoclaw.role=persona", "status": "running"}
        )
        return {c.labels.get("picoclaw.persona") for c in containers if c.labels.get("picoclaw.persona")}
    except Exception as e:
        log.warning(f"Could not query active persona containers: {e}")
        return set()


def poll_once() -> None:
    """Single poll: find due scheduled tasks and spawn containers.

    Skips tasks assigned to personas that have a running 24/7 container —
    those personas self-poll via HEARTBEAT.md and will pick up their own tasks.
    """
    now = datetime.now(timezone.utc)

    # Detect which personas are already running 24/7 (skip their tasks)
    active_persona_slugs = _get_active_persona_slugs()
    if active_persona_slugs:
        log.info(f"Active persona containers (will skip their tasks): {active_persona_slugs}")

    try:
        col = _get_mongo_col()
        # Find tasks with a schedule that are not currently in_progress
        tasks = list(col.find({
            "schedule": {"$nin": [None, ""]},
            "status":   {"$nin": ["in_progress"]},
        }))
    except Exception as e:
        log.error(f"MongoDB query failed: {e}")
        return

    log.info(f"Poll: {len(tasks)} scheduled tasks found")

    for task in tasks:
        schedule  = task.get("schedule", "")
        last_run  = task.get("last_run_at")
        task_id   = str(task["_id"])
        assignee  = task.get("assignee") or task.get("persona")

        # Skip tasks whose persona is running 24/7 — they self-poll via HEARTBEAT.md
        if assignee and assignee in active_persona_slugs:
            log.debug(f"Skipping task '{task.get('title')}' — persona '{assignee}' is active")
            continue

        if not _schedule_is_due(schedule, now, last_run):
            continue

        log.info(f"Scheduling task '{task['title']}' (id={task_id}, schedule={schedule})")

        # Mark in_progress immediately to prevent double-spawn
        try:
            col.update_one(
                _task_query(task_id),
                {"$set": {"status": "in_progress", "updated_at": now}},
            )
        except Exception as e:
            log.error(f"Failed to mark task in_progress: {e}")
            continue

        try:
            run_id, container_short_id = _spawn_task_container(task_id, task)
            # Background thread waits for completion and writes result back
            t = threading.Thread(
                target=_wait_and_collect,
                args=(container_short_id, run_id, task_id),
                daemon=True,
            )
            t.start()
        except Exception as e:
            log.error(f"Failed to spawn container for task {task_id}: {e}")
            # Reset to todo so it can be retried
            try:
                col.update_one(
                    _task_query(task_id),
                    {"$set": {"status": "todo", "updated_at": now}},
                )
            except Exception:
                pass


def main():
    log.info(f"Kanban gateway starting — poll interval: {POLL_INTERVAL}s")

    # Verify Docker socket
    try:
        _get_docker().ping()
        log.info("Docker socket ready")
    except Exception as e:
        log.error(f"Docker socket unavailable: {e}")
        raise SystemExit(1)

    init_gh_token(start_refresh_thread=True)

    # Verify MongoDB
    try:
        _get_mongo_col().count_documents({})
        log.info("MongoDB connected")
    except Exception as e:
        log.error(f"MongoDB unavailable: {e}")
        raise SystemExit(1)

    while True:
        try:
            poll_once()
        except Exception as e:
            log.error(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
