#!/usr/bin/env python3
"""
send_email.py — called by the picoclaw agent to send the reply email with optional attachments.

Usage:
    python3 /home/picoclaw/send_email.py \
        --body "Reply text or path to reply.md" \
        --attach /path/to/file.pdf /path/to/slides.pptx

The script reads SMTP credentials and recipient info from environment variables
set by the gateway when spawning the task container.

Required env vars (set automatically by gateway):
    GATEWAY_EMAIL, GATEWAY_APP_PASSWORD, SMTP_HOST, SMTP_PORT
    PICOCLAW_TASK_TO, PICOCLAW_TASK_SUBJECT, PICOCLAW_TASK_MESSAGE_ID
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


def build_html(body: str) -> str:
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", required=False, help="Reply body text, or path to a .md file")
    parser.add_argument("--attach", nargs="*", default=[], help="File paths to attach")
    args = parser.parse_args()

    # Read body — from arg or from reply.md
    body = ""
    if args.body:
        if os.path.isfile(args.body):
            with open(args.body, "r", encoding="utf-8") as f:
                body = f.read().strip()
        else:
            body = args.body.strip()
    else:
        reply_md = "/home/picoclaw/.picoclaw/workspace/reply.md"
        if os.path.isfile(reply_md):
            with open(reply_md, "r", encoding="utf-8") as f:
                body = f.read().strip()

    if not body:
        print("[send_email] ERROR: no body provided and reply.md is empty", file=sys.stderr)
        sys.exit(1)

    # SMTP config from env
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    gateway_email = os.environ.get("GATEWAY_EMAIL", "")
    app_password = os.environ.get("GATEWAY_APP_PASSWORD", "")
    to_addr = os.environ.get("PICOCLAW_TASK_TO", "")
    subject = os.environ.get("PICOCLAW_TASK_SUBJECT", "(no subject)")
    message_id = os.environ.get("PICOCLAW_TASK_MESSAGE_ID", "")

    if not gateway_email or not app_password or not to_addr:
        print("[send_email] ERROR: missing GATEWAY_EMAIL / GATEWAY_APP_PASSWORD / PICOCLAW_TASK_TO", file=sys.stderr)
        sys.exit(1)

    attachments = [f for f in (args.attach or []) if os.path.isfile(f)]

    # Build message
    if attachments:
        msg = email.mime.multipart.MIMEMultipart("mixed")
        alt = email.mime.multipart.MIMEMultipart("alternative")
        alt.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        alt.attach(email.mime.text.MIMEText(build_html(body), "html", "utf-8"))
        msg.attach(alt)
    else:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
        msg.attach(email.mime.text.MIMEText(build_html(body), "html", "utf-8"))

    msg["From"] = gateway_email
    msg["To"] = to_addr
    msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id

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
            print(f"[send_email] Attached: {os.path.basename(file_path)} ({len(data)} bytes)")
        except Exception as e:
            print(f"[send_email] WARNING: could not attach {file_path}: {e}", file=sys.stderr)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(gateway_email, app_password)
        server.sendmail(gateway_email, to_addr, msg.as_string())

    n = len(attachments)
    print(f"[send_email] Sent to {to_addr} ({n} attachment(s))")

    # Write sentinel so gateway knows the agent already sent the reply
    task_id = os.environ.get("PICOCLAW_TASK_ID", "")
    if task_id:
        workspace = os.path.expanduser("~/.picoclaw/workspace")
        sentinel = os.path.join(workspace, "tasks", f"{task_id}.sent")
        try:
            open(sentinel, "w").close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
