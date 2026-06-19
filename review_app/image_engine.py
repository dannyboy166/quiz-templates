"""OpenAI image generation + editing wrapper for the review app."""

import base64
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

IMAGE_DATA_DIR = Path(os.environ.get("IMAGE_DATA_DIR", "data/images_generated")).resolve()

MAX_VERSIONS = 3  # Keep last 3 versions of each image

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


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------

def _archive_current_image(item_id, image_type="question", option_num=None):
    """Archive current image before overwriting. Returns version info or None."""
    if image_type == "question":
        current = IMAGE_DATA_DIR / f"{item_id}-question.png"
    else:
        current = IMAGE_DATA_DIR / f"{item_id}-answer{option_num}.png"

    if not current.exists():
        return None

    # Find next version number
    existing = get_version_files(item_id, image_type, option_num)
    next_num = len(existing) + 1

    # If at max, rotate: delete v1, shift others down
    if next_num > MAX_VERSIONS:
        for i, vfile in enumerate(existing):
            if i == 0:
                vfile.unlink()  # delete oldest
            else:
                # Shift down: v3 -> v2, v2 -> v1
                new_name = vfile.parent / vfile.name.replace(f"-v{i+1}.", f"-v{i}.")
                vfile.rename(new_name)
        next_num = MAX_VERSIONS

    # Copy current to version
    if image_type == "question":
        version_path = IMAGE_DATA_DIR / f"{item_id}-question-v{next_num}.png"
    else:
        version_path = IMAGE_DATA_DIR / f"{item_id}-answer{option_num}-v{next_num}.png"

    shutil.copy2(current, version_path)
    print(f"  [History] Archived {current.name} -> {version_path.name}")
    return {"version": next_num, "filename": version_path.name}


def get_version_files(item_id, image_type="question", option_num=None):
    """Get list of version files sorted by version number."""
    if image_type == "question":
        pattern = f"{item_id}-question-v*.png"
    else:
        pattern = f"{item_id}-answer{option_num}-v*.png"

    files = sorted(IMAGE_DATA_DIR.glob(pattern))
    return files


def restore_version(item_id, version_num, image_type="question", option_num=None):
    """Restore a previous version as the current image. Archives current first."""
    if image_type == "question":
        version_path = IMAGE_DATA_DIR / f"{item_id}-question-v{version_num}.png"
        current_path = IMAGE_DATA_DIR / f"{item_id}-question.png"
    else:
        version_path = IMAGE_DATA_DIR / f"{item_id}-answer{option_num}-v{version_num}.png"
        current_path = IMAGE_DATA_DIR / f"{item_id}-answer{option_num}.png"

    if not version_path.exists():
        raise FileNotFoundError(f"Version {version_num} not found")

    # Archive current before restoring
    _archive_current_image(item_id, image_type, option_num)

    # Copy version to current
    shutil.copy2(version_path, current_path)
    print(f"  [History] Restored {version_path.name} -> {current_path.name}")
    return current_path


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_question_prompt(q, airtable_desc=None):
    """Build a default prompt suggestion from question context."""
    desc = ""
    if airtable_desc:
        desc = airtable_desc.strip()
    if not desc:
        desc = q.get("notes", "").strip()
    if not desc:
        return ""
    return desc


def build_answer_prompt(q, option_num, option_text):
    """Build a default prompt for an answer option image."""
    if not option_text or option_text.strip() in ("", "True", "False"):
        return ""
    return option_text


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def generate_image(prompt, output_path, size="1024x1024", quality="auto"):
    """Generate an image via OpenAI API and save to output_path.

    quality options: 'low' (~5s), 'medium' (~30s), 'high' (~150-280s), 'auto' (model picks)
    """
    client = _get_client()

    print(f"  [OpenAI] Generating image: {prompt[:100]}...")
    response = client.images.generate(
        model="gpt-image-2",
        prompt=prompt[:4000],
        n=1,
        size=size,
        quality=quality,
        timeout=300,
    )

    image_data = base64.b64decode(response.data[0].b64_json)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_data)

    return len(image_data)


def generate_question_image(q, prompt_override=None, size="1024x1024"):
    """Generate and save a question image. Archives previous version first."""
    prompt = prompt_override or build_question_prompt(q)
    _archive_current_image(q["item_id"], "question")
    output_path = IMAGE_DATA_DIR / f"{q['item_id']}-question.png"
    file_size = generate_image(prompt, output_path, size=size)
    return prompt, file_size


def generate_answer_image(q, option_num, prompt_override=None):
    """Generate and save an answer option image. Archives previous version first."""
    option_text = q.get(f"option{option_num}", "")
    prompt = prompt_override or build_answer_prompt(q, option_num, option_text)
    _archive_current_image(q["item_id"], "answer", option_num)
    output_path = IMAGE_DATA_DIR / f"{q['item_id']}-answer{option_num}.png"
    file_size = generate_image(prompt, output_path)
    return prompt, file_size


# ---------------------------------------------------------------------------
# Image editing (modify existing image without full regeneration)
# ---------------------------------------------------------------------------

def edit_image(source_path, prompt, output_path, size="1024x1024"):
    """Edit an existing image using OpenAI's images.edit API.

    Takes the source image and an edit instruction, returns modified version.
    """
    client = _get_client()

    print(f"  [OpenAI] Editing image: {prompt[:100]}...")
    with open(source_path, "rb") as img_file:
        response = client.images.edit(
            model="gpt-image-2",
            image=img_file,
            prompt=prompt[:4000],
            n=1,
            size=size,
            timeout=300,
        )

    image_data = base64.b64decode(response.data[0].b64_json)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_data)

    return len(image_data)


def edit_question_image(q, edit_prompt, size="1024x1024"):
    """Edit existing question image with an instruction. Archives previous version first."""
    item_id = q["item_id"]
    current_path = IMAGE_DATA_DIR / f"{item_id}-question.png"

    if not current_path.exists():
        raise FileNotFoundError(f"No image to edit for {item_id}")

    _archive_current_image(item_id, "question")
    file_size = edit_image(current_path, edit_prompt, current_path, size=size)
    return edit_prompt, file_size
