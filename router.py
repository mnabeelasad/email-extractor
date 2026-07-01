# """
# router.py
# ---------
# Decides which client folder an email belongs to, based on the sender's domain.

# How it works:
#   - sender: maria.hoffmann@kwp-medtech.de
#   - domain:  kwp-medtech.de
#   - lookup in clients.json → "KWP"
#   - output:  data/KWP/

# If the sender's domain is NOT in clients.json:
#   - email goes to data/_unassigned/
#   - it is NEVER silently dropped — we never lose an email

# Adding a new client later:
#   - just add one line to clients.json: "newclient-domain.de": "ClientName"
#   - no code changes needed
# """

# import json
# from pathlib import Path

# CLIENTS_FILE = Path("clients.json")
# DATA_ROOT    = Path("data")
# UNASSIGNED   = "_unassigned"


# def load_clients() -> dict:
#     """Load the domain -> client name mapping from clients.json."""
#     return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))


# def get_client_folder(sender_address: str) -> Path:
#     """
#     Given a sender email address, return the Path to that client's data folder.

#     Examples:
#         maria.hoffmann@kwp-medtech.de  ->  data/KWP/
#         unknown@random.com             ->  data/_unassigned/
#     """
#     clients = load_clients()

#     # extract domain from the email address
#     if "@" not in sender_address:
#         domain = ""
#     else:
#         domain = sender_address.strip().lower().split("@")[-1]

#     client_name = clients.get(domain, UNASSIGNED)

#     if client_name == UNASSIGNED:
#         print(f"  Router: unknown sender domain '{domain}' -> going to _unassigned/")

#     folder = DATA_ROOT / client_name
#     folder.mkdir(parents=True, exist_ok=True)
#     return folder


# if __name__ == "__main__":
#     # quick self-test
#     tests = [
#         "maria.hoffmann@kwp-medtech.de",
#         "info@xyz-gmbh.de",
#         "unknown@random.com",
#         "nodomain",
#     ]
#     for addr in tests:
#         folder = get_client_folder(addr)
#         print(f"  {addr:40}  ->  {folder}")



#any one send email for kwp-gmbh.de



"""
router.py
---------
Decides which client folder an email belongs to.

Primary signal: the header sender's email domain.
  - sender: maria.hoffmann@kwp-gmbh.de
  - domain:  kwp-gmbh.de
  - lookup in clients.json -> "KWP"
  - output:  data/KWP/

Fallback signal (forwarded/CC'd emails): if the header sender's domain is
NOT a known client (e.g. our colleague forwarded a client email, so the
header sender is our colleague, not the client), we scan the WHOLE email
text (subject + body) for ANY email address belonging to a known client
domain - regardless of who sent it, what name is used, or where in the
email it appears (From: line, signature, CC, quoted text, anywhere).

This means:
  - Anyone forwarding/mentioning a genuine KWP email -> still routes to KWP
  - Unrelated internal emails (no KWP address anywhere) -> _unassigned

If no client domain is found anywhere in the email:
  - it goes to data/_unassigned/
  - it is NEVER silently dropped - we never lose an email

Adding a new client later:
  - just add one line to clients.json: "newclient-domain.de": "ClientName"
  - no code changes needed
"""

import json
import re
from pathlib import Path

CLIENTS_FILE = Path("clients.json")
DATA_ROOT    = Path("data")
UNASSIGNED   = "_unassigned"

# Matches any email address anywhere in text, e.g. "a.plur@kwp-gmbh.de"
EMAIL_PATTERN = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


def load_clients() -> dict:
    """Load the domain -> client name mapping from clients.json."""
    return json.loads(CLIENTS_FILE.read_text(encoding="utf-8"))


def _domain_of(address: str) -> str:
    if not address or "@" not in address:
        return ""
    return address.strip().lower().split("@")[-1]


def find_known_domain_in_text(text: str, known_domains: set) -> str | None:
    """
    Scan arbitrary text (subject + body) for ANY email address whose domain
    matches a known client - no matter who it belongs to or where it
    appears. Returns the matching domain, or None if nothing matches.
    """
    if not text:
        return None
    for match in EMAIL_PATTERN.finditer(text.lower()):
        domain = match.group(1)
        if domain in known_domains:
            return domain
    return None


def get_client_folder(sender_address: str, email_text: str = "") -> Path:
    """
    Given the header sender address (and optionally the full email text -
    subject + body - to catch forwarded/mentioned client emails), return
    the Path to that client's data folder.

    Examples:
        maria.hoffmann@kwp-gmbh.de        -> data/KWP/   (direct)
        unknown@random.com                -> data/_unassigned/
        colleague forwards a KWP email    -> data/KWP/   (found in body)
    """
    clients = load_clients()
    known_domains = set(clients.keys())

    # 1) Try the header sender's domain first.
    domain = _domain_of(sender_address)

    # 2) If that's not a known client, scan the whole email text for ANY
    #    known client domain (covers forwards, CCs, signatures, etc.).
    if domain not in known_domains and email_text:
        found_domain = find_known_domain_in_text(email_text, known_domains)
        if found_domain:
            print(f"  Router: found client domain '{found_domain}' inside the email "
                  f"(header sender was {sender_address})")
            domain = found_domain

    client_name = clients.get(domain, UNASSIGNED)

    if client_name == UNASSIGNED:
        print(f"  Router: no known client domain found -> going to _unassigned/")

    folder = DATA_ROOT / client_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


if __name__ == "__main__":
    # quick self-test
    tests = [
        ("maria.hoffmann@kwp-gmbh.de", ""),
        ("info@xyz-gmbh.de", ""),
        ("unknown@random.com", ""),
        ("christian.schwan@wqs.de",
         "Hi Nabeel,\n\nForwarding this.\n\nVon: Andreas Plur <a.plur@kwp-gmbh.de>\nBetreff: Device info"),
        ("christian.schwan@wqs.de",
         "Hi Nabeel, just an internal note, no KWP mention here."),
        ("random.person@gmail.com",
         "FYI, please also loop in someone@kwp-gmbh.de on this thread."),
    ]
    for addr, body in tests:
        folder = get_client_folder(addr, body)
        print(f"  {addr:30}  ->  {folder}")