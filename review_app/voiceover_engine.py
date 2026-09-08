"""Wrapper around generate_voiceovers.py functions for the review app."""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure project root is on path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load .env
load_dotenv(project_root / ".env")

# Import the text transformation and SSML functions
from scripts.bulk_import.generate_voiceovers import (
    clean_text_for_speech,
    clean_option_for_speech,  # noqa: F401 (used by generate_for_option)
    build_ssml,
    should_read_options,
    is_yes_no,
    API_SETTINGS,
    TEMPLATE_SELECT_ONE,
    TEMPLATE_SELECT_ALL,
    TEMPLATE_TRUE_FALSE,
)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "cupfa8uelkW7cWxLMRa7")
OUTPUT_DIR = Path(os.environ.get("DATA_DIR", project_root / "data" / "voiceovers"))


def build_options_for_ssml(question):
    """Convert spreadsheet question dict to the options format build_ssml expects."""
    options = []
    for i in range(1, 5):
        opt_text = question.get(f"option{i}", "")
        if opt_text:
            options.append({"text": str(opt_text), "image_blob_id": None})
    return options


def get_ssml_for_question(question, speech_override=None, no_answers=False):
    """Generate the SSML text for a question.

    If speech_override is provided, use that instead of auto-generating.
    If no_answers is True, only read the question text without options.
    """
    if speech_override:
        return speech_override

    template_id = question.get("template_id")
    if template_id is None:
        template_id = TEMPLATE_SELECT_ONE

    if no_answers:
        cleaned = clean_text_for_speech(question["question_text"])
        return f'<break time="0.3s" /> {cleaned}'

    options = build_options_for_ssml(question)
    return build_ssml(question["question_text"], template_id, options)


MAX_AUDIO_VERSIONS = 5  # keep the last 5 previous takes of each audio file for revert


def _archive_audio(output_path):
    """Before overwriting an MP3, copy the current one to a versioned backup.

    Keeps the last MAX_AUDIO_VERSIONS as {stem}-v{N}.mp3 (v1 = oldest kept). Lets a
    reviewer revert to a previous take if they don't like a regeneration.
    """
    import shutil
    output_path = Path(output_path)
    if not output_path.exists():
        return
    stem = output_path.stem  # e.g. "20012002-option3"
    parent = output_path.parent
    existing = sorted(parent.glob(f"{stem}-v*.mp3"))
    next_num = len(existing) + 1
    if next_num > MAX_AUDIO_VERSIONS:
        # rotate: drop oldest, shift the rest down
        for i, vf in enumerate(existing):
            if i == 0:
                vf.unlink()
            else:
                vf.rename(parent / vf.name.replace(f"-v{i+1}.", f"-v{i}."))
        next_num = MAX_AUDIO_VERSIONS
    shutil.copy2(output_path, parent / f"{stem}-v{next_num}.mp3")


def get_audio_versions(stem):
    """List version files for an audio stem (e.g. '20012002-option3'), oldest→newest."""
    return sorted(OUTPUT_DIR.glob(f"{stem}-v*.mp3"))


def restore_audio_version(stem, version_num):
    """Restore {stem}-v{N}.mp3 as the current {stem}.mp3 (archives current first)."""
    import shutil
    current = OUTPUT_DIR / f"{stem}.mp3"
    version = OUTPUT_DIR / f"{stem}-v{version_num}.mp3"
    if not version.exists():
        raise FileNotFoundError(f"Version {version_num} not found for {stem}")
    _archive_audio(current)  # keep the current take too
    shutil.copy2(version, current)
    return current


def generate_audio(ssml_text, output_path, speed=None):
    """Generate MP3 from text using ElevenLabs API. Returns file size in bytes.

    Archives the previous take (if any) before overwriting, so it can be reverted.
    """
    if not ELEVENLABS_API_KEY:
        raise Exception("ELEVENLABS_API_KEY not set in .env")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": ssml_text,
        "model_id": API_SETTINGS["model_id"],
        "voice_settings": API_SETTINGS["voice_settings"],
        "speed": speed or API_SETTINGS["speed"],
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"ElevenLabs API error {response.status_code}: {response.text}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _archive_audio(output_path)  # keep the old take before overwriting
    with open(output_path, "wb") as f:
        f.write(response.content)

    return len(response.content)


def generate_for_question(question, state_item=None, no_answers=False):
    """Generate audio for a question. Returns (ssml, file_size)."""
    speech_override = None
    speed = None

    if state_item:
        speech_override = state_item.get("speech_override")
        speed = state_item.get("speed_override")

    ssml = get_ssml_for_question(question, speech_override, no_answers=no_answers)
    output_path = OUTPUT_DIR / f"{question['item_id']}-question.mp3"
    file_size = generate_audio(ssml, output_path, speed)

    return ssml, file_size


# --- Hint audio ---

def get_ssml_for_hint(hint_text, speech_override=None):
    """Generate SSML for a hint. Simpler than questions — no options or T/F."""
    if speech_override:
        return speech_override
    cleaned = clean_text_for_speech(hint_text)
    return f'<break time="0.3s" /> {cleaned}'


def generate_for_hint(question, hint_num, hint_state=None):
    """Generate audio for a hint. Returns (ssml, file_size)."""
    hint_text = question.get(f"hint{hint_num}", "")
    if not hint_text:
        raise Exception(f"No hint{hint_num} text for {question['item_id']}")

    speech_override = None
    speed = None
    if hint_state:
        speech_override = hint_state.get("speech_override")
        speed = hint_state.get("speed_override")

    ssml = get_ssml_for_hint(hint_text, speech_override)
    output_path = OUTPUT_DIR / f"{question['item_id']}-hint{hint_num}.mp3"
    file_size = generate_audio(ssml, output_path, speed)

    return ssml, file_size


# --- Per-option audio (Phase 3: reads a single answer option aloud) ---
# Target DB column: SelectionOption.ReaderBlobID (verified in Victor's schema).
# Naming: {item_id}-option{n}.mp3 (distinct from -question / -hint files).

def get_ssml_for_option(option_text, speech_override=None):
    """SSML for reading a single answer option aloud."""
    if speech_override:
        return speech_override
    cleaned = clean_option_for_speech(str(option_text))
    return f'<break time="0.3s" /> {cleaned}'


def generate_for_option(question, option_num, option_state=None):
    """Generate audio that reads one answer option aloud. Returns (ssml, file_size).

    option_num is 1..4. Raises if that option has no text.
    """
    option_text = question.get(f"option{option_num}", "")
    if not option_text:
        raise Exception(f"No option{option_num} text for {question['item_id']}")

    speech_override = None
    speed = None
    if option_state:
        speech_override = option_state.get("speech_override")
        speed = option_state.get("speed_override")

    ssml = get_ssml_for_option(option_text, speech_override)
    output_path = OUTPUT_DIR / f"{question['item_id']}-option{option_num}.mp3"
    file_size = generate_audio(ssml, output_path, speed)

    return ssml, file_size
