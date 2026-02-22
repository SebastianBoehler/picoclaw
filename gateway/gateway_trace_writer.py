#!/usr/bin/env python3
"""
gateway_trace_writer.py — Wraps `picoclaw gateway`, parses structured log output,
and writes per-message traces to the PostgreSQL traces DB.

Parses these log lines emitted by the Go gateway:
  [INFO] agent: Processing message from <channel>:<sender_id>: <preview> {chat_id=..., session_key=...}
  [INFO] agent: Response: <text> {session_key=..., iterations=N, final_length=N}
  [ERROR] agent: LLM call failed {error=...}
  WEAVE_TOOL_EVENT:<json>   (when PICOCLAW_WEAVE_OBSERVE=1)

Env vars:
  PICOCLAW_TRACES_DB_URL  — PostgreSQL connection string
  PICOCLAW_BIN            — path to picoclaw binary (default: picoclaw)
  PICOCLAW_PERSONA        — persona name for gateway label
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import uuid
import queue
import logging
import threading
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("trace-writer")

PICOCLAW_BIN        = os.environ.get("PICOCLAW_BIN", "picoclaw")
TRACES_DB_URL       = os.environ.get("PICOCLAW_TRACES_DB_URL", "")
PERSONA             = os.environ.get("PICOCLAW_PERSONA", "unknown")

# ── PostgreSQL helpers ────────────────────────────────────────────────────────

def _pg_connect():
    import psycopg2
    return psycopg2.connect(TRACES_DB_URL)


def _ensure_schema() -> None:
    if not TRACES_DB_URL:
        return
    # Step 1: create tables and basic indexes (fast, low contention)
    try:
        conn = _pg_connect()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                task_id     TEXT PRIMARY KEY,
                gateway     TEXT,
                sender      TEXT,
                preview     TEXT,
                exit_code   INTEGER,
                started_at  DOUBLE PRECISION NOT NULL,
                ended_at    DOUBLE PRECISION,
                duration_ms INTEGER,
                tool_count  INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                tools_json  TEXT DEFAULT '[]'
            )
        """)
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
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.warning(f"Schema table init failed: {e}")

    # Step 2: migration — add persona column (retry on deadlock since all containers start simultaneously)
    for attempt in range(4):
        try:
            conn = _pg_connect()
            cur  = conn.cursor()
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
            log.info("Traces schema ready")
            return
        except Exception as e:
            log.warning(f"Schema migration attempt {attempt+1} failed: {e}")
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            if attempt < 3:
                time.sleep(2 + attempt * 2)  # 2s, 4s, 6s backoff
    log.warning("Schema migration failed after retries — persona column may be missing")


# ── In-flight session tracking ────────────────────────────────────────────────

class Session:
    def __init__(self, task_id: str, sender: str, preview: str, gateway: str, started_at: float):
        self.task_id    = task_id
        self.sender     = sender
        self.preview    = preview
        self.gateway    = gateway
        self.started_at = started_at
        self.tools: list[dict] = []
        self.error_count = 0


# session_key → Session
_sessions: dict[str, Session] = {}
_sessions_lock = threading.Lock()

# Pending sessions: last seen Processing message not yet routed (no session_key yet)
# Only one pending slot needed — Processing + Routed are always consecutive lines
_pending_session: "Session | None" = None
_pending_lock = threading.Lock()

# background DB write queue
_db_queue: queue.Queue = queue.Queue()


