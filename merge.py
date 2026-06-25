"""
merge.py
--------
Combine a newly-extracted device form into the existing source of truth.

Simple + safe rule:
  - Master field is EMPTY and the new email has a value   -> FILL it.
  - Master field already filled, new email repeats it      -> leave it.
  - Master field already filled, new email has a DIFFERENT
    value (a client correction)                            -> do NOT overwrite.
        Save it to "changes_to_review.json" for a human to decide.
  - New email says nothing (null) about a field            -> ignore.

So we never lose old data and never silently change an existing value.
"""

import json
from pathlib import Path
from datetime import datetime

from schema import DeviceInfo


def _is_empty(value) -> bool:
    return value in (None, "", [])


def load_existing(path: Path) -> DeviceInfo:
    """Load the current source of truth, or an empty form if none exists yet."""
    if path.exists():
        return DeviceInfo(**json.loads(path.read_text(encoding="utf-8")))
    return DeviceInfo()


def merge_into_source_of_truth(new: DeviceInfo, path: Path, source_label: str = "new email"):
    master_data = load_existing(path).model_dump()
    new_data = new.model_dump()

    filled = []        # blanks we filled this time
    conflicts = []     # values that differ and need a human to decide

    for field, new_value in new_data.items():
        if _is_empty(new_value):
            continue                                   # new email says nothing here
        old_value = master_data.get(field)
        if _is_empty(old_value):
            master_data[field] = new_value             # fill the blank
            filled.append(field)
        elif old_value != new_value:
            conflicts.append({                         # different -> review, don't overwrite
                "field": field,
                "current_value": old_value,
                "new_value": new_value,
                "from": source_label,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        # else: same value -> nothing to do

    # save the updated master
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DeviceInfo(**master_data).model_dump_json(indent=2), encoding="utf-8")

    # append any conflicts to a separate review file
    if conflicts:
        review_path = path.parent / "changes_to_review.json"
        existing = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else []
        existing.extend(conflicts)
        review_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return filled, conflicts