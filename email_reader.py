"""
email_reader.py
---------------
Reads emails from a mailbox over IMAP (e.g. Strato) and returns them in
Graph 'message' shape.

NEW: If an email body is empty but has .msg attachments (forwarded Outlook
emails), it opens each .msg and treats it as a separate message. This means
Christian can just forward KWP emails as-is — no manual copy-paste needed.

Settings (.env):
    IMAP_SERVER=imap.strato.de
    IMAP_PORT=993
    EMAIL_USER=nabeel.asad@wqs.de
    EMAIL_PASSWORD=your-password

Run to test:
    python email_reader.py
"""

import os
import io
import email
import imaplib
import tempfile
from email.header import decode_header
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
load_dotenv()


# ── Header / text helpers ────────────────────────────────────────────────

def _decode(value) -> str:
    """Decode an email header (handles =?UTF-8?= encoded subjects)."""
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


def _extract_sender(from_header: str) -> tuple[str, str]:
    """'Maria Hoffmann <maria@kwp.de>' -> ('Maria Hoffmann', 'maria@kwp.de')"""
    from_header = _decode(from_header)
    name, address = email.utils.parseaddr(from_header)
    return name, address.lower()


def _get_body(msg) -> tuple[str, str]:
    """Return (body_text, content_type). Prefers plain text, falls back to HTML."""
    plain = None
    html = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp  = str(part.get("Content-Disposition") or "")
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


def _body_is_empty(content: str) -> bool:
    """True if the body has no real content (just whitespace/signature)."""
    # strip whitespace + common Outlook signature markers
    stripped = content.strip()
    if not stripped:
        return True
    # if body is only a signature block (very short and no field-like content)
    if len(stripped) < 80 and all(
        kw not in stripped.lower()
        for kw in ["product", "manufacturer", "ref", "article", "device",
                   "purpose", "classification", "variants", "udi", "srn"]
    ):
        return True
    return False


# ── .msg attachment extractor ────────────────────────────────────────────

def _extract_msg_attachments(raw_email: bytes) -> list[dict]:
    """
    Look for .msg attachments in an email. For each one found, open it with
    extract-msg and return a Graph-shaped message dict.

    This handles the case where Christian forwards KWP emails as Outlook items
    (.msg files) — the system reads them automatically without any manual work.
    """
    results = []
    msg = email.message_from_bytes(raw_email)

    for part in msg.walk():
        filename = part.get_filename() or ""
        if not filename.lower().endswith(".msg"):
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        try:
            import extract_msg as em

            # extract-msg needs a file path — write to a temp file
            with tempfile.NamedTemporaryFile(suffix=".msg", delete=False) as tmp:
                tmp.write(payload)
                tmp_path = tmp.name

            try:
                outlook_msg = em.openMsg(tmp_path)
                sender_name    = outlook_msg.sender or ""
                sender_address = (outlook_msg.senderEmail or "").lower()
                subject        = outlook_msg.subject or ""
                body           = outlook_msg.body   or ""
                received       = ""
                if outlook_msg.date:
                    try:
                        received = outlook_msg.date.isoformat()
                    except Exception:
                        received = str(outlook_msg.date)

                if sender_address and body.strip():
                    results.append({
                        "id": f"msg-attachment-{hash(payload)}",
                        "receivedDateTime": received,
                        "subject": subject,
                        "from": {"emailAddress": {
                            "name": sender_name,
                            "address": sender_address,
                        }},
                        "body": {"contentType": "text", "content": body},
                    })
                    print(f"    [.msg] Found attached email: '{subject}' from {sender_address}")
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            print(f"    [.msg] Could not read attachment '{filename}': {e}")

    return results


# ── Main IMAP fetcher ────────────────────────────────────────────────────

def fetch_messages(folder: str = "INBOX",
                   limit: int = 25,
                   unseen_only: bool = False) -> list[dict]:
    """
    Connect to IMAP and return emails in Graph 'message' shape.

    If an email body is empty but contains .msg attachments, the attachments
    are opened and returned as separate messages (with original KWP senders).
    """
    server   = os.environ.get("IMAP_SERVER", "imap.strato.de")
    port     = int(os.environ.get("IMAP_PORT", "993"))
    user     = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASSWORD"]

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
        ids = ids[-limit:]

        for num in ids:
            status, msg_data = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            name, address = _extract_sender(msg.get("From"))
            content, ctype = _get_body(msg)

            try:
                received = parsedate_to_datetime(msg.get("Date")).isoformat()
            except Exception:
                received = ""

            msg_id = _decode(msg.get("Message-ID")) or num.decode()

            # Case 1: body has real content — use it directly
            if not _body_is_empty(content):
                messages.append({
                    "id": msg_id,
                    "receivedDateTime": received,
                    "subject": _decode(msg.get("Subject")),
                    "from": {"emailAddress": {"name": name, "address": address}},
                    "body": {"contentType": ctype, "content": content},
                })

            # Case 2: body is empty → check for .msg attachments
            else:
                attached = _extract_msg_attachments(raw)
                if attached:
                    messages.extend(attached)
                else:
                    # no .msg found either — still add so dedup records it
                    messages.append({
                        "id": msg_id,
                        "receivedDateTime": received,
                        "subject": _decode(msg.get("Subject")),
                        "from": {"emailAddress": {"name": name, "address": address}},
                        "body": {"contentType": "text", "content": content},
                    })

    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return messages


if __name__ == "__main__":
    msgs = fetch_messages(limit=15)
    print(f"\nFetched {len(msgs)} messages:\n")
    for m in msgs:
        sender = m["from"]["emailAddress"]["address"]
        print(f"  {m['receivedDateTime'][:16]:17} | {sender:35} | {m['subject'][:50]}")