#!/bin/sh
# Generate a GitHub App installation token using openssl + curl (no extra deps).
# Usage: gh_app_token.sh <app_id> <installation_id> <private_key_pem>
# Prints the installation token to stdout, or exits non-zero on failure.
#
# The private key can be passed as:
#   - A PEM string (with literal \n newlines)
#   - A file path (if it starts with /)

set -e

APP_ID="$1"
INSTALLATION_ID="$2"
PRIVATE_KEY="$3"

if [ -z "$APP_ID" ] || [ -z "$INSTALLATION_ID" ] || [ -z "$PRIVATE_KEY" ]; then
    echo "Usage: gh_app_token.sh <app_id> <installation_id> <private_key_pem>" >&2
    exit 1
fi

# Write key to a temp file (handle both literal \n and real newlines)
KEY_FILE=$(mktemp /tmp/gh_app_key.XXXXXX.pem)
trap 'rm -f "$KEY_FILE"' EXIT

if [ -f "$PRIVATE_KEY" ]; then
    cp "$PRIVATE_KEY" "$KEY_FILE"
else
    # Replace literal \n with real newlines
    printf '%s' "$PRIVATE_KEY" | sed 's/\\n/\n/g' > "$KEY_FILE"
fi

# ── Build JWT ──────────────────────────────────────────────────────────────────
NOW=$(date +%s)
IAT=$((NOW - 60))       # issued 60s ago (clock skew tolerance)
EXP=$((NOW + 540))      # expires in 9 minutes (max 10m)

# Base64url encode (no padding)
b64url() {
    openssl base64 -A | tr '+/' '-_' | tr -d '='
}

HEADER=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
PAYLOAD=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' "$IAT" "$EXP" "$APP_ID" | b64url)

SIGNING_INPUT="${HEADER}.${PAYLOAD}"

SIGNATURE=$(printf '%s' "$SIGNING_INPUT" | openssl dgst -sha256 -sign "$KEY_FILE" | b64url)

JWT="${SIGNING_INPUT}.${SIGNATURE}"

# ── Exchange JWT for installation token ───────────────────────────────────────
RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/app/installations/${INSTALLATION_ID}/access_tokens")

TOKEN=$(printf '%s' "$RESPONSE" | grep -o '"token":"[^"]*"' | head -1 | sed 's/"token":"//;s/"//')

if [ -z "$TOKEN" ]; then
    echo "Failed to get installation token. Response: $RESPONSE" >&2
    exit 1
fi

printf '%s' "$TOKEN"
