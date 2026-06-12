"""JSON state file for tracking image generation progress."""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

IMAGE_DATA_DIR = Path(os.environ.get("IMAGE_DATA_DIR", "data/images_generated")).resolve()
IMAGE_STATE_FILE = IMAGE_DATA_DIR / "image_state.json"

_lock = threading.Lock()


def _default_image_slot():
    """Default state for a single image slot (question or answer)."""
    return {
        "prompt": "",
        "generated_at": None,
        "approved_at": None,
        "pushed_at": None,
    }


def _default_item():
    """Default state for a question's image generation."""
    return {
        "status": "pending",
        "question_image": _default_image_slot(),
        "answer_images": {
            "1": _default_image_slot(),
            "2": _default_image_slot(),
            "3": _default_image_slot(),
            "4": _default_image_slot(),
        },
        "flag_note": "",
    }


def load_image_state():
    """Load state from JSON file. Returns empty dict if file doesn't exist."""
    with _lock:
        if IMAGE_STATE_FILE.exists():
            with open(IMAGE_STATE_FILE) as f:
                return json.load(f)
        return {}


def save_image_state(state):
    """Write state to JSON file."""
    with _lock:
        IMAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(IMAGE_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)


def get_image_item_state(state, item_id):
    """Get state for one item, with defaults."""
    if item_id in state:
        return state[item_id]
    return _default_item()


def update_image_item_state(state, item_id, **kwargs):
    """Update fields on one item's image state and save."""
    if item_id not in state:
        state[item_id] = _default_item()
    state[item_id].update(kwargs)
    save_image_state(state)


def has_question_image(item_id):
    """Check if a question image PNG exists for this item."""
    return (IMAGE_DATA_DIR / f"{item_id}-question.png").exists()


def has_answer_image(item_id, option_num):
    """Check if an answer image PNG exists for this item+option."""
    return (IMAGE_DATA_DIR / f"{item_id}-answer{option_num}.png").exists()


def now_iso():
    """Current time as ISO string."""
    return datetime.now().isoformat(timespec="seconds")
