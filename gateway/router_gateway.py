#!/usr/bin/env python3
"""
router_gateway.py — Group chat message router for Picoclaw personas.

Polls a Telegram group chat with its own bot token. For each user message,
calls an LLM to pick exactly ONE persona (alex/mia/ops/rex) or "silent".
Injects the message directly into that persona's picoclaw /inject endpoint,
passing a stable session_key so each persona accumulates history per user.

Redis stores a rolling context window (last N message pairs) per user+chat,
used to make context-aware routing decisions (e.g. follow-up messages stay
with the same persona unless clearly off-topic).

Required env vars:
  ROUTER_BOT_TOKEN      — Bot token for the router bot (must be in the group)
  OPENROUTER_API_KEY    — For LLM routing decisions
  TELEGRAM_USER_ID      — Numeric Telegram user ID of the human (to filter messages)

Optional:
  ROUTER_MODEL          — OpenRouter model (default: x-ai/grok-4-fast)
  POLL_TIMEOUT          — Long-poll timeout seconds (default: 30)
  ROUTER_GROUP_CHAT_ID  — Only process messages from this group chat ID
  REDIS_URL             — Redis connection URL (default: redis://picoclaw-redis:6379)
  CONTEXT_WINDOW_SIZE   — Number of message pairs to keep per user (default: 10)
  CONTEXT_TTL_SECONDS   — TTL for context keys in Redis (default: 3600)
"""

from __future__ import annotations

import os
import json
import time
import logging
import tempfile
import re
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("router")

# ── Config ────────────────────────────────────────────────────────────────────
ROUTER_BOT_TOKEN    = os.environ["ROUTER_BOT_TOKEN"]
OPENROUTER_API_KEY  = os.environ.get("OPENROUTER_API_KEY", "")
TELEGRAM_USER_ID    = int(os.environ.get("TELEGRAM_USER_ID") or "0")
ROUTER_MODEL        = os.environ.get("ROUTER_MODEL", "x-ai/grok-4-fast")
POLL_TIMEOUT        = int(os.environ.get("POLL_TIMEOUT", "30"))
ONLY_GROUP_ID       = os.environ.get("ROUTER_GROUP_CHAT_ID", "")
REDIS_URL           = os.environ.get("REDIS_URL", "redis://picoclaw-redis:6379")
CONTEXT_WINDOW_SIZE = int(os.environ.get("CONTEXT_WINDOW_SIZE", "10"))
CONTEXT_TTL         = int(os.environ.get("CONTEXT_TTL_SECONDS", "3600"))

# Internal port all persona gateways listen on (always 18790 inside the container)
_PERSONA_INTERNAL_PORT = 18790

PERSONA_HOST = os.environ.get("PERSONA_HOST", "host.docker.internal")

PERSONA_PORTS: dict[str, int] = {
    "alex": int(os.environ.get("PORT_ALEX", "18790")),
    "mia":  int(os.environ.get("PORT_MIA",  "18791")),
    "ops":  int(os.environ.get("PORT_OPS",  "18792")),
    "rex":  int(os.environ.get("PORT_REX",  "18793")),
}

_API = f"https://api.telegram.org/bot{ROUTER_BOT_TOKEN}"

# ── Persona capability map ────────────────────────────────────────────────────
PERSONAS = {
    "alex": "research, web search, market analysis, competitive intelligence, finding information, data gathering",
    "mia":  "writing, editing, content creation, drafting documents, reports, social posts, emails, sending files, delivering content to the user",
    "ops":  "code, infrastructure, GitHub, deployments, debugging, automation, shell scripts, Docker, CI/CD, technical execution, running commands",
    "rex":  "reviewing plans, critiquing proposals, strategic input, spotting risks, breaking down complex tasks — Rex does NOT execute",
}

