"""
router.py
---------
Decides which client folder an email belongs to, based on the sender's domain.

How it works:
  - sender: maria.hoffmann@kwp-medtech.de
  - domain:  kwp-medtech.de
  - lookup in clients.json → "KWP"
  - output:  data/KWP/

If the sender's domain is NOT in clients.json:
  - email goes to data/_unassigned/
  - it is NEVER silently dropped — we never lose an email

Adding a new client later:
  - just add one line to clients.json: "newclient-domain.de": "ClientName"
  - no code changes needed
"""

import json
from pathlib import Path

CLIENTS_FILE = Path("clients.json")
DATA_ROOT    = Path("data")
UNASSIGNED   = "_unassigned"


def load_clients() -> dict:
    """Load the domain -> client name mapping from clients.json."""
    return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))


def get_client_folder(sender_address: str) -> Path:
    """
    Given a sender email address, return the Path to that client's data folder.

    Examples:
        maria.hoffmann@kwp-medtech.de  ->  data/KWP/
        unknown@random.com             ->  data/_unassigned/
    """
    clients = load_clients()

    # extract domain from the email address
    if "@" not in sender_address:
        domain = ""
    else:
        domain = sender_address.strip().lower().split("@")[-1]

    client_name = clients.get(domain, UNASSIGNED)

    if client_name == UNASSIGNED:
        print(f"  Router: unknown sender domain '{domain}' -> going to _unassigned/")

    folder = DATA_ROOT / client_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


if __name__ == "__main__":
    # quick self-test
    tests = [
        "maria.hoffmann@kwp-medtech.de",
        "info@xyz-gmbh.de",
        "unknown@random.com",
        "nodomain",
    ]
    for addr in tests:
        folder = get_client_folder(addr)
        print(f"  {addr:40}  ->  {folder}")