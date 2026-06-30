"""
pipeline.py
-----------
Full flow for one email:

  1. classify  -> does this email contain device data?  (cheap yes/no)
  2. NO  -> skip (no extraction, nothing saved)
  3. YES -> extract (fill the form)
  4. safety net -> if the form is still empty, don't save it anyway
  5. merge -> into the right client's device_info.json
  6. report -> regenerate the human-readable device_info.txt
  7. notify -> email the colleague if there are conflicts
"""

from pathlib import Path

from schema import DeviceInfo
from classify import is_device_data_email
from extract import build_prompt, call_model, parse_model_output
from merge import merge_into_source_of_truth
from report import generate_txt
from notify import send_conflict_notification

DEFAULT_OUTPUT = Path("data/KWP/device_info.json")


def has_data(device: DeviceInfo) -> bool:
    """True if the model actually filled in at least one field."""
    for key, value in device.model_dump().items():
        if key == "variants":
            if value:
                return True
        elif value not in (None, ""):
            return True
    return False


def process_email(email_text: str, label: str = "email", output_path: Path = DEFAULT_OUTPUT) -> None:
    print(f"\n=== Processing: {label} ===")

    # Step 1: cheap yes/no gate
    if not is_device_data_email(email_text):
        print("  Filter: NO device data  ->  SKIPPED (no extraction).")
        return

    print("  Filter: YES, looks like device data  ->  extracting...")

    # Step 2: extract
    device = parse_model_output(call_model(build_prompt(email_text)))

    # Step 3: safety net
    if not has_data(device):
        print("  Extraction came back empty  ->  NOT saved (safety net).")
        return

    # Step 4: merge into the correct client file
    client_name = output_path.parent.name
    filled, conflicts = merge_into_source_of_truth(device, output_path, source_label=label)
    print(f"  Merged into {output_path}")
    print(f"    - filled {len(filled)} empty field(s)")

    if conflicts:
        print(f"    - WARNING: {len(conflicts)} value(s) differ -> saved to changes_to_review.json")
        send_conflict_notification(client_name, conflicts, label)

    # Step 5: regenerate the human-readable .txt for the colleague
    txt_path = generate_txt(output_path)
    print(f"    - report updated: {txt_path}")