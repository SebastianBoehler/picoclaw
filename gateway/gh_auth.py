#!/usr/bin/env python3
"""
Shared GitHub App authentication helpers for all picoclaw gateways.

Single source of truth for:
  - JWT generation (openssl CLI)
  - Installation token exchange (curl → GitHub API)
  - Token caching (8-minute TTL)
  - gh CLI hosts.yml writing
  - init_gh_token() — call at gateway/task-mode startup

See agent_env.py for build_agent_env() — the env dict forwarded to task containers.
"""

import os
import subprocess
import time
import logging

log = logging.getLogger("gh-auth")

GITHUB_APP_ID           = os.environ.get("GITHUB_APP_ID", "")
GITHUB_INSTALLATION_ID  = os.environ.get("GITHUB_INSTALLATION_ID", "")
GITHUB_APP_PRIVATE_KEY  = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")

_GH_TOKEN_CACHE: dict = {"token": "", "expires_at": 0}


def _make_github_jwt(app_id: str, private_key_pem: str) -> str:
    """Build a GitHub App JWT using the cryptography library. Returns JWT string."""
    import base64 as _b64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    iat = now - 60
    exp = now + 540

    if os.path.isfile(private_key_pem):
        with open(private_key_pem, "r") as f:
            pem = f.read().strip()
    else:
        pem = private_key_pem.replace("\\n", "\n").strip()
    if not pem.startswith("-----"):
        raise ValueError("GITHUB_APP_PRIVATE_KEY does not look like a PEM key")

    def b64url(data: bytes) -> str:
        return _b64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header  = b64url(b'{"alg":"RS256","typ":"JWT"}')
    payload = b64url(f'{{"iat":{iat},"exp":{exp},"iss":"{app_id}"}}'.encode())
    signing_input = f"{header}.{payload}"

    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    sig_bytes = private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    signature = b64url(sig_bytes)

    return f"{signing_input}.{signature}"


def write_gh_hosts(token: str) -> None:
    """Write token to ~/.config/gh/hosts.yml so gh CLI finds it in all subprocesses."""
    gh_config_dir = os.path.expanduser("~/.config/gh")
    os.makedirs(gh_config_dir, exist_ok=True)
    hosts_path = os.path.join(gh_config_dir, "hosts.yml")
    hosts_content = (
        f"github.com:\n"
        f"    oauth_token: {token}\n"
        f"    git_protocol: https\n"
        f"    user: sunderlabs-agent\n"
    )
    with open(hosts_path, "w") as f:
        f.write(hosts_content)


def get_gh_token() -> str:
    """Return a valid GitHub App installation token, refreshing if needed (cached ~8min)."""
    if not (GITHUB_APP_ID and GITHUB_INSTALLATION_ID and GITHUB_APP_PRIVATE_KEY):
        return ""
    now = time.time()
    if _GH_TOKEN_CACHE["token"] and now < _GH_TOKEN_CACHE["expires_at"]:
        return _GH_TOKEN_CACHE["token"]
    try:
        jwt = _make_github_jwt(GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY)
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "-H", f"Authorization: Bearer {jwt}",
                "-H", "Accept: application/vnd.github+json",
                "-H", "X-GitHub-Api-Version: 2022-11-28",
                f"https://api.github.com/app/installations/{GITHUB_INSTALLATION_ID}/access_tokens",
            ],
            capture_output=True, text=True, timeout=15,
        )
        import json as _json
        data = _json.loads(result.stdout)
        token = data.get("token", "")
        if not token:
            log.error(f"GitHub App token exchange failed: {result.stdout[:300]}")
            return ""
        _GH_TOKEN_CACHE["token"] = token
        _GH_TOKEN_CACHE["expires_at"] = now + 480
        write_gh_hosts(token)
        os.environ["GH_TOKEN"] = token
        os.environ["GITHUB_TOKEN"] = token
        log.info("GitHub App installation token refreshed")
        return token
    except Exception as e:
        log.error(f"Failed to get GitHub App token: {e}")
        return ""


def token_refresh_loop() -> None:
    """Background thread: refresh GH token every 8 minutes."""
    import threading as _threading
    while True:
        time.sleep(480)
        get_gh_token()



def init_gh_token(start_refresh_thread: bool = True) -> None:
    """
    Call at gateway startup or task-mode entry.

    - If GH_TOKEN is already in os.environ (injected by the spawning gateway),
      skip re-derivation (avoids overwriting a valid token with "" on failure)
      and just write hosts.yml so gh CLI finds it.
    - Otherwise derive from GitHub App credentials and optionally start the
      background refresh thread.
    """
    import threading as _threading

    if os.environ.get("GH_TOKEN"):
        log.info("GH_TOKEN already set in env — writing hosts.yml, skipping derivation")
        write_gh_hosts(os.environ["GH_TOKEN"])
        return

    if GITHUB_APP_ID and GITHUB_INSTALLATION_ID and GITHUB_APP_PRIVATE_KEY:
        get_gh_token()
        if start_refresh_thread:
            t = _threading.Thread(target=token_refresh_loop, daemon=True)
            t.start()
            log.info("GitHub App token refresh thread started")