ROUTER_SYSTEM = """You are a routing coordinator for a team of 4 AI personas in a group chat.
Given the user's message and recent context, decide:
1. Who should EXECUTE the task (one persona)
2. Which other personas should briefly DISCUSS it first (0-3 personas)

Personas:
- alex: {alex}
- mia:  {mia}
- ops:  {ops}
- rex:  {rex}

Execution rules:
- "send me X", "email me", "forward", "deliver" → executor: mia
- "write", "draft", "create document/post/report" → executor: mia
- "research", "find out", "look up", "search" → executor: alex
- "code", "deploy", "debug", "run", "script", "github" → executor: ops
- "review this plan", "critique", "approve" → executor: rex
- Casual greetings or small talk → executor: mia, no discussants
- Short follow-ups ("ok", "do it", "yes", "continue", "thanks") → executor: last_persona, no discussants
- If the message is clearly from an agent/bot → executor: silent

Discussion rules (who adds value before execution):
- Complex tasks or plans → include rex (critique) + relevant domain persona
- Technical tasks → include rex (risk check), alex (research angle) if relevant
- Content/writing tasks → include rex (quality bar), ops only if technical delivery needed
- Simple/quick tasks → 0-1 discussants max
- Never include the executor as a discussant
- Never add discussants for casual chat, simple follow-ups, or bot messages

Respond with JSON only, no markdown:
{{"executor": "ops", "discussants": ["rex", "alex"]}}
or for simple tasks:
{{"executor": "mia", "discussants": []}}
""".format(**PERSONAS)

# Per-persona discussion prompt templates — injected BEFORE the executor runs
DISCUSSION_PROMPTS = {
    "alex": (
        'The user just asked: "{message}"\n\n'
        "Before {executor} handles this, share a quick research angle or relevant context "
        "the team should know. Be brief (2-4 sentences). No need to execute anything."
    ),
    "mia": (
        'The user just asked: "{message}"\n\n'
        "Before {executor} handles this, share how you'd frame the output or delivery "
        "for the user. Be brief (2-4 sentences). No need to execute anything."
    ),
    "ops": (
        'The user just asked: "{message}"\n\n'
        "Before {executor} handles this, flag any technical considerations, risks, or "
        "infrastructure details the team should factor in. Be brief (2-4 sentences). No execution yet."
    ),
    "rex": (
        'The user just asked: "{message}"\n\n'
        "Before {executor} handles this, give your strategic take: what's the plan, "
        "what are the risks, what should {executor} watch out for? Be direct and brief (3-5 sentences)."
    ),
}

# Executor prompt prefix — injected AFTER discussants have weighed in (only when there were discussants)
EXECUTOR_PROMPT_WITH_DISCUSSION = (
    "The team has shared their perspectives above. Now it's your turn to execute.\n\n"
    "User request: {message}\n\n"
    "Go ahead and handle this fully."
)


# ── Redis context store ───────────────────────────────────────────────────────
_redis = None

def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as redis_lib
        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)
        _redis.ping()
        log.info(f"Redis connected: {REDIS_URL}")
    except Exception as e:
        log.warning(f"Redis unavailable ({e}) — context window disabled")
        _redis = None
    return _redis


def _ctx_key(chat_id: str, sender_id: str) -> str:
    return f"picoclaw:router:ctx:{chat_id}:{sender_id}"


def _last_persona_key(chat_id: str, sender_id: str) -> str:
    return f"picoclaw:router:last_persona:{chat_id}:{sender_id}"


def get_context(chat_id: str, sender_id: str) -> list[dict]:
    """Return rolling context as list of {role, content} dicts."""
    r = _get_redis()
    if r is None:
        return []
    try:
        raw = r.lrange(_ctx_key(chat_id, sender_id), 0, -1)
        return [json.loads(m) for m in raw]
    except Exception as e:
        log.warning(f"Redis get_context failed: {e}")
        return []


def push_context(chat_id: str, sender_id: str, role: str, content: str) -> None:
    """Append a message to the rolling context, trim to window size, reset TTL."""
    r = _get_redis()
    if r is None:
        return
    try:
        key = _ctx_key(chat_id, sender_id)
        r.rpush(key, json.dumps({"role": role, "content": content}))
        # Keep only last CONTEXT_WINDOW_SIZE * 2 entries (user + assistant pairs)
        r.ltrim(key, -(CONTEXT_WINDOW_SIZE * 2), -1)
        r.expire(key, CONTEXT_TTL)
    except Exception as e:
        log.warning(f"Redis push_context failed: {e}")


def get_last_persona(chat_id: str, sender_id: str) -> str | None:
    r = _get_redis()
    if r is None:
        return None
    try:
        return r.get(_last_persona_key(chat_id, sender_id))
    except Exception:
        return None


