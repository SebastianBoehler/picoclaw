#!/usr/bin/env python3
"""
agent_env.py — Builds the environment dict forwarded to every task container.

Single source of truth for which env vars task containers receive.
Add new vars here when task containers need them; gateway-specific secrets
(bot tokens, IMAP passwords, etc.) are intentionally excluded.
"""

import json
import os
from gh_auth import get_gh_token


def _load_config_providers() -> None:
    """Inject provider API keys from config.json into os.environ if not already set."""
    # Config is always mounted at the picoclaw user's home, regardless of
    # which user the gateway process runs as (root in gateway containers).
    for candidate in (
        "/home/picoclaw/.picoclaw/config.json",
        os.path.expanduser("~/.picoclaw/config.json"),
    ):
        if os.path.exists(candidate):
            config_path = candidate
            break
    else:
        return
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        providers = cfg.get("providers", {})
        # openrouter → OPENROUTER_API_KEY
        or_key = providers.get("openrouter", {}).get("api_key", "")
        if or_key and not os.environ.get("OPENROUTER_API_KEY"):
            os.environ["OPENROUTER_API_KEY"] = or_key
        # openai → OPENAI_API_KEY
        oa_key = providers.get("openai", {}).get("api_key", "")
        if oa_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = oa_key
        # anthropic → ANTHROPIC_API_KEY
        an_key = providers.get("anthropic", {}).get("api_key", "")
        if an_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = an_key
        # xai → X_AI_KEY
        xai_key = providers.get("xai", {}).get("api_key", "")
        if xai_key and not os.environ.get("X_AI_KEY"):
            os.environ["X_AI_KEY"] = xai_key
    except Exception:
        pass

# ── Vars forwarded to every task container ─────────────────────────────────────
_AGENT_ENV_KEYS = [
    # LLM / AI
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "X_AI_KEY",

    # Outbound email (send_outbound_email.py)
    "GATEWAY_EMAIL",
    "GATEWAY_APP_PASSWORD",
    "OUTBOUND_EMAIL_WHITELIST",

    # GitHub App (gh CLI + private repo access)
    "GITHUB_APP_ID",
    "GITHUB_INSTALLATION_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",

    # Shopify Admin API
    "SHOPIFY_STORE_URL",
    "SHOPIFY_ACCESS_TOKEN",
    "SHOPIFY_API_VERSION",

    # MongoDB (kanban.py)
    "MONGODB_URI",

    # Picoclaw runtime
    "PICOCLAW_BIN",
    "PICOCLAW_DEBUG",
    "PICOCLAW_WORKSPACE_VOLUME",
    "PICOCLAW_BASE_IMAGE",
    "PICOCLAW_TRACES_DB_URL",

    # Observability
    "WANDB_API_KEY",
    "WANDB_PROJECT",

    # Browser-use
    "BROWSER_USE_MODEL",
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",

    # PATH / system (needed for subprocess calls inside container)
    "PATH",
    "HOME",
    "USER",
]


def build_agent_env() -> dict:
    """Return env dict for task containers with a fresh GH_TOKEN injected."""
    _load_config_providers()
    env = {k: os.environ[k] for k in _AGENT_ENV_KEYS if k in os.environ}

    # Always inject a fresh GitHub App installation token
    gh_token = get_gh_token()
    if gh_token:
        env["GH_TOKEN"] = gh_token
        env["GITHUB_TOKEN"] = gh_token

    # Task containers are NOT on the compose network, so they can't resolve
    # internal hostnames like "picoclaw-traces-db". Rewrite to host.docker.internal
    # so they reach Postgres via the exposed host port instead.
    if "PICOCLAW_TRACES_DB_URL" in env:
        env["PICOCLAW_TRACES_DB_URL"] = env["PICOCLAW_TRACES_DB_URL"].replace(
            "picoclaw-traces-db:5432", "host.docker.internal:5433"
        )

    return env
