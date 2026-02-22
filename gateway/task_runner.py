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
  PICOCLAW_WEAVE_OBSERVE  — "1" to emit WEAVE_TOOL_EVENT lines
  PICOCLAW_TRACES_DB_URL  — PostgreSQL URL for trace recording
  PICOCLAW_CONTAINER_START — float timestamp of container start
"""

import os
import sys
import re
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

# Traces DB
_TRACES_DB_URL = os.environ.get("PICOCLAW_TRACES_DB_URL", "")

# Non-blocking tool_events writer
_TOOL_EVENT_QUEUE: "queue.Queue | None" = None


def _pg_connect():
    import psycopg2
    return psycopg2.connect(_TRACES_DB_URL)


def _init_tool_events_table() -> None:
    """Create tool_events table and start background writer thread."""
    global _TOOL_EVENT_QUEUE
    if not _TRACES_DB_URL:
        return
    try:
        import queue
        conn = _pg_connect()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tool_events (
                id          BIGSERIAL PRIMARY KEY,
                task_id     TEXT NOT NULL,
                persona     TEXT,
                tool        TEXT NOT NULL,
                args_json   TEXT,
                iteration   INTEGER,
                status      TEXT NOT NULL DEFAULT 'running',
                duration_ms INTEGER,
                result_len  INTEGER,
                error       TEXT,
                started_at  DOUBLE PRECISION NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_task_id ON tool_events (task_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_started_at ON tool_events (started_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_persona ON tool_events (persona)")
        # Add persona column if table already exists without it
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE tool_events ADD COLUMN IF NOT EXISTS persona TEXT;
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$;
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_persona ON tool_events (persona) WHERE persona IS NOT NULL")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.warning(f"tool_events table init failed: {e}")
        return

    _TOOL_EVENT_QUEUE = queue.Queue(maxsize=1000)

    def _writer():
        while True:
            op = _TOOL_EVENT_QUEUE.get()
            if op is None:
                break
            try:
                conn = _pg_connect()
                cur  = conn.cursor()
                if op["action"] == "start":
                    cur.execute("""
                        INSERT INTO tool_events
                          (task_id, persona, tool, args_json, iteration, status, started_at)
                        VALUES (%s, %s, %s, %s, %s, 'running', %s)
                        RETURNING id
                    """, (op["task_id"], op.get("persona") or None, op["tool"], op["args_json"], op["iteration"], op["started_at"]))
                    row = cur.fetchone()
                    if row:
                        op["id_box"].append(row[0])
                elif op["action"] == "done" and op.get("row_id"):
                    cur.execute("""
                        UPDATE tool_events
                           SET status='done', duration_ms=%s, result_len=%s
                         WHERE id=%s
                    """, (op["duration_ms"], op["result_len"], op["row_id"]))
                elif op["action"] == "error" and op.get("row_id"):
                    cur.execute("""
                        UPDATE tool_events
                           SET status='error', duration_ms=%s, error=%s
                         WHERE id=%s
                    """, (op["duration_ms"], op["error"], op["row_id"]))
                elif op["action"] == "context":
                    cur.execute("""
                        INSERT INTO tool_events
                          (task_id, persona, tool, args_json, iteration, status, duration_ms, result_len, started_at)
                        VALUES (%s, %s, '__context__', %s, %s, 'done', 0, 0, %s)
                    """, (op["task_id"], op.get("persona") or None, op["args_json"], op["iteration"], op["started_at"]))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                log.warning(f"tool_events write failed: {e}")

    threading.Thread(target=_writer, daemon=True).start()
    log.info("tool_events realtime writer started")


def _emit_tool_start(task_id: str, tool: str, args: dict, iteration: int, persona: str = "") -> list:
    """Enqueue a tool start event. Returns an id_box list that will be populated with the DB row id."""
    id_box: list = []
    if _TOOL_EVENT_QUEUE is None:
        return id_box
    try:
        _TOOL_EVENT_QUEUE.put_nowait({
            "action":     "start",
            "task_id":    task_id,
            "persona":    persona or os.environ.get("PICOCLAW_PERSONA", ""),
            "tool":       tool,
            "args_json":  json.dumps(args),
            "iteration":  iteration,
            "started_at": time.time(),
            "id_box":     id_box,
        })
    except Exception:
        pass
    return id_box


def _emit_tool_done(id_box: list, duration_ms: int, result_len: int) -> None:
    if _TOOL_EVENT_QUEUE is None or not id_box:
        return
    # id_box is populated asynchronously — spin-wait up to 2s
    deadline = time.time() + 2.0
    while not id_box and time.time() < deadline:
        time.sleep(0.05)
    if not id_box:
        return
    try:
        _TOOL_EVENT_QUEUE.put_nowait({
            "action":      "done",
            "row_id":      id_box[0],
            "duration_ms": duration_ms,
            "result_len":  result_len,
        })
    except Exception:
        pass


def _emit_tool_error(id_box: list, duration_ms: int, error: str) -> None:
    if _TOOL_EVENT_QUEUE is None or not id_box:
        return
    deadline = time.time() + 2.0
    while not id_box and time.time() < deadline:
        time.sleep(0.05)
    if not id_box:
        return
    try:
        _TOOL_EVENT_QUEUE.put_nowait({
            "action":      "error",
            "row_id":      id_box[0],
            "duration_ms": duration_ms,
            "error":       error,
        })
    except Exception:
        pass


def _emit_context_event(task_id: str, event: dict) -> None:
    if _TOOL_EVENT_QUEUE is None:
        return
    try:
        _TOOL_EVENT_QUEUE.put_nowait({
            "action":     "context",
            "task_id":    task_id,
            "persona":    os.environ.get("PICOCLAW_PERSONA", ""),
            "args_json":  json.dumps(event),
            "iteration":  int(event.get("iteration", 0) or 0),
            "started_at": time.time(),
        })
    except Exception:
        pass


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


# ── Trace helpers ──────────────────────────────────────────────────────────────
# Patterns emitted by picoclaw --debug:
#   agent: Tool call: write_file({"path":...}) {agent_id=main, tool=write_file, iteration=1}
#   tool: Tool execution completed {tool=write_file, duration_ms=0, result_length=95}
_TOOL_CALL_RE = re.compile(
    r'agent: Tool call: (\w+)\((.*)?\) \{.*?iteration=(\d+)\}'
)
_TOOL_DONE_RE = re.compile(
    r'tool: Tool execution completed \{tool=(\w+), duration_ms=(\d+), result_length=(\d+)'
)
_TOOL_ERROR_RE = re.compile(
    r'tool: Tool execution failed \{tool=(\w+), duration_ms=(\d+), error=(.+?)\}'
)
_CONTEXT_EVENT_MARKER = "CONTEXT_EVENT:"


def _parse_context_event(line: str) -> dict | None:
    if _CONTEXT_EVENT_MARKER not in line:
        return None
    payload = line.split(_CONTEXT_EVENT_MARKER, 1)[1].strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _tee_stderr(proc, result_box: list, task_id: str = "") -> None:
    """Read stderr, log it, and extract tool call events from picoclaw debug lines."""
    tool_events = []
    pending: dict = {}  # tool_name -> deque[{ev, id_box}]  (FIFO per tool name)

    for raw in iter(proc.stderr.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        log.info(f"[agent] {line}")

        # Parse structured context telemetry events.
        context_event = _parse_context_event(line)
        if context_event is not None and task_id:
            _emit_context_event(task_id, context_event)
            continue

        # Parse "Tool call: name(args) {... iteration=N}"
        m = _TOOL_CALL_RE.search(line)
        if m:
            tool_name = m.group(1)
            args_raw  = m.group(2) or ""
            iteration = int(m.group(3))
            try:
                args = json.loads(args_raw) if args_raw.endswith("}") else {"cmd": args_raw}
            except Exception:
                args = {"cmd": args_raw}
            ev = {
                "tool":      tool_name,
                "args":      args,
                "iteration": iteration,
                "is_error":  False,
            }
            id_box = _emit_tool_start(task_id, tool_name, args, iteration)
            if tool_name not in pending:
                pending[tool_name] = []
            pending[tool_name].append({"ev": ev, "id_box": id_box})
            continue

        # Parse "Tool execution completed {tool=..., duration_ms=..., result_length=...}"
        m = _TOOL_DONE_RE.search(line)
        if m:
            tool_name   = m.group(1)
            duration_ms = int(m.group(2))
            result_len  = int(m.group(3))
            queue = pending.get(tool_name)
            entry = queue.pop(0) if queue else None
            if queue is not None and not queue:
                del pending[tool_name]
            ev    = entry["ev"] if entry else {"tool": tool_name, "is_error": False}
            ev["duration_ms"]   = duration_ms
            ev["result_length"] = result_len
            tool_events.append(ev)
            if entry:
                threading.Thread(
                    target=_emit_tool_done,
                    args=(entry["id_box"], duration_ms, result_len),
                    daemon=True,
                ).start()
            continue

        # Parse "Tool execution failed {tool=..., duration_ms=..., error=...}"
        m = _TOOL_ERROR_RE.search(line)
        if m:
            tool_name   = m.group(1)
            duration_ms = int(m.group(2))
            error_msg   = m.group(3).strip()
            queue = pending.get(tool_name)
            entry = queue.pop(0) if queue else None
            if queue is not None and not queue:
                del pending[tool_name]
            ev    = entry["ev"] if entry else {"tool": tool_name}
            ev["duration_ms"] = duration_ms
            ev["error"]       = error_msg
            ev["is_error"]    = True
            tool_events.append(ev)
            if entry:
                threading.Thread(
                    target=_emit_tool_error,
                    args=(entry["id_box"], duration_ms, error_msg),
                    daemon=True,
                ).start()
            continue

    # Flush any pending calls that never got a completion line (e.g. agent killed)
    for queue in pending.values():
        for entry in queue:
            ev = entry["ev"]
            ev["is_error"] = True
            ev["error"]    = "no completion line (agent may have been killed)"
            tool_events.append(ev)
            threading.Thread(
                target=_emit_tool_error,
                args=(entry["id_box"], 0, "no completion line"),
                daemon=True,
            ).start()

    result_box.append(tool_events)


def _record_trace(task_id: str, sender: str, subject: str, tool_events: list,
                  exit_code: int, started_at: float, ended_at: float) -> None:
    if not _TRACES_DB_URL:
        return
    # Detect gateway from env — tg_chat_id set means Telegram, task_to means email, else kanban
    if os.environ.get("PICOCLAW_TG_CHAT_ID"):
        gateway = "tg"
    elif os.environ.get("PICOCLAW_TASK_TO"):
        gateway = "email"
    else:
        gateway = "kanban"
    try:
        import psycopg2
        conn = psycopg2.connect(_TRACES_DB_URL)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO traces
              (task_id, gateway, sender, preview, exit_code, started_at, ended_at,
               duration_ms, tool_count, error_count, tools_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                exit_code=EXCLUDED.exit_code, ended_at=EXCLUDED.ended_at,
                duration_ms=EXCLUDED.duration_ms, tool_count=EXCLUDED.tool_count,
                error_count=EXCLUDED.error_count, tools_json=EXCLUDED.tools_json
        """, (
            task_id, gateway, sender, subject[:200],
            exit_code, started_at, ended_at,
            round((ended_at - started_at) * 1000),
            len(tool_events),
            sum(1 for e in tool_events if e.get("is_error")),
            json.dumps(tool_events),
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.warning(f"Trace record failed: {e}")


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

    result_box:    list = []
    stdout_chunks: list = []
    container_start = float(os.environ.get("PICOCLAW_CONTAINER_START", str(time.time())))

    _init_tool_events_table()

    def _tee_stdout(p, chunks):
        for line in iter(p.stdout.readline, b""):
            chunks.append(line)

    started_at = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ.copy())
    t_err = threading.Thread(target=_tee_stderr, args=(proc, result_box, task_id), daemon=True)
    t_out = threading.Thread(target=_tee_stdout, args=(proc, stdout_chunks), daemon=True)
    t_err.start()
    t_out.start()
    proc.wait()
    t_err.join(timeout=5)
    t_out.join(timeout=5)
    ended_at   = time.time()
    tool_events = result_box[0] if result_box else []

    _record_trace(task_id, sender, preview, tool_events, proc.returncode, started_at, ended_at)

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
