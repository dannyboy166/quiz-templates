"""OpenAI image generation wrapper for the review app."""

import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

from openai import OpenAI

IMAGE_DATA_DIR = Path(os.environ.get("IMAGE_DATA_DIR", "data/images_generated")).resolve()

# Lazy client init (so import doesn't fail if key not set yet)
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY not set in .env")
        _client = OpenAI(api_key=api_key)
    return _client


def build_question_prompt(q):
    """Build an image generation prompt from a question dict.

    Uses image_description if available. If not, builds a simple visual
    prompt — just the key object/concept, not the whole question text.
    """
    desc = q.get("image_description", "").strip()

    if not desc:
        # No description provided — Georgia will likely edit this.
        # Give a placeholder hint rather than dumping the question text.
        desc = (
            f"[No image description in spreadsheet. "
            f"Edit this prompt to describe what image you need for: "
            f"\"{q.get('question_text', '')[:100]}\"]"
        )
        return desc

    return (
        f"A simple, colorful cartoon illustration for a children's "
        f"educational quiz (ages 5-12). "
        f"{desc}. "
        f"White background, no text, no writing, no numbers, no labels, "
        f"child-friendly style."
    )


def build_answer_prompt(q, option_num, option_text):
    """Build an image generation prompt for a single answer option."""
    return (
        f"A simple, clear, colorful cartoon illustration of: {option_text}. "
        f"For a children's educational quiz (ages 5-12). "
        f"White background, no text, no labels, child-friendly style, "
        f"single object or concept centered in frame."
    )


def generate_image(prompt, output_path, size="1024x1024", quality="medium"):
    """Generate an image via OpenAI API and save to output_path.

    Returns file size in bytes.
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
