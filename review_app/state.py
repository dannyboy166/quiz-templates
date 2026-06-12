"""JSON state file for tracking review progress."""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

# Use DATA_DIR env var for Railway volume, fallback to local
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers"))
STATE_FILE = DATA_DIR / "review_state.json"
VOICEOVER_DIR = DATA_DIR

_lock = threading.Lock()


def load_state():
    """Load state from JSON file. Returns empty dict if file doesn't exist."""
    with _lock:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {}


def save_state(state):
    """Write state to JSON file."""
    with _lock:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)


def get_item_state(state, item_id):
    """Get state for one item, with defaults."""
    return state.get(item_id, {
        "status": "pending",
        "speech_override": None,
        "speed_override": None,
        "flag_note": "",
        "generated_at": None,
        "approved_at": None,
    })


def update_item_state(state, item_id, **kwargs):
    """Update fields on one item's state and save."""
    if item_id not in state:
        state[item_id] = {
            "status": "pending",
            "speech_override": None,
            "speed_override": None,
            "flag_note": "",
            "generated_at": None,
            "approved_at": None,
        }
    state[item_id].update(kwargs)
    save_state(state)


def has_audio(item_id):
    """Check if an MP3 file exists for this item."""
    return (VOICEOVER_DIR / f"{item_id}-question.mp3").exists()


def now_iso():
    """Current time as ISO string."""
    return datetime.now().isoformat(timespec="seconds")
