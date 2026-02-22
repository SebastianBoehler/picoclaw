#!/usr/bin/env python3
"""
send_outbound_email.py — send an outbound email to any whitelisted recipient.

Unlike send_email.py (which replies to the task sender), this script is for
outreach emails to leads, third parties, or any external address.

Usage:
    python3 /home/picoclaw/send_outbound_email.py \
        --to "contact@company.com" \
        --subject "Zusammenarbeit — Sunderlabs" \
        --body "Email body text or path to a .md file" \
        [--attach /path/to/file.pdf]

Required env vars (set automatically by gateway in agent containers):
    GATEWAY_EMAIL, GATEWAY_APP_PASSWORD
    OUTBOUND_EMAIL_WHITELIST  — comma-separated allowed recipient addresses/domains
                                e.g. "basti@hotmail.de,@sunderlabs.com,@trusted.org"
                                Use "@domain.com" to whitelist an entire domain.
                                Set to "*" to allow all (INSECURE — only for testing).

Exit codes:
    0  — sent successfully
    1  — recipient not in whitelist (hard block — never retried)
    2  — missing required arguments or env vars
    3  — SMTP error
"""

import argparse
import email
import email.encoders
import email.mime.application
import email.mime.base
import email.mime.multipart
import email.mime.text
import mimetypes
import os
import smtplib
import sys


def _build_html(body: str) -> str:
    try:
        import markdown
        content = markdown.markdown(body, extensions=["fenced_code", "tables"])
    except Exception:
        content = body.replace("\n", "<br>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
max-width:700px;margin:0 auto;padding:32px 24px;background:#fff;color:#1a1a1a;line-height:1.6}}
pre{{background:#f4f4f5;border-radius:6px;padding:14px 16px;overflow-x:auto;font-size:13px}}
code{{background:#f4f4f5;border-radius:4px;padding:2px 6px;font-size:13px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #e4e4e7;padding:8px 12px}}
</style></head><body>{content}</body></html>"""


def _is_whitelisted(recipient: str, whitelist_raw: str) -> bool:
    """
    Check if recipient is allowed.

    Whitelist entries:
      - "*"            → allow all
      - "foo@bar.com"  → exact address match (case-insensitive)
      - "@bar.com"     → entire domain match
    """
    recipient = recipient.strip().lower()
    if not whitelist_raw or not whitelist_raw.strip():
        return False  # empty whitelist = deny all

    for entry in whitelist_raw.split(","):
        entry = entry.strip().lower()
        if not entry:
            continue
        if entry == "*":
            return True
        if entry.startswith("@"):
            # domain wildcard: @sunderlabs.com matches foo@sunderlabs.com
            if recipient.endswith(entry):
                return True
        else:
            if recipient == entry:
                return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Send an outbound email (whitelist-gated)")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", required=False, help="Body text or path to a .md file")
    parser.add_argument("--attach", nargs="*", default=[], help="File paths to attach")
    args = parser.parse_args()

    # ── Credentials from env ────────────────────────────────────────────────
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    gateway_email = os.environ.get("GATEWAY_EMAIL", "")
    app_password = os.environ.get("GATEWAY_APP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", "") or gateway_email
    whitelist_raw = os.environ.get("OUTBOUND_EMAIL_WHITELIST", "")

    if not gateway_email or not app_password:
        print(
            "[send_outbound_email] ERROR: GATEWAY_EMAIL / GATEWAY_APP_PASSWORD not set",
            file=sys.stderr,
        )
        sys.exit(2)

    # ── Whitelist check ─────────────────────────────────────────────────────
    recipient = args.to.strip()
    if not _is_whitelisted(recipient, whitelist_raw):
        print(
            f"[send_outbound_email] BLOCKED: '{recipient}' is not in OUTBOUND_EMAIL_WHITELIST.\n"
            f"  Whitelist: {whitelist_raw or '(empty — all blocked)'}\n"
            f"  To add this recipient, update OUTBOUND_EMAIL_WHITELIST in the gateway env.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Read body ───────────────────────────────────────────────────────────
    body = ""
    if args.body:
        if os.path.isfile(args.body):
            with open(args.body, "r", encoding="utf-8") as f:
                body = f.read().strip()
        else:
            body = args.body.strip()

    if not body:
        print("[send_outbound_email] ERROR: no body provided", file=sys.stderr)
        sys.exit(2)

    # ── Build message ───────────────────────────────────────────────────────
    attachments = [f for f in (args.attach or []) if os.path.isfile(f)]

    if attachments:
        msg = email.mime.multipart.MIMEMultipart("mixed")
        alt = email.mime.multipart.MIMEMultipart("alternative")
        alt.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        alt.attach(email.mime.text.MIMEText(_build_html(body), "html", "utf-8"))
        msg.attach(alt)
    else:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        msg.attach(email.mime.text.MIMEText(_build_html(body), "html", "utf-8"))

    msg["From"] = smtp_from
    msg["To"] = recipient
    msg["Subject"] = args.subject

    for file_path in attachments:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
            with open(file_path, "rb") as f:
                data = f.read()
            part = email.mime.base.MIMEBase(main_type, sub_type)
            part.set_payload(data)
            email.encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", "attachment", filename=os.path.basename(file_path)
            )
            msg.attach(part)
            print(f"[send_outbound_email] Attached: {os.path.basename(file_path)} ({len(data)} bytes)")
        except Exception as e:
            print(f"[send_outbound_email] WARNING: could not attach {file_path}: {e}", file=sys.stderr)

    # ── Send ────────────────────────────────────────────────────────────────
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(gateway_email, app_password)
            server.sendmail(smtp_from, recipient, msg.as_string())
    except Exception as e:
        print(f"[send_outbound_email] SMTP ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    n = len(attachments)
    print(f"[send_outbound_email] Sent to {recipient} from {smtp_from} ({n} attachment(s))")

    # ── Log to outreach log ─────────────────────────────────────────────────
    try:
        import datetime
        log_dir = "/home/picoclaw/.picoclaw/workspace/leads"
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "outreach-log.md")
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        entry = f"- `{ts}` → **{recipient}** | {args.subject}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


if __name__ == "__main__":
    main()
