#!/usr/bin/env node
/**
 * Generates a GitHub App installation token and writes it to
 * picoclaw/workspace/config/github_token
 *
 * Usage:
 *   node scripts/generate_github_token.js
 *
 * Required env vars:
 *   GITHUB_APP_ID          - GitHub App ID (numeric)
 *   GITHUB_APP_PRIVATE_KEY - Path to the .pem file, OR the PEM content itself
 *   GITHUB_INSTALLATION_ID - Installation ID (find at: Settings > Developer > Apps > Install)
 *
 * Or set them in picoclaw/.env (gitignored)
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const crypto = require("crypto");

// Load .env from picoclaw dir if present
const envPath = path.join(__dirname, "..", ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const m = line.match(/^([A-Z_]+)=(.+)$/);
    if (m) process.env[m[1]] = m[2].trim().replace(/^["']|["']$/g, "");
  }
}

const APP_ID = process.env.GITHUB_APP_ID;
const INSTALLATION_ID = process.env.GITHUB_INSTALLATION_ID;
let privateKey = process.env.GITHUB_APP_PRIVATE_KEY || "";

if (!APP_ID || !privateKey) {
  console.error("Missing required env vars: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY");
  process.exit(1);
}

if (!INSTALLATION_ID) {
  console.error([
    "GITHUB_INSTALLATION_ID is not set.",
    "",
    "To find it:",
    "  1. Go to https://github.com/settings/apps/sunderlabs-agent/installations",
    "  2. Click Install on SebastianBoehler/sunderlabs",
    "  3. The installation ID is in the URL: github.com/settings/installations/XXXXXXXX",
    "  4. Add it to picoclaw/.env: GITHUB_INSTALLATION_ID=XXXXXXXX",
  ].join("\n"));
  process.exit(1);
}

// If it's a file path, read it
if (fs.existsSync(privateKey)) {
  privateKey = fs.readFileSync(privateKey, "utf8");
}

// ── Build JWT ──────────────────────────────────────────────────────────────
function base64url(buf) {
  return buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function buildJwt(appId, pem) {
  const now = Math.floor(Date.now() / 1000);
  const header = base64url(Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const payload = base64url(Buffer.from(JSON.stringify({ iat: now - 60, exp: now + 540, iss: appId })));
  const data = `${header}.${payload}`;
  const sig = base64url(crypto.createSign("RSA-SHA256").update(data).sign(pem));
  return `${data}.${sig}`;
}

// ── Exchange JWT for installation token ────────────────────────────────────
function getInstallationToken(jwt, installationId) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: "api.github.com",
      path: `/app/installations/${installationId}/access_tokens`,
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sunderlabs-agent",
      },
    };
    const req = https.request(options, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => {
        try {
          const data = JSON.parse(body);
          if (data.token) resolve(data.token);
          else reject(new Error(`GitHub API error: ${body}`));
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on("error", reject);
    req.end();
  });
}

(async () => {
  try {
    const jwt = buildJwt(APP_ID, privateKey);
    const token = await getInstallationToken(jwt, INSTALLATION_ID);

    // Write to workspace config
    const outDir = path.join(__dirname, "..", "workspace", "config");
    fs.mkdirSync(outDir, { recursive: true });
    const outPath = path.join(outDir, "github_token");
    fs.writeFileSync(outPath, token, { mode: 0o600 });

    console.log(`✓ Token written to ${outPath}`);
    console.log(`  Expires in ~1 hour. Re-run or restart container to refresh.`);
  } catch (err) {
    console.error("Failed to generate token:", err.message);
    process.exit(1);
  }
})();
