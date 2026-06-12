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
    clean_option_for_speech,
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


def get_ssml_for_question(question, speech_override=None):
    """Generate the SSML text for a question.

    If speech_override is provided, use that instead of auto-generating.
    """
    if speech_override:
        return speech_override

    template_id = question.get("template_id")
    if template_id is None:
        template_id = TEMPLATE_SELECT_ONE

    options = build_options_for_ssml(question)
    return build_ssml(question["question_text"], template_id, options)


def generate_audio(ssml_text, output_path, speed=None):
    """Generate MP3 from text using ElevenLabs API. Returns file size in bytes."""
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
    with open(output_path, "wb") as f:
        f.write(response.content)

    return len(response.content)


def generate_for_question(question, state_item=None):
    """Generate audio for a question. Returns (ssml, file_size)."""
    speech_override = None
    speed = None

    if state_item:
        speech_override = state_item.get("speech_override")
        speed = state_item.get("speed_override")

    ssml = get_ssml_for_question(question, speech_override)
    output_path = OUTPUT_DIR / f"{question['item_id']}-question.mp3"
    file_size = generate_audio(ssml, output_path, speed)

    return ssml, file_size
