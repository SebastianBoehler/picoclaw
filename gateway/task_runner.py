#!/usr/bin/env python3
"""
task_runner.py — Unified Picoclaw task container entry point.

Lives in the base picoclaw-agent image. All gateways spawn task containers
with:  command=["python3", "/home/picoclaw/task_runner.py"]

Reads the task file written by the gateway, applies persona, runs
`picoclaw agent -m <prompt>`, then sends the reply via the appropriate
channel (telegram / email / kanban-summary) based on env vars.

Required env vars (set by gateway before spawning):
  PICOCLAW_TASK_ID        — hex task ID
  PICOCLAW_TASK_MODE      — must be "1"

Channel selection:
  PICOCLAW_TG_CHAT_ID     — if set → send Telegram reply
  (not set)               — write reply to workspace/tasks/<task_id>_reply.md
                            (email gateway reaper reads and sends this)

Optional:
  PICOCLAW_PERSONA        — persona name (default: max)
  PICOCLAW_KANBAN_ID      — MongoDB kanban task _id to finish
  PICOCLAW_DEBUG          — "1" to enable --debug on picoclaw agent
  PICOCLAW_CONTAINER_START — float timestamp of container start
"""

import os
import sys
import json
import glob
import time
import shutil
import logging
import threading
import subprocess
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("task-runner")

# ── Config from env ────────────────────────────────────────────────────────────
PICOCLAW_BIN   = os.environ.get("PICOCLAW_BIN", "picoclaw")
PICOCLAW_DEBUG = os.environ.get("PICOCLAW_DEBUG", "").lower() in ("1", "true", "yes")
WORKSPACE      = os.path.expanduser("~/.picoclaw/workspace")

# Telegram
_TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TG_API_BASE  = f"https://api.telegram.org/bot{_TG_BOT_TOKEN}" if _TG_BOT_TOKEN else ""

# Runtime tracing is emitted directly by the Go agent to PostgreSQL.
# This task runner no longer parses logs or writes trace rows itself.


# ── Telegram helpers ───────────────────────────────────────────────────────────
def _tg_request(method: str, payload: dict) -> dict:
    if not _TG_API_BASE:
        return {}
    url  = f"{_TG_API_BASE}/{method}"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.error(f"Telegram {method} error: {e}")
        return {}


def _tg_send(chat_id: int, text: str) -> None:
    MAX = 4096
    for i in range(0, max(1, len(text)), MAX):
        chunk = text[i:i + MAX]
        result = _tg_request("sendMessage", {"chat_id": chat_id, "text": chunk})
        if not result.get("ok"):
            log.error(f"Telegram sendMessage failed: {result}")


def _tg_send_file(chat_id: int, path: str) -> None:
    import mimetypes
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    is_image = mime.startswith("image/")
    method   = "sendPhoto" if is_image else "sendDocument"
    field    = "photo"     if is_image else "document"
    import urllib.parse
    boundary = "----PicoTaskBoundary"
    with open(path, "rb") as fh:
        file_data = fh.read()
    filename = os.path.basename(path)
    body  = f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n"
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n"
    body_bytes = body.encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{_TG_API_BASE}/{method}",
        data=body_bytes,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                log.warning(f"Failed to send file {filename}: {result}")
    except Exception as e:
        log.warning(f"Failed to send file {filename}: {e}")


# ── Kanban helpers ──────────────────────────────────────────────────────────────
def _kanban_finish(kanban_id: str, success: bool, summary: str) -> None:
    if not kanban_id:
        return
    try:
        from kanban import kanban_finish
        kanban_finish(kanban_id, success, summary)
    except Exception as e:
        log.warning(f"kanban_finish failed: {e}")


