#!/usr/bin/env python3
"""
sunderlabs-cli — Control Sunderlabs Studio APIs from the command line.

Usage:
  sunderlabs leads list [--status STATUS] [--source SOURCE] [--q QUERY] [--limit N]
  sunderlabs leads get <id>
  sunderlabs leads create --name NAME [--company C] [--title T] [--email E] [--linkedin URL] [--status S] [--source SRC] [--score N] [--notes TEXT]
  sunderlabs leads update <id> [--status S] [--score N] [--notes TEXT] [--email E] [--tags TAG,TAG]
  sunderlabs leads delete <id>
  sunderlabs leads discover --category CAT --location LOC [--limit N] [--icp TEXT] [--enrich]
  sunderlabs leads batch [--limit N]
  sunderlabs leads batch-status <batch_id>

  sunderlabs kanban list [--assignee A] [--status S] [--tenant TENANT]
  sunderlabs kanban get <id>
  sunderlabs kanban create --title TITLE [--assignee A] [--tenant TENANT] [--description D] [--priority P]
  sunderlabs kanban update <id> [--status S] [--assignee A] [--rex-approved] [--notes TEXT]
  sunderlabs kanban poll --assignee A [--tenant TENANT] [--status S]
  sunderlabs kanban handoff <id> --to PERSONA [--title TITLE]

  sunderlabs meme generate --entity SLUG --topic TEXT [--style STYLE]
  sunderlabs carousel generate --entity SLUG --topic TEXT [--slides N]
  sunderlabs social generate --entity SLUG --topic TEXT

  sunderlabs release list --artist SLUG
  sunderlabs release assets --artist SLUG --release SLUG [--refresh]
  sunderlabs release run --artist SLUG --release SLUG

  sunderlabs entities list [--type TYPE]
  sunderlabs entities get <slug>

  sunderlabs config set-url URL
  sunderlabs config set-token TOKEN
  sunderlabs config show

Environment variables (override config file):
  SUNDERLABS_API_URL    — Studio API base URL (e.g. https://studio.sunderlabs.com)
  SUNDERLABS_API_TOKEN  — Bearer token for authentication
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".sunderlabs" / "config.json"
DEFAULT_URL = "http://localhost:3000"


def load_config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return cfg


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def get_base_url() -> str:
    return (
        os.environ.get("SUNDERLABS_API_URL")
        or load_config().get("api_url")
        or DEFAULT_URL
    ).rstrip("/")


def get_token() -> str | None:
    return os.environ.get("SUNDERLABS_API_TOKEN") or load_config().get("api_token")


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _request(method: str, path: str, body: dict | None = None, params: dict | None = None) -> dict:
    base = get_base_url()
    url = f"{base}{path}"

    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:
            err = {"error": str(e)}
        _die(f"HTTP {e.code}: {err.get('error') or err.get('detail') or json.dumps(err)}")
    except urllib.error.URLError as e:
        _die(f"Cannot reach {base}: {e.reason}")


import urllib.parse  # noqa: E402 (needed after _request definition)


def _get(path: str, params: dict | None = None) -> dict:
    return _request("GET", path, params=params)


def _post(path: str, body: dict) -> dict:
    return _request("POST", path, body=body)


def _patch(path: str, body: dict) -> dict:
    return _request("PATCH", path, body=body)


def _delete(path: str, params: dict | None = None) -> dict:
    return _request("DELETE", path, params=params)


# ─── Output helpers ───────────────────────────────────────────────────────────

def _die(msg: str):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str):
    print(f"✓ {msg}")


def _json(data):
    print(json.dumps(data, indent=2, default=str))


def _table(rows: list[dict], cols: list[str]):
    if not rows:
        print("(no results)")
        return
    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(row.get(c, "") or "")))
    header = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print(header)
    print("  ".join("-" * widths[c] for c in cols))
    for row in rows:
        print("  ".join(str(row.get(c, "") or "").ljust(widths[c]) for c in cols))


# ─── Leads ────────────────────────────────────────────────────────────────────

def cmd_leads_list(args):
    params = {}
    if args.status:
        params["status"] = args.status
    if args.source:
        params["source"] = args.source
    if args.q:
        params["q"] = args.q
    if args.limit:
        params["limit"] = args.limit
    r = _get("/api/leads", params)
    leads = r.get("leads", [])
    _table(leads, ["_id", "name", "company", "title", "status", "score", "source"])


def cmd_leads_get(args):
    r = _get(f"/api/leads/{args.id}")
    _json(r)


def cmd_leads_create(args):
    body = {"name": args.name}
    for field in ["company", "title", "email", "linkedin_url", "status", "source", "notes"]:
        val = getattr(args, field.replace("linkedin_url", "linkedin"), None)
        if field == "linkedin_url":
            val = getattr(args, "linkedin", None)
        if val is not None:
            body[field] = val
    if args.score is not None:
        body["score"] = args.score
    r = _post("/api/leads", body)
    _ok(f"Lead created: {r.get('id')}")


def cmd_leads_update(args):
    body = {}
    if args.status:
        body["status"] = args.status
    if args.score is not None:
        body["score"] = args.score
    if args.notes:
        body["notes"] = args.notes
    if args.email:
        body["email"] = args.email
    if args.tags:
        body["tags"] = [t.strip() for t in args.tags.split(",")]
    r = _patch(f"/api/leads/{args.id}", body)
    _ok(f"Updated: {r.get('updated_fields')}")


def cmd_leads_delete(args):
    r = _delete("/api/leads", {"id": args.id})
    _ok("Deleted") if r.get("ok") else _die(r.get("error", "failed"))


def cmd_leads_discover(args):
    body = {
        "category": args.category,
        "location": args.location,
        "limit": args.limit or 20,
        "icp": args.icp or "",
        "use_llm_scoring": True,
        "handelsregister_enrich": bool(args.enrich),
    }
    r = _post("/api/leads/discover", body)
    if r.get("batch_id"):
        _ok(f"Batch started: {r['batch_id']}")
        print(f"  Check status: sunderlabs leads batch-status {r['batch_id']}")
    else:
        _json(r)


def cmd_leads_batch(args):
    r = _get("/api/leads/discover", {"limit": args.limit or 20})
    batches = r if isinstance(r, list) else r.get("batches", [r])
    _table(batches, ["batch_id", "status", "category", "location", "count", "created_at"])


def cmd_leads_batch_status(args):
    r = _get(f"/api/leads/discover", {"batch_id": args.batch_id})
    _json(r)


# ─── Kanban ───────────────────────────────────────────────────────────────────

KANBAN_BIN = "/home/picoclaw/kanban.py"


def _kanban(subcmd: list[str]) -> str:
    import subprocess
    result = subprocess.run(
        ["python3", KANBAN_BIN] + subcmd,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        _die(result.stderr.strip() or "kanban.py failed")
    return result.stdout.strip()


def cmd_kanban_list(args):
    subcmd = ["list"]
    if args.assignee:
        subcmd += ["--assignee", args.assignee]
    if args.status:
        subcmd += ["--status", args.status]
    if args.tenant:
        subcmd += ["--tenant-id", args.tenant]
    out = _kanban(subcmd)
    print(out)


def cmd_kanban_get(args):
    out = _kanban(["get", args.id])
    print(out)


def cmd_kanban_create(args):
    subcmd = ["create", "--title", args.title]
    if args.assignee:
        subcmd += ["--assignee", args.assignee]
    if args.tenant:
        subcmd += ["--tenant-id", args.tenant]
    if args.description:
        subcmd += ["--description", args.description]
    if args.priority:
        subcmd += ["--priority", args.priority]
    out = _kanban(subcmd)
    print(out)


def cmd_kanban_update(args):
    subcmd = ["update", args.id]
    if args.status:
        subcmd += ["--status", args.status]
    if args.assignee:
        subcmd += ["--assignee", args.assignee]
    if args.rex_approved:
        subcmd += ["--rex-approved", "true"]
    if args.notes:
        subcmd += ["--notes", args.notes]
    out = _kanban(subcmd)
    print(out)


def cmd_kanban_poll(args):
    subcmd = ["poll", "--assignee", args.assignee]
    if args.tenant:
        subcmd += ["--tenant-id", args.tenant]
    if args.status:
        subcmd += ["--status", args.status]
    out = _kanban(subcmd)
    print(out)


def cmd_kanban_handoff(args):
    subcmd = ["handoff", args.id, "--to", args.to]
    if args.title:
        subcmd += ["--title", args.title]
    out = _kanban(subcmd)
    print(out)


# ─── Meme / Carousel / Social ─────────────────────────────────────────────────

def cmd_meme_generate(args):
    body = {"entity_slug": args.entity, "topic": args.topic}
    if args.style:
        body["style"] = args.style
    r = _post("/api/meme-generate", body)
    _json(r)


def cmd_carousel_generate(args):
    body = {"entity_slug": args.entity, "topic": args.topic}
    if args.slides:
        body["slide_count"] = args.slides
    r = _post("/api/carousels", body)
    _json(r)


def cmd_social_generate(args):
    body = {"entity_slug": args.entity, "topic": args.topic}
    r = _post("/api/corporate-posts", body)
    _json(r)


# ─── Release ──────────────────────────────────────────────────────────────────

def cmd_release_list(args):
    r = _get("/api/release", {"artistSlug": args.artist})
    releases = r if isinstance(r, list) else r.get("releases", [r])
    _table(releases, ["slug", "title", "status", "created_at"])


def cmd_release_assets(args):
    params = {"artistSlug": args.artist, "releaseSlug": args.release}
    if args.refresh:
        params["refresh"] = "1"
    r = _get("/api/release-files", params)
    files = r.get("files", [])
    _table(files, ["object_path", "size_bytes", "updated_at"])


def cmd_release_run(args):
    body = {"artistSlug": args.artist, "releaseSlug": args.release}
    r = _post("/api/release-run", body)
    _json(r)


# ─── Entities ─────────────────────────────────────────────────────────────────

def cmd_entities_list(args):
    params = {}
    if args.type:
        params["type"] = args.type
    r = _get("/api/entities", params)
    entities = r if isinstance(r, list) else r.get("entities", [r])
    _table(entities, ["slug", "name", "type", "tags"])


def cmd_entities_get(args):
    r = _get(f"/api/entities/{args.slug}")
    _json(r)


# ─── Config ───────────────────────────────────────────────────────────────────

def cmd_config_set_url(args):
    cfg = load_config()
    cfg["api_url"] = args.url
    save_config(cfg)
    _ok(f"API URL set to: {args.url}")


def cmd_config_set_token(args):
    cfg = load_config()
    cfg["api_token"] = args.token
    save_config(cfg)
    _ok("API token saved")


def cmd_config_show(args):
    cfg = load_config()
    token = cfg.get("api_token", "")
    if token:
        cfg["api_token"] = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
    print(f"Config file : {CONFIG_PATH}")
    print(f"API URL     : {get_base_url()}")
    print(f"Token       : {cfg.get('api_token', '(not set)')}")
    env_url = os.environ.get("SUNDERLABS_API_URL")
    env_tok = os.environ.get("SUNDERLABS_API_TOKEN")
    if env_url:
        print(f"Env URL     : {env_url}  (overrides config)")
    if env_tok:
        print(f"Env Token   : {env_tok[:8]}...  (overrides config)")


# ─── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sunderlabs",
        description="Sunderlabs Studio CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="group", required=True)

    # ── leads ──
    leads = sub.add_parser("leads", help="Lead management & discovery")
    lsub = leads.add_subparsers(dest="cmd", required=True)

    ll = lsub.add_parser("list", help="List leads")
    ll.add_argument("--status", help="Filter by status (new/contacted/qualified/disqualified)")
    ll.add_argument("--source", help="Filter by source")
    ll.add_argument("--q", help="Search query")
    ll.add_argument("--limit", type=int, default=50)
    ll.set_defaults(func=cmd_leads_list)

    lg = lsub.add_parser("get", help="Get lead by ID")
    lg.add_argument("id")
    lg.set_defaults(func=cmd_leads_get)

    lc = lsub.add_parser("create", help="Create a lead")
    lc.add_argument("--name", required=True)
    lc.add_argument("--company")
    lc.add_argument("--title")
    lc.add_argument("--email")
    lc.add_argument("--linkedin")
    lc.add_argument("--status", default="new")
    lc.add_argument("--source", default="manual")
    lc.add_argument("--score", type=int)
    lc.add_argument("--notes")
    lc.set_defaults(func=cmd_leads_create)

    lu = lsub.add_parser("update", help="Update a lead")
    lu.add_argument("id")
    lu.add_argument("--status")
    lu.add_argument("--score", type=int)
    lu.add_argument("--notes")
    lu.add_argument("--email")
    lu.add_argument("--tags", help="Comma-separated tags")
    lu.set_defaults(func=cmd_leads_update)

    ld = lsub.add_parser("delete", help="Delete a lead")
    ld.add_argument("id")
    ld.set_defaults(func=cmd_leads_delete)

    ldis = lsub.add_parser("discover", help="Start lead discovery pipeline")
    ldis.add_argument("--category", required=True, help="Business category (e.g. 'Steuerberater')")
    ldis.add_argument("--location", required=True, help="Location (e.g. 'München')")
    ldis.add_argument("--limit", type=int, default=20)
    ldis.add_argument("--icp", help="Ideal customer profile description")
    ldis.add_argument("--enrich", action="store_true", help="Enrich via Handelsregister")
    ldis.set_defaults(func=cmd_leads_discover)

    lb = lsub.add_parser("batch", help="List recent discovery batches")
    lb.add_argument("--limit", type=int, default=20)
    lb.set_defaults(func=cmd_leads_batch)

    lbs = lsub.add_parser("batch-status", help="Check discovery batch status")
    lbs.add_argument("batch_id")
    lbs.set_defaults(func=cmd_leads_batch_status)

    # ── kanban ──
    kanban = sub.add_parser("kanban", help="Kanban task management")
    ksub = kanban.add_subparsers(dest="cmd", required=True)

    kl = ksub.add_parser("list", help="List tasks")
    kl.add_argument("--assignee")
    kl.add_argument("--status")
    kl.add_argument("--tenant", default="dev")
    kl.set_defaults(func=cmd_kanban_list)

    kg = ksub.add_parser("get", help="Get task by ID")
    kg.add_argument("id")
    kg.set_defaults(func=cmd_kanban_get)

    kc = ksub.add_parser("create", help="Create a task")
    kc.add_argument("--title", required=True)
    kc.add_argument("--assignee")
    kc.add_argument("--tenant", default="dev")
    kc.add_argument("--description")
    kc.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    kc.set_defaults(func=cmd_kanban_create)

    ku = ksub.add_parser("update", help="Update a task")
    ku.add_argument("id")
    ku.add_argument("--status", choices=["todo", "in_progress", "done", "blocked"])
    ku.add_argument("--assignee")
    ku.add_argument("--rex-approved", action="store_true")
    ku.add_argument("--notes")
    ku.set_defaults(func=cmd_kanban_update)

    kp = ksub.add_parser("poll", help="Poll tasks for an assignee")
    kp.add_argument("--assignee", required=True)
    kp.add_argument("--tenant", default="dev")
    kp.add_argument("--status", default="todo")
    kp.set_defaults(func=cmd_kanban_poll)

    kh = ksub.add_parser("handoff", help="Hand off task to another persona")
    kh.add_argument("id")
    kh.add_argument("--to", required=True, help="Target persona (e.g. mia)")
    kh.add_argument("--title")
    kh.set_defaults(func=cmd_kanban_handoff)

    # ── meme ──
    meme = sub.add_parser("meme", help="Meme generation")
    msub = meme.add_subparsers(dest="cmd", required=True)
    mg = msub.add_parser("generate", help="Generate a meme")
    mg.add_argument("--entity", required=True, help="Entity slug")
    mg.add_argument("--topic", required=True)
    mg.add_argument("--style")
    mg.set_defaults(func=cmd_meme_generate)

    # ── carousel ──
    carousel = sub.add_parser("carousel", help="Carousel generation")
    csub = carousel.add_subparsers(dest="cmd", required=True)
    cg = csub.add_parser("generate", help="Generate a carousel")
    cg.add_argument("--entity", required=True)
    cg.add_argument("--topic", required=True)
    cg.add_argument("--slides", type=int)
    cg.set_defaults(func=cmd_carousel_generate)

    # ── social ──
    social = sub.add_parser("social", help="Social post generation")
    ssub = social.add_subparsers(dest="cmd", required=True)
    sg = ssub.add_parser("generate", help="Generate a social post")
    sg.add_argument("--entity", required=True)
    sg.add_argument("--topic", required=True)
    sg.set_defaults(func=cmd_social_generate)

    # ── release ──
    release = sub.add_parser("release", help="Music release management")
    rsub = release.add_subparsers(dest="cmd", required=True)

    rl = rsub.add_parser("list", help="List releases for an artist")
    rl.add_argument("--artist", required=True)
    rl.set_defaults(func=cmd_release_list)

    ra = rsub.add_parser("assets", help="List release assets")
    ra.add_argument("--artist", required=True)
    ra.add_argument("--release", required=True)
    ra.add_argument("--refresh", action="store_true")
    ra.set_defaults(func=cmd_release_assets)

    rr = rsub.add_parser("run", help="Run release pipeline")
    rr.add_argument("--artist", required=True)
    rr.add_argument("--release", required=True)
    rr.set_defaults(func=cmd_release_run)

    # ── entities ──
    entities = sub.add_parser("entities", help="Entity management")
    esub = entities.add_subparsers(dest="cmd", required=True)

    el = esub.add_parser("list", help="List entities")
    el.add_argument("--type", help="Filter by type (artist, influencer, meme_account, ...)")
    el.set_defaults(func=cmd_entities_list)

    eg = esub.add_parser("get", help="Get entity by slug")
    eg.add_argument("slug")
    eg.set_defaults(func=cmd_entities_get)

    # ── config ──
    config = sub.add_parser("config", help="CLI configuration")
    cfgsub = config.add_subparsers(dest="cmd", required=True)

    csu = cfgsub.add_parser("set-url", help="Set Studio API base URL")
    csu.add_argument("url")
    csu.set_defaults(func=cmd_config_set_url)

    cst = cfgsub.add_parser("set-token", help="Set API auth token")
    cst.add_argument("token")
    cst.set_defaults(func=cmd_config_set_token)

    csh = cfgsub.add_parser("show", help="Show current config")
    csh.set_defaults(func=cmd_config_show)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
