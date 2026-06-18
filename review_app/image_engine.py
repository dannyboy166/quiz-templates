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


def build_question_prompt(q, airtable_desc=None):
    """Build a default prompt suggestion from question context.

    Georgia will edit this before generating — it's just a starting point.
    The prompt is sent to OpenAI exactly as typed, no style suffix added.
    """
    # Try Airtable description first (e.g. "The sun is hot")
    desc = ""
    if airtable_desc:
        desc = airtable_desc.strip()

    # Fall back to spreadsheet ImageDescription
    if not desc:
        desc = q.get("image_description", "").strip()

    # No description — empty prompt for Georgia to fill in
    if not desc:
        return ""

    return desc


def build_answer_prompt(q, option_num, option_text):
    """Build a default prompt for an answer option image."""
    if not option_text or option_text.strip() in ("", "True", "False"):
        return ""
    return option_text


def generate_image(prompt, output_path, size="1024x1024", quality="high"):
    """Generate an image via OpenAI API and save to output_path.

    Returns file size in bytes. Uses quality='high' ($0.08/image) for best results.
    """
    client = _get_client()

    print(f"  [OpenAI] Generating image: {prompt[:100]}...")
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt[:4000],  # OpenAI prompt length limit
        n=1,
        size=size,
        quality=quality,
        timeout=120,  # 2 min timeout per image
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