def _db_worker() -> None:
    """Background thread: drains _db_queue and writes to PostgreSQL."""
    if not TRACES_DB_URL:
        return
    conn = None
    while True:
        item = _db_queue.get()
        if item is None:
            break
        try:
            if conn is None or conn.closed:
                conn = _pg_connect()
            kind = item["kind"]
            cur  = conn.cursor()
            if kind == "tool_event":
                cur.execute(
                    """INSERT INTO tool_events
                       (task_id, persona, tool, args_json, iteration, status, duration_ms, result_len, error, started_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (item["task_id"], item.get("persona") or None, item["tool"], item.get("args_json"),
                     item.get("iteration"), item["status"],
                     item.get("duration_ms"), item.get("result_len"),
                     item.get("error"), item["started_at"]),
                )
            elif kind == "tool_event_done":
                cur.execute(
                    """UPDATE tool_events SET status='done', duration_ms=%s
                       WHERE id = (
                           SELECT id FROM tool_events
                            WHERE task_id=%s AND tool=%s AND status='running'
                            ORDER BY id DESC LIMIT 1
                       )""",
                    (item["duration_ms"], item["task_id"], item["tool"]),
                )
            elif kind == "context_event":
                cur.execute(
                    """INSERT INTO tool_events
                       (task_id, persona, tool, args_json, iteration, status, duration_ms, result_len, error, started_at)
                       VALUES (%s,%s,'__context__',%s,%s,'done',0,0,NULL,%s)""",
                    (item["task_id"], item.get("persona") or None, item["args_json"], item.get("iteration"), item["started_at"]),
                )
            elif kind == "trace":
                cur.execute(
                    """INSERT INTO traces
                       (task_id, gateway, sender, preview, exit_code,
                        started_at, ended_at, duration_ms, tool_count, error_count, tools_json)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (task_id) DO UPDATE SET
                         ended_at    = EXCLUDED.ended_at,
                         duration_ms = EXCLUDED.duration_ms,
                         tool_count  = EXCLUDED.tool_count,
                         error_count = EXCLUDED.error_count,
                         tools_json  = EXCLUDED.tools_json,
                         exit_code   = EXCLUDED.exit_code""",
                    (item["task_id"], item["gateway"], item["sender"],
                     item["preview"], item["exit_code"],
                     item["started_at"], item["ended_at"],
                     item["duration_ms"], item["tool_count"],
                     item["error_count"], item["tools_json"]),
                )
            conn.commit()
            cur.close()
        except Exception as e:
            log.warning(f"DB write failed: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            conn = None
        finally:
            _db_queue.task_done()


# ── Log line parsers ──────────────────────────────────────────────────────────

# [INFO] agent: Processing message from telegram:sebastianboehler: hello {sender_id=..., session_key=, channel=telegram, chat_id=...}
_RE_MSG = re.compile(
    r'\[INFO\] agent: Processing message from (\S+):(\S+): (.*?) \{'
)

# [INFO] agent: Routed message {agent_id=main, session_key=agent:main:main, matched_by=default}
_RE_ROUTED = re.compile(
    r'\[INFO\] agent: Routed message \{.*?session_key=([^,}]+)'
)

# [INFO] agent: Response: <text>   (single-line: metadata on same line)
_RE_RESP_INLINE = re.compile(
    r'\[INFO\] agent: Response:.*\{.*?session_key=([^,}]+).*?iterations=(\d+)'
)

# [INFO] agent: Response: <text>   (first line of multi-line response — no metadata yet)
_RE_RESP_START = re.compile(r'\[INFO\] agent: Response:')

# Closing metadata line for a multi-line response (no [INFO] prefix, just the {...} block)
_RE_RESP_META = re.compile(
    r'\{.*?session_key=([^,}]+).*?iterations=(\d+)'
)

# [INFO] tool: Tool execution started {tool=web_search, args=map[query:foo]}
_RE_TOOL_START = re.compile(
    r'\[INFO\] tool: Tool execution started \{tool=([^,}]+)(?:.*?args=map\[([^\]]*)\])?'
)

# [INFO] tool: Tool execution completed {tool=web_search, duration_ms=123, result_length=456}
_RE_TOOL_DONE = re.compile(
    r'\[INFO\] tool: Tool execution completed \{.*?tool=([^,}]+).*?duration_ms=(\d+)'
)

# [ERROR] agent: LLM call failed {session_key=..., error=...}
_RE_ERR = re.compile(r'\[ERROR\] agent: LLM call failed \{.*?session_key=([^,}]*)')
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


# Tracks whether we are inside a multi-line Response block waiting for the metadata line
_in_response: bool = False


def _finish_session(session_key: str) -> None:
    with _sessions_lock:
        sess = _sessions.pop(session_key, None)
    if sess:
        ended_at = time.time()
        duration_ms = int((ended_at - sess.started_at) * 1000)
        _db_queue.put({
            "kind": "trace",
            "task_id": sess.task_id,
            "gateway": sess.gateway,
            "sender": sess.sender,
            "preview": sess.preview,
            "exit_code": 0,
            "started_at": sess.started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "tool_count": len(sess.tools),
            "error_count": sess.error_count,
            "tools_json": json.dumps(sess.tools),
        })
        log.info(f"Trace written: {sess.task_id} ({duration_ms}ms, {len(sess.tools)} tools)")


def _handle_line(line: str) -> None:
    global _in_response
    line = line.rstrip()

    # Structured context telemetry event from agent loop.
    context_event = _parse_context_event(line)
    if context_event is not None:
        session_key = str(context_event.get("session_key", "")).strip()
        with _sessions_lock:
            sess = _sessions.get(session_key) if session_key else None
            if not sess and _sessions:
                sess = max(_sessions.values(), key=lambda s: s.started_at)
            if sess:
                _db_queue.put({
                    "kind": "context_event",
                    "task_id": sess.task_id,
                    "persona": PERSONA,
                    "args_json": json.dumps(context_event),
                    "iteration": int(context_event.get("iteration", 0) or 0),
                    "started_at": time.time(),
                })
        return

    # Tool execution started — attach to active session + write to DB immediately
    m = _RE_TOOL_START.search(line)
    if m:
        tool_name = m.group(1).strip()
        args_raw  = m.group(2) or ""
        with _sessions_lock:
            # If no active session (e.g. heartbeat/cron fires before any message),
            # create an ephemeral session so the tool event is still recorded.
            if not _sessions:
                ephemeral_id = f"hb-{PERSONA}-{uuid.uuid4().hex[:8]}"
                # Key as 'heartbeat' so the 'Response: HEARTBEAT_OK {session_key=heartbeat}'
                # line correctly calls _finish_session('heartbeat') to close it.
                _sessions["heartbeat"] = Session(
                    task_id=ephemeral_id,
                    sender=PERSONA,
                    preview="(heartbeat)",
                    gateway="heartbeat",
                    started_at=time.time(),
                )
            sess = max(_sessions.values(), key=lambda s: s.started_at)
            ev = {
                "tool": tool_name,
                "args": args_raw,
                "duration_ms": None,
                "is_error": False,
                "error_msg": "",
            }
            sess.tools.append(ev)
            _db_queue.put({
                "kind": "tool_event",
                "task_id": sess.task_id,
                "persona": PERSONA,
                "tool": tool_name,
                "args_json": json.dumps({"args": args_raw}),
                "iteration": len(sess.tools),
                "status": "running",
                "duration_ms": None,
                "result_len": None,
                "error": None,
                "started_at": time.time(),
            })
        return

    # Tool execution completed — update in-memory entry + write done status to DB
    m = _RE_TOOL_DONE.search(line)
    if m:
        tool_name   = m.group(1).strip()
        duration_ms = int(m.group(2))
        with _sessions_lock:
            if _sessions:
                sess = max(_sessions.values(), key=lambda s: s.started_at)
                for ev in reversed(sess.tools):
                    if ev["tool"] == tool_name and ev["duration_ms"] is None:
                        ev["duration_ms"] = duration_ms
                        break
                _db_queue.put({
                    "kind": "tool_event_done",
                    "task_id": sess.task_id,
                    "tool": tool_name,
                    "duration_ms": duration_ms,
                })
        return

    # New incoming message → park as pending (session_key not assigned yet at this point)
    m = _RE_MSG.search(line)
    if m:
        global _pending_session
        channel, sender_id, preview = m.group(1), m.group(2), m.group(3)
        task_id = uuid.uuid4().hex[:12]
        gateway = "tg" if "telegram" in channel else channel.split(":")[0]
        sess = Session(
            task_id=task_id,
            sender=sender_id,
            preview=preview[:200],
            gateway=gateway,
            started_at=time.time(),
        )
        with _pending_lock:
            _pending_session = sess
        log.debug(f"Session pending: {task_id} sender={sender_id}")
        return

    # Routed message → promote pending session to active with real session_key
    m = _RE_ROUTED.search(line)
    if m:
        session_key = m.group(1).strip()
        with _pending_lock:
            sess = _pending_session
            _pending_session = None
        if session_key:
            with _sessions_lock:
                # Evict any stale ephemeral heartbeat session before starting a real one
                _sessions.pop("heartbeat", None)
                if sess:
                    _sessions[session_key] = sess
                    log.debug(f"Session start: {sess.task_id} key={session_key} sender={sess.sender}")
                elif session_key not in _sessions:
                    # Processing message was truncated — create a fallback session so
                    # _finish_session can still fire _notify_router for queue advancement
                    fallback = Session(
                        task_id=uuid.uuid4().hex[:12],
                        sender="router",
                        preview="(injected)",
                        gateway="tg" if session_key.startswith("tg:") else "inject",
                        started_at=time.time(),
                    )
                    _sessions[session_key] = fallback
                    log.debug(f"Session fallback: {fallback.task_id} key={session_key}")
        return

    # Response (single-line: metadata on same line as "Response:")
    m = _RE_RESP_INLINE.search(line)
    if m:
        _in_response = False
        session_key = m.group(1).strip()
        _finish_session(session_key)
        return

    # Response start (multi-line: message text spans multiple lines before metadata)
    if _RE_RESP_START.search(line):
        _in_response = True
        return

    # Closing metadata line of a multi-line Response block
    if _in_response:
        m = _RE_RESP_META.search(line)
        if m:
            _in_response = False
            session_key = m.group(1).strip()
            _finish_session(session_key)
            return
        # Any non-metadata line resets the flag only if it is a new structured log entry
        if re.search(r'\[(INFO|WARN|WARNING|ERROR|DEBUG)\]', line):
            _in_response = False

    # LLM error → mark session as errored
    m = _RE_ERR.search(line)
    if m:
        session_key = m.group(1).strip()
        with _sessions_lock:
            sess = _sessions.get(session_key)
            if sess:
                sess.error_count += 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TRACES_DB_URL:
        log.warning("PICOCLAW_TRACES_DB_URL not set — running gateway without trace writing")
        os.execvp(PICOCLAW_BIN, [PICOCLAW_BIN, "gateway"] + sys.argv[1:])
        return  # unreachable

    _ensure_schema()

    # Start DB worker thread
    db_thread = threading.Thread(target=_db_worker, daemon=True)
    db_thread.start()

    # Launch picoclaw gateway with PICOCLAW_WEAVE_OBSERVE=1
    env = os.environ.copy()
    env["PICOCLAW_WEAVE_OBSERVE"] = "1"

    proc = subprocess.Popen(
        [PICOCLAW_BIN, "gateway"] + sys.argv[1:],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout so we see everything
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            _handle_line(line)
    except KeyboardInterrupt:
        pass
    finally:
        proc.wait()
        _db_queue.put(None)  # signal worker to stop
        db_thread.join(timeout=5)

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
