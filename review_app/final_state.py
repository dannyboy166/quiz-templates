"""JSON state for Final Stage 'approved for upload' tracking.

Separate file from voiceover/image state so nothing collides. Records which questions
a reviewer has marked Final Approved (only allowed when all completeness gates pass),
plus who/when. This is the source for the upload manifest — the terminal uploader
(built later) reads approved questions from here and inserts them into Victor's DB.

The app NEVER writes to Victor's DB. This is purely an approval ledger on the volume.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

# Store next to the voiceover state on the Railway volume.
_DATA_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers"))
FINAL_STATE_FILE = _DATA_DIR / "final_state.json"

_lock = threading.Lock()


def load_final_state():
    """Load approval ledger. {item_id: {approved, approved_at, approved_by, uploaded_at}}."""
    with _lock:
        if FINAL_STATE_FILE.exists():
            with open(FINAL_STATE_FILE) as f:
                return json.load(f)
        return {}


def _save(state):
    FINAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FINAL_STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(FINAL_STATE_FILE)  # atomic write — never leave a half-written ledger


def get_final_item(state, item_id):
    return state.get(item_id, {
        "approved": False,
        "approved_at": None,
        "approved_by": None,
        "uploaded_at": None,
    })


def set_approved(state, item_id, approved, by=None):
    """Mark (or unmark) a question as Final Approved. Returns the updated ledger."""
    with _lock:
        item = state.get(item_id, {})
        item["approved"] = bool(approved)
        if approved:
            item["approved_at"] = _now()
            item["approved_by"] = by
        else:
            item["approved_at"] = None
            item["approved_by"] = None
        state[item_id] = item
        _save(state)
    return item


def mark_uploaded(state, item_id):
    """Record that an approved question has been uploaded to the DB (set by the uploader)."""
    with _lock:
        item = state.get(item_id, {})
        item["uploaded_at"] = _now()
        state[item_id] = item
        _save(state)
    return item


def approved_ids(state):
    return [iid for iid, v in state.items() if v.get("approved")]


def _now():
    return datetime.now().isoformat(timespec="seconds")
