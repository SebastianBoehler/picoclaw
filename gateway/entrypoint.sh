#!/bin/sh
# Fix Docker socket permissions if present, then exec as picoclaw user
if [ -S /var/run/docker.sock ]; then
    chmod 666 /var/run/docker.sock 2>/dev/null || true
fi

# Ensure the traces volume is writable by the picoclaw user
if [ -d /picoclaw-traces ]; then
    chown picoclaw:picoclaw /picoclaw-traces 2>/dev/null || true
fi

# In agent task containers the config/pem are staged into the shared
# workspace volume by the gateway. Symlink them into the expected paths
# so picoclaw can find them at ~/.picoclaw/config.json.
STAGED_DIR="/home/picoclaw/.picoclaw/workspace/.staged"
CONFIG_DST="/home/picoclaw/.picoclaw/config.json"
PEM_DST="/home/picoclaw/github_app.pem"

if [ -f "${STAGED_DIR}/config.json" ]; then
    cp "${STAGED_DIR}/config.json" "${CONFIG_DST}"
fi
if [ -f "${STAGED_DIR}/github_app.pem" ]; then
    cp "${STAGED_DIR}/github_app.pem" "${PEM_DST}"
fi

exec su-exec picoclaw "$@"
