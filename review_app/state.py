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
    """Write state to JSON file atomically (temp file + replace).

    Atomic so a concurrent reader/writer never sees a half-written file and a
    crash mid-write can't corrupt the ledger (two reviewers using the app at once).
    """
    with _lock:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        tmp.replace(STATE_FILE)


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


# --- Hint state ---

DEFAULT_HINT_STATE = {
    "status": "pending",
    "mode": "audio_text",
    "speech_override": None,
    "speed_override": None,
    "flag_note": "",
    "generated_at": None,
    "approved_at": None,
}


def get_hint_state(state, item_id, hint_num):
    """Get state for one hint, with defaults."""
    item = state.get(item_id, {})
    hints = item.get("hints", {})
    return hints.get(f"hint{hint_num}", dict(DEFAULT_HINT_STATE))


def update_hint_state(state, item_id, hint_num, **kwargs):
    """Update fields on one hint's state and save."""
    if item_id not in state:
        state[item_id] = {
            "status": "pending",
            "speech_override": None,
            "speed_override": None,
            "flag_note": "",
            "generated_at": None,
            "approved_at": None,
        }
    if "hints" not in state[item_id]:
        state[item_id]["hints"] = {}
    key = f"hint{hint_num}"
    if key not in state[item_id]["hints"]:
        state[item_id]["hints"][key] = dict(DEFAULT_HINT_STATE)
    state[item_id]["hints"][key].update(kwargs)
    save_state(state)


def has_hint_audio(item_id, hint_num):
    """Check if a hint MP3 file exists."""
    return (VOICEOVER_DIR / f"{item_id}-hint{hint_num}.mp3").exists()


# --- Per-option audio state (Phase 3) ---

DEFAULT_OPTION_STATE = {
    "status": "pending",
    "speech_override": None,
    "speed_override": None,
    "flag_note": "",
    "generated_at": None,
    "approved_at": None,
}


def get_option_state(state, item_id, option_num):
    """Get state for one option's voice-over, with defaults."""
    item = state.get(item_id, {})
    opts = item.get("options", {})
    return opts.get(f"option{option_num}", dict(DEFAULT_OPTION_STATE))


def update_option_state(state, item_id, option_num, **kwargs):
    """Update fields on one option's VO state and save."""
    if item_id not in state:
        state[item_id] = {
            "status": "pending",
            "speech_override": None,
            "speed_override": None,
            "flag_note": "",
            "generated_at": None,
            "approved_at": None,
        }
    if "options" not in state[item_id]:
        state[item_id]["options"] = {}
    key = f"option{option_num}"
    if key not in state[item_id]["options"]:
        state[item_id]["options"][key] = dict(DEFAULT_OPTION_STATE)
    state[item_id]["options"][key].update(kwargs)
    save_state(state)


def has_option_audio(item_id, option_num):
    """Check if a per-option MP3 file exists."""
    return (VOICEOVER_DIR / f"{item_id}-option{option_num}.mp3").exists()


def now_iso():
    """Current time as ISO string."""
    return datetime.now().isoformat(timespec="seconds")