def _tee_stderr(proc) -> None:
    """Read stderr and mirror agent logs. Runtime tracing is handled by Go."""
    for raw in iter(proc.stderr.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        log.info(f"[agent] {line}")


# ── Reply file helpers ─────────────────────────────────────────────────────────
def _read_task_reply(task_id: str) -> str:
    path = os.path.join(WORKSPACE, "tasks", f"{task_id}_reply.md")
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
            os.remove(path)
            return content
        except Exception:
            pass
    return ""


def _read_reply_file() -> str:
    path = os.path.join(WORKSPACE, "reply.md")
    if os.path.exists(path):
        try:
            with open(path) as f:
                content = f.read().strip()
            os.remove(path)
            return content
        except Exception:
            pass
    return ""


_NOISE_PREFIXES = (
    "WEAVE_TOOL_EVENT:",
    "🔍 Debug mode enabled",
    "\U0001f50d Debug mode enabled",
    "Using custom deny patterns:",
    "Using custom allow patterns:",
    "[DEBUG]",
    "[TRACE]",
    "time=",
    "level=",
)

# Substrings that indicate injected system/runtime messages — never send these to users.
_NOISE_SUBSTRINGS = (
    "Memory threshold reached",
    "Optimizing conversation history",
    "ephemeral_message",
    "CHECKPOINT",
    "{{ CHECKPOINT",
    "No MEMORIES were retrieved",
    "System-retrieved memories",
    "SYSTEM-RETRIEVED-MEMORY",
    "automatically retrieved from previous conversations",
    "this summary is just for your reference",
    "DO NOT ACKNOWLEDGE THIS CHECKPOINT",
    "injected by the system",
)

def _clean_output(text: str) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        if any(line.startswith(p) for p in _NOISE_PREFIXES):
            continue
        if any(s in line for s in _NOISE_SUBSTRINGS):
            continue
        out.append(line)
    return "\n".join(out).strip()


# ── Persona setup ──────────────────────────────────────────────────────────────
def _apply_persona(task_id: str) -> None:
    persona     = os.environ.get("PICOCLAW_PERSONA", "max")
    personas_dir = "/home/picoclaw/personas"
    identity_dst = os.path.join(WORKSPACE, "IDENTITY.md")
    persona_src  = os.path.join(personas_dir, persona, "IDENTITY.md")
    if persona != "max" and os.path.exists(persona_src):
        try:
            shutil.copy2(persona_src, identity_dst)
            log.info(f"Persona set to '{persona}' for task {task_id}")
        except Exception as e:
            log.warning(f"Could not set persona '{persona}': {e}")


# ── Task cleanup ───────────────────────────────────────────────────────────────
def _cleanup_task(task_id: str) -> None:
    # Remove tmp scratch dir for this task
    tmp_dir = os.path.join(WORKSPACE, "tasks", task_id, "tmp")
    if os.path.isdir(tmp_dir):
        try:
            shutil.rmtree(tmp_dir)
            log.info(f"Deleted tmp dir for task {task_id}")
        except Exception as e:
            log.warning(f"Could not delete tmp dir: {e}")
    # Remove plan.md for this task
    plan_file = os.path.join(WORKSPACE, "tasks", task_id, "plan.md")
    if os.path.exists(plan_file):
        try:
            os.remove(plan_file)
            log.info(f"Deleted plan file for task {task_id}")
        except Exception:
            pass
    # Also clean up any legacy plans/ dir files from older agents
    plans_dir = os.path.join(WORKSPACE, "plans")
    if os.path.isdir(plans_dir):
        for f in glob.glob(os.path.join(plans_dir, "*.md")):
            try:
                os.remove(f)
            except Exception:
                pass


# ── Main task runner ───────────────────────────────────────────────────────────
def run(task_id: str) -> None:
    task_file = os.path.join(WORKSPACE, "tasks", f"{task_id}.json")

    log.info(f"Task runner: loading task {task_id}")
    if not os.path.exists(task_file):
        log.error(f"Task file not found: {task_file}")
        sys.exit(1)

    with open(task_file) as f:
        task = json.load(f)

    full_prompt = task["prompt"]
    sender      = task.get("sender", "")
    kanban_id   = task.get("kanban_id", "") or os.environ.get("PICOCLAW_KANBAN_ID", "")

    # Channel-specific fields
    tg_chat_id  = int(task.get("chat_id", 0)) or int(os.environ.get("PICOCLAW_TG_CHAT_ID", "0"))
    preview     = task.get("message_preview", task.get("subject", ""))[:100]

    # Delete task file before agent runs — agent must not see other tasks' files
    try:
        os.remove(task_file)
        log.info(f"Deleted task file: {task_id}.json")
    except Exception as e:
        log.warning(f"Could not delete task file: {e}")

    # Clear stale session history to avoid context poisoning across tasks
    session_file = os.path.join(WORKSPACE, "sessions", "agent_main_main.json")
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
            log.info(f"Cleared stale session for task {task_id}")
        except Exception as e:
            log.warning(f"Could not clear session: {e}")

    # GitHub App token
    try:
        from gh_auth import init_gh_token
        init_gh_token(start_refresh_thread=False)
    except Exception as e:
        log.warning(f"gh_auth init failed: {e}")

    # Apply persona (copies IDENTITY.md before agent starts)
    _apply_persona(task_id)

    # Private scratch space for this task
    private_dir = os.path.join(WORKSPACE, "tasks", task_id)
    os.makedirs(private_dir, exist_ok=True)

    # Clear stale reply.md
    reply_md = os.path.join(WORKSPACE, "reply.md")
    if os.path.exists(reply_md):
        try:
            os.remove(reply_md)
        except Exception:
            pass

    # ── Run picoclaw agent ─────────────────────────────────────────────────────
    cmd = [PICOCLAW_BIN, "agent"]
    if PICOCLAW_DEBUG:
        cmd.append("--debug")
    cmd += ["-m", full_prompt]

    log.info(f"Running: {' '.join(cmd[:3])} -m <{len(full_prompt)} chars>")

    stdout_chunks: list = []

    def _tee_stdout(p, chunks):
        for line in iter(p.stdout.readline, b""):
            chunks.append(line)

    started_at = time.time()
    env = os.environ.copy()
    env["PICOCLAW_TRACE_SENDER"] = str(sender or "")
    env["PICOCLAW_TRACE_SUBJECT"] = str(preview or "")[:200]
    if tg_chat_id:
        env["PICOCLAW_TRACE_GATEWAY"] = "tg"
    elif os.environ.get("PICOCLAW_TASK_TO"):
        env["PICOCLAW_TRACE_GATEWAY"] = "email"
    else:
        env["PICOCLAW_TRACE_GATEWAY"] = "kanban"

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    t_err = threading.Thread(target=_tee_stderr, args=(proc,), daemon=True)
    t_out = threading.Thread(target=_tee_stdout, args=(proc, stdout_chunks), daemon=True)
    t_err.start()
    t_out.start()
    proc.wait()
    t_err.join(timeout=5)
    t_out.join(timeout=5)
    ended_at   = time.time()
    try:
        # ── Read reply ─────────────────────────────────────────────────────────
        reply = _clean_output(_read_task_reply(task_id) or _read_reply_file())
        if not reply:
            raw = b"".join(stdout_chunks).decode("utf-8", errors="replace")
            reply = _clean_output(raw)
        if not reply or reply.strip() == "I've completed processing but have no response to give.":
            reply = f"✅ Task done (exit {proc.returncode}) — no reply written."

        success        = proc.returncode == 0
        result_summary = reply[:200].strip()

        _kanban_finish(kanban_id, success, result_summary)

        # ── Send reply via appropriate channel ─────────────────────────────────
        if tg_chat_id:
            _tg_send(tg_chat_id, reply)
            log.info(f"Telegram reply sent to chat_id={tg_chat_id} for task {task_id}")
            # Send any files the agent dropped into reply-files/<task_id>/
            reply_files_dir = os.path.join(WORKSPACE, "reply-files", task_id)
            if os.path.isdir(reply_files_dir):
                for fpath in sorted(glob.glob(os.path.join(reply_files_dir, "*"))):
                    if os.path.isfile(fpath):
                        _tg_send_file(tg_chat_id, fpath)
                        log.info(f"Sent file: {os.path.basename(fpath)}")

        else:
            # No channel configured — write to reply.md as fallback
            out_path = os.path.join(WORKSPACE, "tasks", f"{task_id}_reply.md")
            with open(out_path, "w") as f:
                f.write(reply)
            log.info(f"No channel configured — reply written to {out_path}")

    finally:
        _cleanup_task(task_id)


if __name__ == "__main__":
    task_id = os.environ.get("PICOCLAW_TASK_ID", "")
    if not task_id:
        log.error("PICOCLAW_TASK_ID not set")
        sys.exit(1)
    run(task_id)
