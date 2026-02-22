#!/usr/bin/env python3
"""
send_telegram_file.py — send a file (or text message) to a Telegram chat.

Personas call this via exec when they need to deliver a file to the user
directly over Telegram, without going through the email gateway.

Usage:
    python3 /home/picoclaw/send_telegram_file.py \
        --chat-id -1001234567890 \
        --file /path/to/document.docx \
        [--caption "Here is your document"]

    python3 /home/picoclaw/send_telegram_file.py \
        --chat-id -1001234567890 \
        --text "Hello from Mia"

Required env vars (automatically set in persona containers):
    TELEGRAM_BOT_TOKEN   — the persona's bot token

Arguments:
    --chat-id    Target Telegram chat ID (numeric, e.g. -5099033473 for a group)
    --file       Path to file to send (sendDocument / sendPhoto based on mime type)
    --text       Text message to send instead of (or after) a file
    --caption    Optional caption for the file

Exit codes:
    0  — sent successfully
    1  — missing required arguments or env vars
    2  — Telegram API error
    3  — file not found
"""

import argparse
import mimetypes
import os
import sys
import json
import urllib.request
import urllib.error


def _api_base() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("[send_telegram_file] ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    return f"https://api.telegram.org/bot{token}"


def _send_text(api_base: str, chat_id: str, text: str) -> None:
    MAX = 4096
    for i in range(0, max(1, len(text)), MAX):
        chunk = text[i:i + MAX]
        data = json.dumps({"chat_id": chat_id, "text": chunk}).encode()
        req = urllib.request.Request(
            f"{api_base}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    print(f"[send_telegram_file] sendMessage failed: {result}", file=sys.stderr)
                    sys.exit(2)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            print(f"[send_telegram_file] HTTP {e.code}: {body}", file=sys.stderr)
            sys.exit(2)


def _send_file(api_base: str, chat_id: str, path: str, caption: str = "") -> None:
    if not os.path.isfile(path):
        print(f"[send_telegram_file] ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(3)

    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    is_image = mime.startswith("image/")
    method = "sendPhoto" if is_image else "sendDocument"
    field = "photo" if is_image else "document"

    with open(path, "rb") as fh:
        file_data = fh.read()

    filename = os.path.basename(path)
    boundary = "----PicoSendFileBoundary"

    parts = []
    # chat_id field
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
    )
    # caption field (optional)
    if caption:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
        )
    # file field header
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    )

    body_bytes = (
        "".join(parts).encode()
        + file_header.encode()
        + file_data
        + f"\r\n--{boundary}--\r\n".encode()
    )

    req = urllib.request.Request(
        f"{api_base}/{method}",
        data=body_bytes,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                print(f"[send_telegram_file] {method} failed: {result}", file=sys.stderr)
                sys.exit(2)
            print(f"[send_telegram_file] Sent {filename} ({len(file_data)} bytes) to chat {chat_id}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[send_telegram_file] HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Send a file or message to a Telegram chat")
    parser.add_argument("--chat-id", required=True, help="Telegram chat ID (numeric)")
    parser.add_argument("--file", default=None, help="Path to file to send")
    parser.add_argument("--text", default=None, help="Text message to send")
    parser.add_argument("--caption", default="", help="Caption for the file (optional)")
    args = parser.parse_args()

    if not args.file and not args.text:
        print("[send_telegram_file] ERROR: provide --file and/or --text", file=sys.stderr)
        sys.exit(1)

    api_base = _api_base()

    if args.file:
        _send_file(api_base, args.chat_id, args.file, caption=args.caption)

    if args.text:
        _send_text(api_base, args.chat_id, args.text)


if __name__ == "__main__":
    main()
