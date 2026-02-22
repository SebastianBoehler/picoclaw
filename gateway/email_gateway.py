#!/usr/bin/env python3
"""
Picoclaw Email Gateway
Polls a Gmail label via IMAP. For each unread email, creates a kanban task
assigned to the persona. The persona picks it up via its heartbeat cron and
sends the reply using send_email_reply.py.

Required env vars:
  GATEWAY_EMAIL        - Gmail account to authenticate (e.g. sebastian@sunderlabs.com)
  GATEWAY_APP_PASSWORD - Google App Password (16-char, no spaces)
  SMTP_FROM            - Alias to send FROM (e.g. alex@sunderlabs.com)
  IMAP_FOLDER          - Gmail label to poll (e.g. picoclaw/alex)
  MONGODB_URI          - MongoDB connection string
  PICOCLAW_PERSONA     - Persona slug to assign tasks to (e.g. alex)
  PICOCLAW_TENANT_ID   - Tenant ID (default: dev)

Optional:
  ALLOWED_SENDERS      - Comma-separated allowed sender emails (empty = allow all)
  POLL_INTERVAL        - Seconds between polls (default: 60)
  MAX_EMAIL_CHARS      - Max body chars in task description (default: 8000)
  EMAIL_POLL_ACK       - Set to "0" to disable ack reply (default: enabled)
"""

import email
import email.mime.multipart
import email.mime.text
import imaplib
import json
import logging
import os
import re
import smtplib
import sys
import time
import uuid
from email.header import decode_header

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("email-gateway")

# ── Config from env ────────────────────────────────────────────────────────────
GATEWAY_EMAIL        = os.environ.get("GATEWAY_EMAIL", "")
GATEWAY_APP_PASSWORD = os.environ.get("GATEWAY_APP_PASSWORD", "")
SMTP_FROM            = os.environ.get("SMTP_FROM", "") or GATEWAY_EMAIL
IMAP_FOLDER          = os.environ.get("IMAP_FOLDER", "INBOX")
PERSONA              = os.environ.get("PICOCLAW_PERSONA", "alex")
TENANT_ID            = os.environ.get("PICOCLAW_TENANT_ID", "dev")
POLL_INTERVAL        = int(os.environ.get("POLL_INTERVAL", "60"))
MAX_EMAIL_CHARS      = int(os.environ.get("MAX_EMAIL_CHARS", "8000"))
SEND_ACK             = os.environ.get("EMAIL_POLL_ACK", "1").lower() not in ("0", "false", "no")
ALLOWED_SENDERS      = {
    s.strip().lower()
    for s in os.environ.get("ALLOWED_SENDERS", "").split(",")
    if s.strip()
}

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


# ── Helpers ────────────────────────────────────────────────────────────────────

def _decode_str(value: str) -> str:
    parts = decode_header(value or "")
    out = []
    for part, charset in parts:
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def _get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", errors="replace").strip()
    return ""


def _send_ack(to_addr: str, subject: str, message_id: str) -> None:
    persona_name = PERSONA.capitalize()
    body = f"Hi,\n\nThanks for your email. I've received it and will get back to you shortly.\n\n— {persona_name}"
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["From"]    = SMTP_FROM
    msg["To"]      = to_addr
    msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"]  = message_id
    msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(GATEWAY_EMAIL, GATEWAY_APP_PASSWORD)
            server.sendmail(SMTP_FROM, to_addr, msg.as_string())
        log.info(f"Ack sent to {to_addr}")
    except Exception as e:
        log.warning(f"Ack send failed: {e}")


def _kanban_create(task_id: str, title: str, description: str,
                   sender: str, sender_name: str, message_id: str, subject: str) -> str:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from kanban import kanban_create
        return kanban_create(
            task_id=task_id,
            title=title,
            sender=sender,
            persona=PERSONA,
            assignee=PERSONA,
            tenant_id=TENANT_ID,
            source="email",
            priority="medium",
            tags=["email"],
            description=description,
            metadata={
                "reply_to":    sender,
                "reply_from":  SMTP_FROM,
                "sender_name": sender_name,
                "message_id":  message_id,
                "subject":     subject,
                "imap_folder": IMAP_FOLDER,
            },
        )
    except Exception as e:
        log.error(f"kanban_create failed: {e}")
        return ""


# ── Core poll ──────────────────────────────────────────────────────────────────

def process_inbox() -> int:
    """Poll inbox once. Returns number of kanban tasks created."""
    created = 0
    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(GATEWAY_EMAIL, GATEWAY_APP_PASSWORD)
        imap.select(IMAP_FOLDER)

        _, data = imap.search(None, "UNSEEN")
        uids = data[0].split()
        if not uids:
            log.info(f"No unread emails in {IMAP_FOLDER}")
            return 0

        log.info(f"Found {len(uids)} unread email(s) in {IMAP_FOLDER}")

        for uid in uids:
            _, msg_data = imap.fetch(uid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            from_header = _decode_str(msg.get("From", ""))
            match = re.search(r"<([^>]+)>", from_header)
            sender = match.group(1).lower() if match else from_header.lower().strip()

            # Loop prevention
            if sender in (GATEWAY_EMAIL.lower(), SMTP_FROM.lower()):
                imap.store(uid, "+FLAGS", "\\Seen")
                continue

            # Allowlist check
            if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
                log.warning(f"Rejected email from unauthorized sender: {sender}")
                imap.store(uid, "+FLAGS", "\\Seen")
                continue

            subject    = _decode_str(msg.get("Subject", "(no subject)"))
            message_id = msg.get("Message-ID", "")
            body       = _get_body(msg)

            if not body:
                log.warning(f"Empty body from {sender}, skipping")
                imap.store(uid, "+FLAGS", "\\Seen")
                continue

            name_match  = re.search(r'^([^<@]+?)\s*(?:<|$)', from_header)
            sender_name = name_match.group(1).strip() if name_match else sender
            first_name  = sender_name.split()[0] if sender_name else sender

            task_id     = uuid.uuid4().hex[:12]
            title       = f"[Email] {subject[:120]}"
            description = (
                f"Email from {sender_name} <{sender}>\n"
                f"Subject: {subject}\n\n"
                f"{body[:MAX_EMAIL_CHARS]}\n\n"
                f"---\n"
                f"Address this person as \"{first_name}\" in your reply.\n"
                f"When done, send your reply with:\n"
                f"  python3 /home/picoclaw/send_email_reply.py "
                f"--to \"{sender}\" "
                f"--subject \"{subject}\" "
                f"--message-id \"{message_id}\" "
                f"--body /home/picoclaw/.picoclaw/workspace/reply.md"
            )

            kanban_id = _kanban_create(task_id, title, description,
                                       sender, sender_name, message_id, subject)
            if kanban_id:
                log.info(f"Kanban task {kanban_id} created for email from {sender}: {subject}")
                created += 1
                if SEND_ACK:
                    _send_ack(sender, subject, message_id)
            else:
                log.error(f"Failed to create kanban task for email from {sender}")

            imap.store(uid, "+FLAGS", "\\Seen")

    return created


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if not GATEWAY_EMAIL or not GATEWAY_APP_PASSWORD:
        log.error("GATEWAY_EMAIL / GATEWAY_APP_PASSWORD not set")
        raise SystemExit(1)

    log.info(f"Email gateway starting — persona={PERSONA} folder={IMAP_FOLDER} from={SMTP_FROM}")
    log.info(f"Allowed senders: {ALLOWED_SENDERS or '(all)'} | poll interval: {POLL_INTERVAL}s")

    while True:
        try:
            process_inbox()
        except Exception as e:
            log.error(f"Inbox poll error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