def set_last_persona(chat_id: str, sender_id: str, persona: str) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.set(_last_persona_key(chat_id, sender_id), persona, ex=CONTEXT_TTL)
    except Exception:
        pass


# ── Telegram helpers ──────────────────────────────────────────────────────────
def _tg(method: str, payload: dict) -> dict:
    url = f"{_API}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.error(f"TG {method} HTTP {e.code}: {e.read().decode()[:200]}")
        return {}
    except Exception as e:
        log.error(f"TG {method} error: {e}")
        return {}


def get_updates(offset: int) -> list:
    r = _tg("getUpdates", {"offset": offset, "timeout": POLL_TIMEOUT})
    return r.get("result", [])


# ── LLM routing ───────────────────────────────────────────────────────────────
_SHORT_FOLLOWUPS = {"ok", "yes", "no", "do it", "continue", "go ahead", "thanks", "great", "sure", "please", "k"}


def extract_explicit_personas(message: str) -> list[str]:
    """
    Detect explicit persona addressing in user text.
    Matches standalone tokens like "alex", "@alex", "alex," etc.
    Returns unique personas in order of first appearance.
    """
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"(?<![A-Za-z0-9_])@?(alex|mia|ops|rex)(?![A-Za-z0-9_])", message, flags=re.IGNORECASE):
        p = m.group(1).lower()
        if p not in seen:
            found.append(p)
            seen.add(p)
    return found

