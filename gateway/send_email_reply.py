#!/usr/bin/env python3
"""
send_email_reply.py — Send an email reply from a persona alias.

Called by agents after completing an email kanban task.

Usage:
    python3 /home/picoclaw/send_email_reply.py \
        --to "sender@example.com" \
        --subject "Re: Original subject" \
        --message-id "<original-message-id>" \
        --body /home/picoclaw/.picoclaw/workspace/reply.md

Required env vars (already set in persona containers):
    GATEWAY_EMAIL         - Gmail account to authenticate
    GATEWAY_APP_PASSWORD  - Google App Password
    SMTP_FROM             - Alias to send FROM (e.g. alex@sunderlabs.com)
"""

import argparse
import email
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import mimetypes
import os
import re
import smtplib
import sys

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _build_html(body: str) -> str:
    try:
        import markdown
        content = markdown.markdown(body, extensions=["fenced_code", "tables"])
    except Exception:
        # Minimal fallback
        html = body
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        content = html.replace("\n\n", "</p><p>")
    smtp_from = os.environ.get("SMTP_FROM", os.environ.get("GATEWAY_EMAIL", ""))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
max-width:700px;margin:0 auto;padding:32px 24px;background:#fff;color:#1a1a1a;line-height:1.6;font-size:15px}}
h1{{font-size:22px;font-weight:700;margin:28px 0 8px}}
h2{{font-size:18px;font-weight:600;margin:24px 0 6px}}
h3{{font-size:15px;font-weight:600;margin:20px 0 4px}}
p{{margin:0 0 14px}}
pre{{background:#f4f4f5;border-radius:6px;padding:14px 16px;overflow-x:auto;font-size:13px}}
code{{background:#f4f4f5;border-radius:4px;padding:2px 6px;font-size:13px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #e4e4e7;padding:8px 12px}}
.footer{{margin-top:40px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af}}
</style></head><body>{content}
<div class="footer">Sent by Sunderlabs AI Agent &middot; {smtp_from}</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Send an email reply from a persona alias")
    parser.add_argument("--to",         required=True,  help="Recipient email address")
    parser.add_argument("--subject",    required=True,  help="Email subject")
    parser.add_argument("--message-id", default="",     help="Original Message-ID for threading")
    parser.add_argument("--body",       required=True,  help="Body text or path to a .md file")
    parser.add_argument("--attach",     nargs="*", default=[], help="File paths to attach")
    args = parser.parse_args()

    gateway_email = os.environ.get("GATEWAY_EMAIL", "")
    app_password  = os.environ.get("GATEWAY_APP_PASSWORD", "")
    smtp_from     = os.environ.get("SMTP_FROM", "") or gateway_email

    if not gateway_email or not app_password:
        print("[send_email_reply] ERROR: GATEWAY_EMAIL / GATEWAY_APP_PASSWORD not set", file=sys.stderr)
        sys.exit(2)

    # Read body
    body = ""
    if os.path.isfile(args.body):
        with open(args.body, "r", encoding="utf-8") as f:
            body = f.read().strip()
    else:
        body = args.body.strip()

    if not body:
        print("[send_email_reply] ERROR: empty body", file=sys.stderr)
        sys.exit(2)

    subject = args.subject if args.subject.startswith("Re:") else f"Re: {args.subject}"
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

    msg["From"]    = smtp_from
    msg["To"]      = args.to
    msg["Subject"] = subject
    if args.message_id:
        msg["In-Reply-To"] = args.message_id
        msg["References"]  = args.message_id

    for file_path in attachments:
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
            with open(file_path, "rb") as f:
                data = f.read()
            part = email.mime.base.MIMEBase(main_type, sub_type)
            part.set_payload(data)
            email.encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(file_path))
            msg.attach(part)
            print(f"[send_email_reply] Attached: {os.path.basename(file_path)} ({len(data)} bytes)")
        except Exception as e:
            print(f"[send_email_reply] WARNING: could not attach {file_path}: {e}", file=sys.stderr)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(gateway_email, app_password)
            server.sendmail(smtp_from, args.to, msg.as_string())
    except Exception as e:
        print(f"[send_email_reply] SMTP ERROR: {e}", file=sys.stderr)
        sys.exit(3)

    n = len(attachments)
    print(f"[send_email_reply] Sent to {args.to} from {smtp_from} ({n} attachment(s))")


if __name__ == "__main__":
    main()
