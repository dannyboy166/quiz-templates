"""OpenAI image generation wrapper for the review app."""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

IMAGE_DATA_DIR = Path(os.environ.get("IMAGE_DATA_DIR", "data/images_generated")).resolve()

_client = None


def _get_client():
    global _client
    if _client is None:
        if OpenAI is None:
            raise Exception("openai package not installed. Run: pip install openai")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY not set in .env")
        _client = OpenAI(api_key=api_key)
    return _client


STYLE_SUFFIX = (
    "Simple, colorful cartoon illustration style suitable for children ages 5-12. "
    "White or plain background. No text, no writing, no numbers, no letters, no labels."
)


def build_question_prompt(q, airtable_desc=None):
    """Build an image generation prompt from a question dict.

    Priority for description source:
    1. Airtable description (from Georgia's existing work)
    2. Spreadsheet image_description column
    3. Placeholder asking Georgia to write the prompt

    Args:
        q: question dict from spreadsheet
        airtable_desc: description from Airtable record (if exists)
    """
    # Try Airtable description first (e.g. "The sun is hot")
    desc = ""
    if airtable_desc:
        desc = airtable_desc.strip()

    # Fall back to spreadsheet ImageDescription
    if not desc:
        desc = q.get("image_description", "").strip()

    # No description anywhere — show placeholder for Georgia
    if not desc:
        q_text = q.get("question_text", "")[:120]
        return (
            f"[Edit this prompt] Describe the image you need for this question: "
            f"\"{q_text}\""
        )

    return f"{desc}. {STYLE_SUFFIX}"


def build_answer_prompt(q, option_num, option_text):
    """Build an image generation prompt for a single answer option."""
    if not option_text or option_text.strip() in ("", "True", "False"):
        return ""

    return (
        f"A cartoon illustration of: {option_text}. "
        f"Single object or concept, centered. {STYLE_SUFFIX}"
    )


def generate_image(prompt, output_path, size="1024x1024", quality="low"):
    """Generate an image via OpenAI API and save to output_path.

    Returns file size in bytes. Uses quality='low' by default ($0.02/image).
    """
    client = _get_client()

    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
    )

    image_data = base64.b64decode(response.data[0].b64_json)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_data)

    return len(image_data)


def generate_question_image(q, prompt_override=None):
    """Generate and save a question image. Returns (prompt, file_size)."""
    prompt = prompt_override or build_question_prompt(q)
    output_path = IMAGE_DATA_DIR / f"{q['item_id']}-question.png"
    file_size = generate_image(prompt, output_path)
    return prompt, file_size


def generate_answer_image(q, option_num, prompt_override=None):
    """Generate and save an answer option image. Returns (prompt, file_size)."""
    option_text = q.get(f"option{option_num}", "")
    prompt = prompt_override or build_answer_prompt(q, option_num, option_text)
    output_path = IMAGE_DATA_DIR / f"{q['item_id']}-answer{option_num}.png"
    file_size = generate_image(prompt, output_path)
    return prompt, file_size