def pick_routing(message: str, chat_id: str, sender_id: str) -> tuple[str, list[str]]:
    """
    Returns (executor, discussants).
    executor: persona name or 'silent'
    discussants: list of persona names who should briefly weigh in first
    """
    if not OPENROUTER_API_KEY:
        log.warning("No OPENROUTER_API_KEY — defaulting to mia, no discussants")
        return "mia", []

    last = get_last_persona(chat_id, sender_id)

    # Sticky routing for short follow-ups — no discussion, just execute
    if last and message.lower().strip().rstrip("!.") in _SHORT_FOLLOWUPS:
        log.info(f"Short follow-up → sticky to {last}, no discussion")
        return last, []

    # Build context-aware prompt
    context = get_context(chat_id, sender_id)
    messages: list[dict] = [{"role": "system", "content": ROUTER_SYSTEM}]

    if context:
        ctx_lines = "\n".join(
            f"  [{m['role']}]: {m['content'][:120]}" for m in context[-6:]
        )
        messages.append({
            "role": "system",
            "content": f"Recent conversation context:\n{ctx_lines}" +
                       (f"\nLast persona used: {last}" if last else ""),
        })

    messages.append({"role": "user", "content": message})

    payload = json.dumps({
        "model": ROUTER_MODEL,
        "messages": messages,
        "max_tokens": 64,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            raw = data["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            executor = result.get("executor", "silent").lower()
            discussants = [p for p in result.get("discussants", []) if p in PERSONAS and p != executor]
            if executor not in PERSONAS and executor != "silent":
                log.warning(f"Unknown executor '{executor}' — defaulting to {last or 'mia'}")
                executor = last or "mia"
            return executor, discussants
    except Exception as e:
        log.error(f"Router LLM failed: {e} — defaulting to {last or 'mia'}, no discussants")
        return last or "mia", []


# ── HTTP inject to persona gateway ───────────────────────────────────────────
def inject_message(persona: str, sender_id: str, chat_id: str, content: str, session_key: str) -> bool:
    """POST message directly to persona's picoclaw /inject endpoint."""
    if PERSONA_HOST == "host.docker.internal":
        url = f"http://picoclaw-{persona}:{_PERSONA_INTERNAL_PORT}/inject"
    else:
        port = PERSONA_PORTS.get(persona)
        if not port:
            log.error(f"No port configured for persona: {persona}")
            return False
        url = f"http://{PERSONA_HOST}:{port}/inject"

    payload = json.dumps({
        "sender_id":   sender_id,
        "chat_id":     chat_id,
        "content":     content,
        "channel":     "telegram",
        "session_key": session_key,
    }).encode()

    for attempt in range(3):
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                log.info(f"Injected to {persona} ({url}): HTTP {resp.status}")
                return True
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                log.warning(f"Inject to {persona} failed (attempt {attempt+1}/3): {e} — retrying in {wait}s")
                time.sleep(wait)
            else:
                log.error(f"Inject to {persona} failed: {e}")
    return False


# ── Discussion queue (Redis) ─────────────────────────────────────────────────
# Stores per-chat: remaining pipeline [next_persona, ..., executor] + original message.
# Persona bot IDs are discovered at startup via getMe on each persona's token.
# When a persona bot posts in the group, the router pops the next item and injects it.

def _q_pipeline_key(chat_id: str) -> str:
    return f"picoclaw:router:queue:{chat_id}"

def _q_meta_key(chat_id: str) -> str:
    return f"picoclaw:router:queue_meta:{chat_id}"

_QUEUE_TTL = 600  # 10 min — discard stale queues

def queue_set(chat_id: str, pipeline: list[str], executor: str, message: str, sender_name: str, sender_id: str) -> None:
    """Store pipeline (discussants + executor last) and metadata."""
    r = _get_redis()
    if r is None:
        return
    pk = _q_pipeline_key(chat_id)
    r.delete(pk)
    for p in pipeline:
        r.rpush(pk, p)
    r.expire(pk, _QUEUE_TTL)
    r.set(_q_meta_key(chat_id), json.dumps({
        "executor": executor,
        "message": message,
        "sender_name": sender_name,
        "sender_id": sender_id,
    }), ex=_QUEUE_TTL)

def queue_pop(chat_id: str) -> tuple[str | None, dict]:
    """Pop next persona from pipeline. Returns (persona, meta). persona=None if empty."""
    r = _get_redis()
    if r is None:
        return None, {}
    persona = r.lpop(_q_pipeline_key(chat_id))
    if not persona:
        return None, {}
    raw = r.get(_q_meta_key(chat_id))
    meta = json.loads(raw) if raw else {}
    return persona, meta

def queue_peek_len(chat_id: str) -> int:
    r = _get_redis()
    if r is None:
        return 0
    return r.llen(_q_pipeline_key(chat_id)) or 0

def queue_clear(chat_id: str) -> None:
    r = _get_redis()
    if r is None:
        return
    r.delete(_q_pipeline_key(chat_id), _q_meta_key(chat_id))


# ── HTTP server for /queue-advance ────────────────────────────────────────────
# Persona gateways POST here after sending a response, so the router can advance
# the discussion queue without relying on Telegram getUpdates (which only delivers
# messages from the router's own bot token, not from persona bot tokens).

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

ROUTER_HTTP_PORT = int(os.environ.get("ROUTER_HTTP_PORT", "18800"))

# Shared state: chat_id → persona that just responded (set by HTTP handler, consumed by main loop)
_advance_queue: "list[tuple[str, str]]" = []
_advance_lock = threading.Lock()


class _AdvanceHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def do_POST(self):
        if self.path != "/queue-advance":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            chat_id  = str(body.get("chat_id", ""))
            persona  = str(body.get("persona", ""))
            if chat_id and persona:
                with _advance_lock:
                    _advance_queue.append((chat_id, persona))
                log.info(f"Queue advance requested: persona={persona} chat_id={chat_id}")
                self.send_response(202)
            else:
                self.send_response(400)
            self.end_headers()
        except Exception as e:
            log.warning(f"/queue-advance error: {e}")
            self.send_response(500)
            self.end_headers()


def _start_http_server():
    server = HTTPServer(("0.0.0.0", ROUTER_HTTP_PORT), _AdvanceHandler)
    log.info(f"Router HTTP server listening on :{ROUTER_HTTP_PORT}")
    server.serve_forever()


def _process_advance_queue() -> None:
    """Drain pending advance requests and inject next persona in queue."""
    with _advance_lock:
        pending = list(_advance_queue)
        _advance_queue.clear()

    for chat_id, responding_persona in pending:
        remaining = queue_peek_len(chat_id)
        log.info(f"Processing advance: {responding_persona} responded, queue_remaining={remaining}, chat_id={chat_id}")
        if remaining == 0:
            log.info(f"Queue empty for chat {chat_id} — discussion complete")
            continue

        next_persona, meta = queue_pop(chat_id)
        if not next_persona or not meta:
            log.warning(f"Queue pop returned empty for chat {chat_id}")
            continue

        orig_message = meta.get("message", "")
        orig_sender  = meta.get("sender_name", "user")
        orig_sid     = meta.get("sender_id", "user")
        executor     = meta.get("executor", next_persona)
        session_key  = f"tg:{chat_id}:{orig_sid}"
        is_executor  = (next_persona == executor)

        if is_executor:
            content = EXECUTOR_PROMPT_WITH_DISCUSSION.format(message=orig_message)
        else:
            content = DISCUSSION_PROMPTS[next_persona].format(
                message=orig_message, executor=executor
            )

        log.info(f"Queue advance: {responding_persona} → injecting {next_persona} (executor={is_executor})")
        inject_message(next_persona, orig_sender, chat_id, content, session_key)


# ── Main loop ─────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("Router gateway started")
    log.info(f"Model: {ROUTER_MODEL} | User filter: {TELEGRAM_USER_ID or 'all'} | Group filter: {ONLY_GROUP_ID or 'all'}")
    log.info(f"Redis: {REDIS_URL} | Context window: {CONTEXT_WINDOW_SIZE} pairs | TTL: {CONTEXT_TTL}s")

    _get_redis()

    # Start HTTP server for /queue-advance in background thread
    http_thread = threading.Thread(target=_start_http_server, daemon=True)
    http_thread.start()

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
        except Exception as e:
            log.error(f"getUpdates failed: {e}")
            time.sleep(5)
            continue

        # Process any pending queue advances from persona gateways
        _process_advance_queue()

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message") or update.get("edited_message")
            if not msg:
                continue

            chat      = msg.get("chat", {})
            chat_id   = str(chat.get("id"))
            chat_type = chat.get("type", "")
            sender    = msg.get("from", {})
            sender_id = str(sender.get("id", 0))
            text      = msg.get("text", "").strip()
            is_bot    = sender.get("is_bot", False)

            if chat_type not in ("group", "supergroup"):
                continue
            if ONLY_GROUP_ID and chat_id != str(ONLY_GROUP_ID):
                continue
            if not text or is_bot:
                continue

            # ── Human user message ─────────────────────────────────────────
            if TELEGRAM_USER_ID and sender_id != str(TELEGRAM_USER_ID):
                continue

            sender_name = sender.get("username") or sender.get("first_name", "user")
            log.info(f"Routing message from @{sender_name}: {text[:80]}")

            # Clear any stale queue from a previous conversation
            queue_clear(chat_id)

            mentions = extract_explicit_personas(text)
            if len(mentions) == 1:
                executor, discussants = mentions[0], []
                log.info(f"Explicit persona mention detected → forcing executor: {executor}")
            else:
                executor, discussants = pick_routing(text, chat_id, sender_id)
            log.info(f"→ Executor: {executor} | Discussants: {discussants}")

            if executor == "silent":
                log.info("Router decided: silent")
                continue

            session_key = f"tg:{chat_id}:{sender_id}"

            if not discussants:
                # Simple task — inject executor directly
                ok = inject_message(executor, sender_name, chat_id, text, session_key)
                if ok:
                    push_context(chat_id, sender_id, "user", text)
                    push_context(chat_id, sender_id, "assistant", f"[routed to {executor}]")
                    set_last_persona(chat_id, sender_id, executor)
            else:
                # Team discussion — inject first discussant now, queue the rest + executor
                # Pipeline stored: [discussant2, ..., executor] (first discussant injected immediately)
                first = discussants[0]
                rest  = discussants[1:] + [executor]
                queue_set(chat_id, rest, executor, text, sender_name, sender_id)

                content = DISCUSSION_PROMPTS[first].format(message=text, executor=executor)
                ok = inject_message(first, sender_name, chat_id, content, session_key)
                if ok:
                    push_context(chat_id, sender_id, "user", text)
                    push_context(chat_id, sender_id, "assistant", f"[discussion started: {first} → {' → '.join(rest)}]")
                    set_last_persona(chat_id, sender_id, executor)
                    log.info(f"Discussion started: {first} injected, queue={rest}")


if __name__ == "__main__":
    main()
