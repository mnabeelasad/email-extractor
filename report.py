"""
report.py
---------
Turns device_info.json into a clean, human-readable .txt file.

This file is what the colleague opens — no Python, no JSON, no terminal.
Just a plain text file with all device fields clearly labelled.

It is called automatically by pipeline.py after every merge, so the .txt
is always up to date. The colleague never needs to run anything.
"""

import json
from pathlib import Path
from datetime import datetime


def _val(value, empty="[ — to be provided by client — ]") -> str:
    """Return the value, or a clear placeholder if empty."""
    if value is None or value == "" or value == []:
        return empty
    return str(value)


def _section(title: str) -> str:
    line = "─" * 50
    return f"\n{title}\n{line}\n"


def generate_txt(json_path: Path) -> Path:
    """
    Read device_info.json and write a matching device_info.txt
    in the same folder. Returns the path to the .txt file.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    client_name = json_path.parent.name
    txt_path    = json_path.parent / "device_info.txt"

    # check for conflicts file
    conflicts_path = json_path.parent / "changes_to_review.json"
    conflicts = []
    if conflicts_path.exists():
        conflicts = json.loads(conflicts_path.read_text(encoding="utf-8"))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    product = data.get("product_name") or "Unknown device"

    lines = []

    # ── Header ────────────────────────────────────────────────────────────
    lines += [
        "═" * 55,
        f"  CLIENT : {client_name}",
        f"  DEVICE : {product}",
        f"  Updated: {now}",
        "═" * 55,
    ]

    # ── General information ────────────────────────────────────────────────
    lines.append(_section("GENERAL INFORMATION"))
    lines += [
        f"Manufacturer     : {_val(data.get('manufacturer'))}",
        f"Product name     : {_val(data.get('product_name'))}",
        f"Article number   : {_val(data.get('article_number_ref'))}",
        f"SRN              : {_val(data.get('srn'))}",
        f"Basic UDI-DI     : {_val(data.get('basic_udi_di'))}",
    ]

    lines.append(_section("DEVICE DESCRIPTION"))
    lines += [
        f"Description      :\n  {_val(data.get('device_description'))}",
        f"\nIntended purpose :\n  {_val(data.get('intended_purpose'))}",
        f"\nIndications      :\n  {_val(data.get('indications'))}",
        f"\nContraindications:\n  {_val(data.get('contraindications'))}",
        f"\nWarnings         :\n  {_val(data.get('warnings'))}",
    ]

    # ── Classification ────────────────────────────────────────────────────
    lines.append(_section("CLASSIFICATION"))
    lines += [
        f"Classification   : {_val(data.get('classification'))}",
        f"Rule             : {_val(data.get('rule'))}",
    ]

    # ── Codes ─────────────────────────────────────────────────────────────
    lines.append(_section("CODES"))
    lines += [
        f"EMDN             : {_val(data.get('code_emdn'))}",
        f"GMDN             : {_val(data.get('code_gmdn'))}",
        f"MDR              : {_val(data.get('code_mdr'))}",
    ]

    # ── Variants ──────────────────────────────────────────────────────────
    lines.append(_section("VARIANTS"))
    variants = data.get("variants") or []
    if variants:
        for i, v in enumerate(variants, 1):
            art  = v.get("art_no")    or "—"
            name = v.get("product_name") or "—"
            lines.append(f"  {i}. {name}  |  REF: {art}")
    else:
        lines.append("  [ — to be provided by client — ]")

    # ── Device characteristics ────────────────────────────────────────────
    lines.append(_section("DEVICE CHARACTERISTICS"))
    lines += [
        f"Previous generations    :\n  {_val(data.get('previous_generations'))}",
        f"\nInnovative properties   :\n  {_val(data.get('innovative_properties'))}",
        f"\nAccessories             :\n  {_val(data.get('accessories'))}",
        f"\nProducts for combined use:\n  {_val(data.get('products_for_combined_use'))}",
    ]

    # ── Application specifications ────────────────────────────────────────
    lines.append(_section("APPLICATION SPECIFICATIONS"))
    lines += [
        f"Patient population :\n  {_val(data.get('patient_population'))}",
        f"\nIntended users     :\n  {_val(data.get('intended_users'))}",
        f"\nDescription of use :\n  {_val(data.get('description_of_use'))}",
    ]

    # ── Labeling ──────────────────────────────────────────────────────────
    lines.append(_section("LABELING"))
    lines.append(f"Special labeling   :\n  {_val(data.get('special_labeling'))}")

    # ── Conflicts / changes to review ─────────────────────────────────────
    if conflicts:
        lines.append(_section("⚠  CHANGES TO REVIEW  ⚠"))
        lines.append("The following values arrived from a new email but differ from")
        lines.append("what was already saved. Please check and update manually.\n")
        for c in conflicts:
            lines += [
                f"  Field        : {c.get('field')}",
                f"  Current value: {c.get('current_value')}",
                f"  New value    : {c.get('new_value')}",
                f"  From email   : {c.get('from')}",
                f"  Date         : {c.get('date')}",
                "  " + "·" * 40,
            ]

    # ── Footer ────────────────────────────────────────────────────────────
    lines += [
        "\n" + "═" * 55,
        "  This file is generated automatically.",
        "  Do not edit — changes will be overwritten.",
        "  To update data: wait for the next client email.",
        "═" * 55,
    ]

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    return txt_path


if __name__ == "__main__":
    # Run directly to regenerate .txt for all known clients
    from pathlib import Path
    data_root = Path("data")
    found = list(data_root.rglob("device_info.json"))
    if not found:
        print("No device_info.json files found. Run process_inbox.py first.")
    for json_path in found:
        txt_path = generate_txt(json_path)
        print(f"Generated: {txt_path}")