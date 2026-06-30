"""
process_inbox.py
----------------
Main script. Reads emails from the real mailbox (IMAP), and runs each one
through the pipeline (classify -> extract -> merge -> report -> notify).

It remembers which message ids it already processed (per client), so running
it again will NOT re-process the same emails.

Run:
    python process_inbox.py          # real mailbox (default)
    python process_inbox.py test     # read from test_emails/*.txt (offline test)
"""

import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from bs4 import BeautifulSoup

from router import get_client_folder
from pipeline import process_email


def html_to_text(html: str) -> str:
    """Turn messy HTML email content into clean plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    return "\n".join(line for line in lines if line)


def message_to_text(msg: dict) -> str:
    """Turn a Graph/IMAP message into the plain text we feed the model."""
    subject = msg.get("subject", "")
    body_obj = msg.get("body", {})
    content = body_obj.get("content", "")
    if body_obj.get("contentType", "text").lower() == "html":
        content = html_to_text(content)
    return f"Subject: {subject}\n\n{content}"


def load_messages(source: str) -> list[dict]:
    """source = 'real' -> IMAP mailbox.  source = 'test' -> test_emails/*.txt"""
    if source == "test":
        import uuid
        test_folder = Path("test_emails")
        if not test_folder.exists():
            print("No test_emails/ folder found.")
            return []
        print("Reading from test_emails/ folder...")
        messages = []
        for txt_file in sorted(test_folder.glob("*.txt")):
            content = txt_file.read_text(encoding="utf-8")
            sender, subject = "test@kwp-gmbh.de", txt_file.stem
            for line in content.splitlines()[:5]:
                if line.startswith("From:"):
                    sender = line.replace("From:", "").strip()
                elif line.startswith("Subject:"):
                    subject = line.replace("Subject:", "").strip()
            messages.append({
                "id": "TEST" + uuid.uuid4().hex,
                "receivedDateTime": "2026-06-25T10:00:00Z",
                "subject": subject,
                "from": {"emailAddress": {"name": sender.split("@")[0], "address": sender}},
                "body": {"contentType": "text", "content": content},
            })
        return messages

    # default: real mailbox
    from email_reader import fetch_messages
    print("Reading from the REAL mailbox (IMAP)...")
    return fetch_messages(limit=25)


def load_processed_ids(client_folder: Path) -> set:
    path = client_folder / "processed_ids.json"
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return set()


def save_processed_ids(client_folder: Path, ids: set) -> None:
    (client_folder / "processed_ids.json").write_text(
        json.dumps(sorted(ids), indent=2), encoding="utf-8"
    )


def main(source: str = "real"):
    messages = load_messages(source)
    if not messages:
        return
    messages.sort(key=lambda m: m.get("receivedDateTime", ""))   # oldest first

    processed_by_client: dict[str, set] = {}
    new_count = 0

    for msg in messages:
        mid = msg["id"]
        sender = msg["from"]["emailAddress"]["address"]
        subject = msg.get("subject", "")

        # 1. which client does this sender belong to?
        client_folder = get_client_folder(sender)
        client_key = str(client_folder)

        if client_key not in processed_by_client:
            processed_by_client[client_key] = load_processed_ids(client_folder)
        processed = processed_by_client[client_key]

        # 2. skip if already seen
        if mid in processed:
            print(f"\n--- Already processed, skipping: {subject} ---")
            continue

        print(f"\n--- New email from {sender} ({client_folder.name}) ---")

        # 3. unknown sender -> save raw, do NOT extract
        if client_folder.name == "_unassigned":
            raw_path = client_folder / "unassigned_emails.json"
            existing = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
            existing.append({
                "received": msg.get("receivedDateTime"),
                "from": sender,
                "subject": subject,
                "body": msg.get("body", {}).get("content", "")[:500],
            })
            raw_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Unknown sender -> saved to _unassigned/ (add '{sender.split('@')[-1]}' to clients.json if real client)")
            processed.add(mid)
            new_count += 1
            continue

        # 4. known client -> classify -> extract -> merge -> report -> notify
        process_email(message_to_text(msg), label=subject,
                      output_path=client_folder / "device_info.json")
        processed.add(mid)
        new_count += 1

    for client_key, ids in processed_by_client.items():
        save_processed_ids(Path(client_key), ids)

    print(f"\nDone. Processed {new_count} new email(s).")


if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else "real"
    main(source)