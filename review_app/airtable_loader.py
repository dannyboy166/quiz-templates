"""Load image data from Airtable on startup — shows what Georgia has done."""

import os
import time
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "apptbIO1ziocd4RHA")

# Subject (from spreadsheet) → Airtable table name
# English uses category to determine which table
SUBJECT_TO_TABLE = {
    "Maths Number & Algebra": "Numbers & Algebra",
    "Maths Statistics & Probability": "Statistics & Probability",
    "Maths Measurement & Space": "Measurement & Space",
    "Human Society and its Environment": "HSIE",
    "Science & Technology": "Science & technology",
    "Creative Arts": "Creative Arts",
    "Personal Development Health and Physical Education": "PD H PE",
}

ENGLISH_CATEGORY_TO_TABLE = {
    "Phonological Awareness": "Phonological Awareness",
    "Phonics": "Phonics",
    "Spelling": "Spelling",
    "Punctuation": "Punctuation",
    "Grammar": None,  # No Airtable table yet
    "Vocabulary": None,
    "Reading Comprehension": None,
}

# All tables to fetch from
AIRTABLE_TABLES = {
    "Numbers & Algebra": "tbldKCkIYblhKoKO9",
    "Statistics & Probability": "tblA0hcvDFxy8lRgk",
    "Measurement & Space": "tbl8RYjMjcmzoPYx2",
    "Phonological Awareness": "tblPofqYbDA8e4NRO",
    "Phonics": "tblxuqIa3A5vKnBo7",
    "Spelling": "tbljXqnnA3cRZ1gkr",
    "Punctuation": "tbleEauHSyfon4gZv",
    "HSIE": "tblc9IH2c0RRjiNij",
    "Science & technology": "tblsUEwLBE9dTAobz",
    "Creative Arts": "tbl3whnn4cLfuxOFo",
    "PD H PE": "tbloE0Yd8BN7lHLeY",
}


CACHE_FILE = Path(os.environ.get("IMAGE_DATA_DIR", "data/images_generated")).resolve() / "airtable_cache.json"


def load_cached_airtable_images():
    """Load from local cache if available. Much faster than fetching from API."""
    if CACHE_FILE.exists():
        import json
        with open(CACHE_FILE) as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} images from Airtable cache")
        return data
    return None


def save_airtable_cache(images):
    """Save Airtable data to local cache."""
    import json
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Strip the full URL data (expires anyway) — just keep metadata
    stripped = {}
    for item_id, entry in images.items():
        stripped[item_id] = {
            "item_id": entry["item_id"],
            "table": entry["table"],
            "description": entry["description"],
            "question_image": {"filename": entry["question_image"]["filename"], "type": entry["question_image"]["type"]} if entry.get("question_image") else None,
            "answer_images": {
                k: {"filename": v["filename"], "type": v["type"]} if v else None
                for k, v in entry.get("answer_images", {}).items()
            } if entry.get("answer_images") else {},
            "graphic_type": entry.get("graphic_type", []),
            "record_id": entry.get("record_id", ""),
        }
    with open(CACHE_FILE, "w") as f:
        json.dump(stripped, f)
    print(f"  Cached {len(stripped)} Airtable records to {CACHE_FILE}")


def _get_attachment_url(attachment_list):
    """Extract the thumbnail or full URL from an Airtable attachment field."""
    if not attachment_list:
        return None
    att = attachment_list[0]
    # Prefer thumbnails for display (smaller, faster)
    thumbs = att.get("thumbnails", {})
    if thumbs.get("large"):
        return thumbs["large"]["url"]
    return att.get("url")


def _get_attachment_info(attachment_list):
    """Extract url, filename, and type from an Airtable attachment."""
    if not attachment_list:
        return None
    att = attachment_list[0]
    thumbs = att.get("thumbnails", {})
    return {
        "url": thumbs.get("large", {}).get("url") or att.get("url"),
        "filename": att.get("filename", ""),
        "type": att.get("type", ""),
    }


def load_airtable_images():
    """Fetch all image records from Airtable. Returns dict keyed by ItemID.

    Each entry:
    {
        "item_id": str,
        "table": str,  # Airtable table name
        "description": str,
        "question_image": {url, filename, type} or None,
        "answer_images": {"1": {...} or None, "2": ..., "3": ..., "4": ...},
        "graphic_type": list,
    }
    """
    if not AIRTABLE_TOKEN:
        print("  WARNING: AIRTABLE_TOKEN not set, skipping Airtable load")
        return {}

    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    all_images = {}

    for table_name, table_id in AIRTABLE_TABLES.items():
        records = []
        offset = None

        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset

            try:
                resp = requests.get(
                    f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
            except requests.RequestException as e:
                print(f"  WARNING: Failed to fetch {table_name}: {e}")
                break

            if resp.status_code != 200:
                print(f"  WARNING: Airtable {table_name} returned {resp.status_code}")
                break

            data = resp.json()
            records.extend(data["records"])

            offset = data.get("offset")
            if not offset:
                break
            time.sleep(0.05)  # minimal rate limit delay

        # Process records
        for r in records:
            f = r["fields"]
            raw_id = str(f.get("Which Question it refers to", "")).strip()
            if not raw_id:
                continue
            # Normalize: strip leading zeros to match spreadsheet format
            item_id = raw_id.lstrip("0") or raw_id

            # Question image — check multiple possible column names
            q_img = (_get_attachment_info(f.get("Question Image SVG"))
                     or _get_attachment_info(f.get("Question Image JSON"))
                     or _get_attachment_info(f.get("Graphic File SVG"))
                     or _get_attachment_info(f.get("Graphic File JSON")))

            # Answer images
            ans_imgs = {
                "1": _get_attachment_info(f.get("Answer A Image")),
                "2": _get_attachment_info(f.get("Answer B Image")),
                "3": _get_attachment_info(f.get("Answer C Image")),
                "4": _get_attachment_info(f.get("Answer D Image")),
            }

            has_any_answer = any(v for v in ans_imgs.values())

            all_images[item_id] = {
                "item_id": item_id,
                "table": table_name,
                "description": str(f.get("Description", "")).strip(),
                "question_image": q_img,
                "answer_images": ans_imgs if has_any_answer else {},
                "graphic_type": f.get("Graphic Type", []),
                "record_id": r["id"],
            }

        print(f"  Airtable {table_name}: {len(records)} records")

    print(f"  Total Airtable images loaded: {len(all_images)}")
    return all_images


def get_airtable_table_for_question(q):
    """Determine which Airtable table a question belongs to."""
    subject = q.get("subject", "")
    category = q.get("category", "")

    if subject == "English":
        return ENGLISH_CATEGORY_TO_TABLE.get(category)

    return SUBJECT_TO_TABLE.get(subject)
