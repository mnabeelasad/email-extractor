"""
process_inbox.py
----------------
Read emails (Graph 'message' shape) and run each one through the pipeline
(classify -> extract -> merge).

Right now the emails come from data/fake_inbox.json (made by make_fake_inbox.py).
Later, the real Outlook/Graph reader will hand over messages in the SAME shape,
and THIS file will not need to change.

It remembers which message ids it already processed (per client), so running
it again will NOT re-process the same emails.

Run:
    python process_inbox.py
"""

import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()                                    # load .env (GEMINI_API_KEY, EMAIL_*, ...)

from bs4 import BeautifulSoup

from router import get_client_folder          # domain -> data/ClientName/
from pipeline import process_email            # classify -> extract -> merge

INBOX_PATH = Path("data/fake_inbox.json")


def html_to_text(html: str) -> str:
    """Turn messy HTML email content into clean plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    return "\n".join(line for line in lines if line)


def message_to_text(msg: dict) -> str:
    """Turn a Graph message into plain text for the model."""
    subject = msg.get("subject", "")
    body_obj = msg.get("body", {})
    content  = body_obj.get("content", "")
    if body_obj.get("contentType", "text").lower() == "html":
        content = html_to_text(content)
    return f"Subject: {subject}\n\n{content}"


def load_processed_ids(client_folder: Path) -> set:
    path = client_folder / "processed_ids.json"
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return set()


def save_processed_ids(client_folder: Path, ids: set) -> None:
    path = client_folder / "processed_ids.json"
    path.write_text(json.dumps(sorted(ids), indent=2), encoding="utf-8")


def load_messages(source: str) -> list[dict]:
    """
    Get emails as a list of Graph-shaped messages.
      source = "fake"  -> read from data/fake_inbox.json (testing)
      source = "real"  -> read from the real mailbox over IMAP
    """
    if source == "real":
        from email_reader import fetch_messages
        print("Reading from the REAL mailbox (IMAP)...")
        return fetch_messages(limit=25)

    # default: fake inbox
    if not INBOX_PATH.exists():
        print(f"No inbox found at {INBOX_PATH}. Run: python make_fake_inbox.py")
        return []
    print("Reading from the FAKE inbox (data/fake_inbox.json)...")
    return json.loads(INBOX_PATH.read_text(encoding="utf-8"))


def main(source: str = "fake"):
    messages = load_messages(source)
    if not messages:
        return
    messages.sort(key=lambda m: m.get("receivedDateTime", ""))  # oldest first

    # load processed ids per client (we'll update as we go)
    processed_by_client: dict[str, set] = {}
    new_count = 0

    for msg in messages:
        mid    = msg["id"]
        sender = msg["from"]["emailAddress"]["address"]
        subject = msg.get("subject", "")

        # 1. which client does this sender belong to?
        client_folder = get_client_folder(sender)
        client_key    = str(client_folder)

        # load this client's processed ids (once per client)
        if client_key not in processed_by_client:
            processed_by_client[client_key] = load_processed_ids(client_folder)

        processed = processed_by_client[client_key]

        # 2. skip if already seen
        if mid in processed:
            print(f"\n--- Already processed, skipping: {subject} ---")
            continue

        print(f"\n--- New email from {sender} ({client_folder.name}) ---")

        # 3. UNASSIGNED: unknown sender — save raw email, do NOT extract
        #    A human must first confirm who this is and add them to clients.json
        if client_folder.name == "_unassigned":
            raw_path = client_folder / "unassigned_emails.json"
            existing = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
            existing.append({
                "received": msg.get("receivedDateTime"),
                "from": sender,
                "subject": subject,
                "body": msg.get("body", {}).get("content", "")[:500],  # first 500 chars
            })
            raw_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  ⚠ Unknown sender — saved to _unassigned/unassigned_emails.json")
            print(f"    Add '{sender.split('@')[-1]}' to clients.json if this is a real client.")
            processed.add(mid)
            new_count += 1
            continue

        # 4. known client: classify -> extract -> merge
        output_path = client_folder / "device_info.json"
        process_email(
            message_to_text(msg),
            label=subject,
            output_path=output_path,         # each client has its own file
        )

        processed.add(mid)
        new_count += 1

    # save updated processed ids for every client we touched
    for client_key, ids in processed_by_client.items():
        save_processed_ids(Path(client_key), ids)

    print(f"\nDone. Processed {new_count} new email(s).")


if __name__ == "__main__":
    import sys
    # default is "fake"; run `python process_inbox.py real` to use the mailbox
    source = sys.argv[1] if len(sys.argv) > 1 else "fake"
    main(source)