"""
email_reader.py
---------------
Reads emails from a mailbox over IMAP (e.g. Strato) and converts each one
into the SAME shape that Microsoft Graph uses (id, from, subject, body,
receivedDateTime).

Why the same shape? So the rest of the system (process_inbox.py, pipeline,
router) does not change at all. We just swapped the *source* of the emails
from a fake JSON file to a real mailbox.

Settings come from the .env file (never hard-code your password):
    IMAP_SERVER=imap.strato.de
    IMAP_PORT=993
    EMAIL_USER=nabeel.asad@wqs.de
    EMAIL_PASSWORD=your-password

Run it directly to test the connection and list recent emails:
    python email_reader.py
"""

import os
import email
import imaplib
from email.header import decode_header
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
load_dotenv()                                    # load EMAIL_USER, EMAIL_PASSWORD, IMAP_*


def _decode(value) -> str:
    """Decode an email header (handles =?UTF-8?...?= encoded subjects)."""
    if value is None:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _get_body(msg) -> tuple[str, str]:
    """
    Return (content, content_type) for an email.
    Prefers plain text; falls back to HTML.
    """
    plain = None
    html = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                html = text
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html = text
        else:
            plain = text

    if plain:
        return plain, "text"
    if html:
        return html, "html"
    return "", "text"


def _extract_sender(from_header: str) -> tuple[str, str]:
    """Turn 'Maria Hoffmann <maria@kwp.de>' into ('Maria Hoffmann', 'maria@kwp.de')."""
    from_header = _decode(from_header)
    name, address = email.utils.parseaddr(from_header)
    return name, address.lower()


def fetch_messages(folder: str = "INBOX", limit: int = 25, unseen_only: bool = False) -> list[dict]:
    """
    Connect to the mailbox and return recent emails in Graph 'message' shape.

    unseen_only=True  -> only emails not yet marked as read
    limit             -> how many recent emails to fetch
    """
    server   = os.environ.get("IMAP_SERVER", "imap.strato.de")
    port     = int(os.environ.get("IMAP_PORT", "993"))
    user     = os.environ["EMAIL_USER"]          # required
    password = os.environ["EMAIL_PASSWORD"]      # required

    messages = []

    imap = imaplib.IMAP4_SSL(server, port)
    try:
        imap.login(user, password)
        imap.select(folder)

        criteria = "UNSEEN" if unseen_only else "ALL"
        status, data = imap.search(None, criteria)
        if status != "OK":
            return messages

        ids = data[0].split()
        ids = ids[-limit:]          # take the most recent `limit` emails

        for num in ids:
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            name, address = _extract_sender(msg.get("From"))
            content, ctype = _get_body(msg)

            # received date -> ISO string
            try:
                received = parsedate_to_datetime(msg.get("Date")).isoformat()
            except Exception:
                received = ""

            messages.append({
                "id": _decode(msg.get("Message-ID")) or num.decode(),
                "receivedDateTime": received,
                "subject": _decode(msg.get("Subject")),
                "from": {"emailAddress": {"name": name, "address": address}},
                "body": {"contentType": ctype, "content": content},
            })
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return messages


if __name__ == "__main__":
    # Test the connection and show what we can see
    msgs = fetch_messages(limit=10)
    print(f"Fetched {len(msgs)} emails from the mailbox:\n")
    for m in msgs:
        sender = m["from"]["emailAddress"]["address"]
        print(f"  {m['receivedDateTime'][:16]:17} | {sender:30} | {m['subject']}")