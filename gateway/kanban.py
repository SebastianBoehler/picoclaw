#!/usr/bin/env python3
"""
Shared Kanban helpers — direct MongoDB writes, no HTTP dependency.

Used by all gateways (email, telegram, kanban) and persona heartbeats.
Requires MONGODB_URI env var (e.g. mongodb://host.docker.internal:27017/agency).

CLI usage (for agents via exec):
  python3 kanban.py create --title "..." --assignee alex --tenant-id t1 [--description "..."] [--priority high]
  python3 kanban.py poll --assignee alex --tenant-id t1 [--status todo]
  python3 kanban.py update <task_id> --status in_progress
  python3 kanban.py add-file <task_id> --path p --label l --type output --added-by alex
  python3 kanban.py handoff <task_id> --to mia --title "..." [--files "p1,p2"]
  python3 kanban.py finish <task_id> --result "..."
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("kanban")

MONGODB_URI = os.environ.get("MONGODB_URI", "")

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_VALID_FILE_TYPES = {"input", "output", "reference"}


def _get_col():
    """Return (client, collection) or (None, None) if MongoDB not configured."""
    if not MONGODB_URI:
        return None, None
    try:
        from pymongo import MongoClient
        from urllib.parse import urlparse
        parsed = urlparse(MONGODB_URI)
        db_name = parsed.path.lstrip("/").split("?")[0] or "agency"
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        return client, client[db_name]["kanban_tasks"]
    except Exception as e:
        log.warning(f"Kanban MongoDB connect failed: {e}")
        return None, None


def _oid(kanban_id: str):
    """Convert string to ObjectId, fall back to raw string."""
    try:
        from bson import ObjectId
        return ObjectId(kanban_id)
    except Exception:
        return kanban_id


def kanban_create(
    task_id: str,
    title: str,
    sender: str,
    persona: str = "max",
    source: str = "gateway",
    priority: str = "medium",
    tags: list = None,
    metadata: dict = None,
    assignee: str = None,
    tenant_id: str = "",
    description: str = "",
) -> str:
    """
    Insert a new kanban task as in_progress.
    Returns the MongoDB _id string, or empty string on failure.
    """
    client, col = _get_col()
    if col is None:
        return ""
    try:
        now = datetime.now(timezone.utc)
        doc = {
            "title": title,
            "description": description or f"{source} task from {sender}",
            "status": "in_progress",
            "assignee": assignee or persona,
            "persona": persona,
            "tenant_id": tenant_id,
            "priority": priority,
            "tags": (tags or []) + [source, f"from:{sender}"],
            "metadata": {**(metadata or {}), "task_id": task_id, "sender": sender},
            "files": [],
            "parent_task_id": None,
            "child_task_ids": [],
            "last_activity_at": now,
            "rex_approved": False,
            "error_log": None,
            "stalled_at": None,
            "result_summary": "",
            "created_at": now,
            "updated_at": now,
        }
        result = col.insert_one(doc)
        kanban_id = str(result.inserted_id)
        log.info(f"Kanban task created: {kanban_id} (task={task_id} source={source})")
        return kanban_id
    except Exception as e:
        log.warning(f"Kanban create failed: {e}")
        return ""
    finally:
        try:
            client.close()
        except Exception:
            pass


def kanban_finish(kanban_id: str, success: bool, result_summary: str) -> None:
    """Update a kanban task to done or blocked."""
    if not kanban_id:
        return
    client, col = _get_col()
    if col is None:
        return
    try:
        now = datetime.now(timezone.utc)
        fields = {
            "status": "done" if success else "blocked",
            "result_summary": result_summary[:500],
            "last_activity_at": now,
            "updated_at": now,
        }
        if not success:
            fields["error_log"] = result_summary[:500]
        col.update_one({"_id": _oid(kanban_id)}, {"$set": fields})
        log.info(f"Kanban task {kanban_id} marked {'done' if success else 'blocked'}")
    except Exception as e:
        log.warning(f"Kanban finish failed: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass


def kanban_update(kanban_id: str, fields: dict) -> None:
    """Generic partial update on a kanban task."""
    if not kanban_id:
        return
    client, col = _get_col()
    if col is None:
        return
    try:
        now = datetime.now(timezone.utc)
        fields["updated_at"] = now
        fields["last_activity_at"] = now
        col.update_one({"_id": _oid(kanban_id)}, {"$set": fields})
    except Exception as e:
        log.warning(f"Kanban update failed: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass


def kanban_poll(
    assignee: str,
    tenant_id: str,
    status: str = "todo",
) -> list:
    """
    Return tasks assigned to a persona with the given status, sorted by priority.
    Used by persona HEARTBEAT.md to check for pending work.
    """
    client, col = _get_col()
    if col is None:
        return []
    try:
        cursor = col.find({
            "assignee": assignee,
            "tenant_id": tenant_id,
            "status": status,
        })
        tasks = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            tasks.append(doc)
        tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t.get("priority", "medium"), 1))
        return tasks
    except Exception as e:
        log.warning(f"Kanban poll failed: {e}")
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def kanban_add_file(
    kanban_id: str,
    path: str,
    label: str,
    file_type: str,
    added_by: str,
) -> None:
    """
    Append a file reference to a task's files[] array.
    file_type must be one of: input, output, reference.
    """
    if file_type not in _VALID_FILE_TYPES:
        raise ValueError(f"Invalid file type '{file_type}'. Must be one of: {_VALID_FILE_TYPES}")
    client, col = _get_col()
    if col is None:
        return
    try:
        now = datetime.now(timezone.utc)
        file_entry = {
            "path": path,
            "label": label,
            "type": file_type,
            "added_by": added_by,
            "added_at": now,
        }
        col.update_one(
            {"_id": _oid(kanban_id)},
            {"$push": {"files": file_entry}, "$set": {"last_activity_at": now, "updated_at": now}},
        )
        log.info(f"Kanban task {kanban_id}: added file {path} ({file_type})")
    except Exception as e:
        log.warning(f"Kanban add-file failed: {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass


def kanban_handoff(
    kanban_id: str,
    to: str,
    title: str,
    files: list,
    tenant_id: str,
) -> str:
    """
    Create a child task assigned to another persona.
    Copies listed file paths as 'input' files on the child task.
    Links parent → child and child → parent.
    Returns the new child task _id string.
    """
    client, col = _get_col()
    if col is None:
        return ""
    try:
        now = datetime.now(timezone.utc)
        input_files = [
            {"path": p, "label": p.split("/")[-1], "type": "input", "added_by": "handoff", "added_at": now}
            for p in (files or [])
        ]
        child_doc = {
            "title": title,
            "description": f"Handed off from task {kanban_id}",
            "status": "todo",
            "assignee": to,
            "tenant_id": tenant_id,
            "priority": "medium",
            "tags": ["handoff"],
            "files": input_files,
            "parent_task_id": kanban_id,
            "child_task_ids": [],
            "last_activity_at": now,
            "rex_approved": False,
            "error_log": None,
            "stalled_at": None,
            "result_summary": "",
            "created_at": now,
            "updated_at": now,
        }
        result = col.insert_one(child_doc)
        child_id = str(result.inserted_id)
        col.update_one(
            {"_id": _oid(kanban_id)},
            {"$push": {"child_task_ids": child_id}, "$set": {"last_activity_at": now, "updated_at": now}},
        )
        log.info(f"Kanban handoff: {kanban_id} → {child_id} (to={to})")
        return child_id
    except Exception as e:
        log.warning(f"Kanban handoff failed: {e}")
        return ""
    finally:
        try:
            client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI entrypoint — agents call this via exec
# ---------------------------------------------------------------------------

def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Kanban CLI for persona agents")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Create a new kanban task")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--description", default="")
    p_create.add_argument("--assignee", required=True)
    p_create.add_argument("--tenant-id", default="dev")
    p_create.add_argument("--priority", default="medium", choices=["high", "medium", "low"])
    p_create.add_argument("--tags", default="", help="Comma-separated tags")

    p_poll = sub.add_parser("poll", help="List tasks assigned to a persona")
    p_poll.add_argument("--assignee", required=True)
    p_poll.add_argument("--tenant-id", required=True)
    p_poll.add_argument("--status", default="todo")

    p_update = sub.add_parser("update", help="Update task fields")
    p_update.add_argument("task_id")
    p_update.add_argument("--status")
    p_update.add_argument("--rex-approved", action="store_true", default=None)

    p_add_file = sub.add_parser("add-file", help="Add a file reference to a task")
    p_add_file.add_argument("task_id")
    p_add_file.add_argument("--path", required=True)
    p_add_file.add_argument("--label", required=True)
    p_add_file.add_argument("--type", dest="file_type", required=True)
    p_add_file.add_argument("--added-by", required=True)

    p_handoff = sub.add_parser("handoff", help="Hand off task to another persona")
    p_handoff.add_argument("task_id")
    p_handoff.add_argument("--to", required=True)
    p_handoff.add_argument("--title", required=True)
    p_handoff.add_argument("--tenant-id", required=True)
    p_handoff.add_argument("--files", default="", help="Comma-separated file paths")

    p_finish = sub.add_parser("finish", help="Mark task done or blocked")
    p_finish.add_argument("task_id")
    p_finish.add_argument("--result", required=True)
    p_finish.add_argument("--failed", action="store_true")

    args = parser.parse_args()

    if args.cmd == "create":
        import uuid
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        task_id = str(uuid.uuid4())
        kanban_id = kanban_create(
            task_id=task_id,
            title=args.title,
            sender="agent",
            persona=args.assignee,
            assignee=args.assignee,
            tenant_id=args.tenant_id,
            priority=args.priority,
            description=args.description,
            tags=tags,
            source="cli",
        )
        print(json.dumps({"task_id": kanban_id}))

    elif args.cmd == "poll":
        tasks = kanban_poll(args.assignee, args.tenant_id, args.status)
        print(json.dumps(tasks, default=str))

    elif args.cmd == "update":
        fields = {}
        if args.status:
            fields["status"] = args.status
        if args.rex_approved:
            fields["rex_approved"] = True
        if fields:
            kanban_update(args.task_id, fields)
        print(json.dumps({"ok": True}))

    elif args.cmd == "add-file":
        kanban_add_file(args.task_id, args.path, args.label, args.file_type, args.added_by)
        print(json.dumps({"ok": True}))

    elif args.cmd == "handoff":
        files = [f.strip() for f in args.files.split(",") if f.strip()]
        child_id = kanban_handoff(args.task_id, args.to, args.title, files, args.tenant_id)
        print(json.dumps({"child_task_id": child_id}))

    elif args.cmd == "finish":
        kanban_finish(args.task_id, success=not args.failed, result_summary=args.result)
        print(json.dumps({"ok": True}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _cli()
