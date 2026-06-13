"""Push generated images to Airtable."""

import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "apptbIO1ziocd4RHA")

# Airtable table IDs by name
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

# Map spreadsheet subject+category to Airtable table name
SUBJECT_TO_TABLE = {
    "Maths Number & Algebra": "Numbers & Algebra",
    "Maths Statistics & Probability": "Statistics & Probability",
    "Maths Measurement & Space": "Measurement & Space",
    "Human Society and its Environment": "HSIE",
    "Science & Technology": "Science & technology",
    "Creative Arts": "Creative Arts",
    "Personal Development Health and Physical Education": "PD H PE",
}

# English uses category to pick the table
ENGLISH_CATEGORY_TO_TABLE = {
    "Phonological Awareness": "Phonological Awareness",
    "Phonics": "Phonics",
    "Spelling": "Spelling",
    "Punctuation": "Punctuation",
    "Grammar": None,
    "Vocabulary": None,
    "Reading Comprehension": None,
}

# Image type → Airtable column name
IMAGE_COLUMN_MAP = {
    "question": "Question Image SVG",
    "answer1": "Answer A Image",
    "answer2": "Answer B Image",
    "answer3": "Answer C Image",
    "answer4": "Answer D Image",
}


def get_table_for_question(q):
    """Determine which Airtable table a question belongs to.

    Returns (table_name, table_id) or (None, None) if no table exists.
    """
    subject = q.get("subject", "")
    category = q.get("category", "")

    if subject == "English":
        table_name = ENGLISH_CATEGORY_TO_TABLE.get(category)
    else:
        table_name = SUBJECT_TO_TABLE.get(subject)

    if not table_name:
        return None, None

    table_id = AIRTABLE_TABLES.get(table_name)
    return table_name, table_id


def _headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def find_record(table_id, item_id):
    """Find an existing Airtable record by ItemID.

    Returns the record dict or None.
    """
    # Fetch all records and filter client-side (more reliable than filterByFormula)
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        resp = requests.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
            headers=_headers(),
            params=params,
            timeout=15,
        )

        if resp.status_code != 200:
            raise Exception(f"Airtable API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        for r in data["records"]:
            rid = str(r["fields"].get("Which Question it refers to", "")).strip()
            if rid == item_id:
                return r

        offset = data.get("offset")
        if not offset:
            break

    return None


def create_record(table_id, item_id, question_text="", description=""):
    """Create a new Airtable record for a question."""
    fields = {
        "Which Question it refers to": item_id,
    }
    if question_text:
        fields["Question"] = question_text[:1000]
    if description:
        fields["Description"] = description[:1000]

    resp = requests.post(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}",
        headers=_headers(),
        json={"fields": fields},
        timeout=15,
    )

    if resp.status_code != 200:
        raise Exception(f"Airtable create error {resp.status_code}: {resp.text[:200]}")

    return resp.json()


def push_image(table_id, record_id, column_name, image_url):
    """Update an Airtable record to add an image attachment.

    Airtable requires a publicly accessible URL — it downloads the file.
    """
    resp = requests.patch(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}/{record_id}",
        headers=_headers(),
        json={
            "fields": {
                column_name: [{"url": image_url}],
            }
        },
        timeout=30,
    )

    if resp.status_code != 200:
        raise Exception(f"Airtable push error {resp.status_code}: {resp.text[:200]}")

    return resp.json()


def push_question_image(q, image_url, airtable_cache=None):
    """Full workflow: find/create record, push question image.

    Returns (table_name, record_id, status_message).
    """
    table_name, table_id = get_table_for_question(q)
    if not table_id:
        raise Exception(f"No Airtable table for subject={q.get('subject')}, category={q.get('category')}")

    item_id = q["item_id"]

    # Check cache first, then API
    record = None
    if airtable_cache and item_id in airtable_cache:
        cached = airtable_cache[item_id]
        record_id = cached.get("record_id")
        if record_id:
            record = {"id": record_id}

    if not record:
        record = find_record(table_id, item_id)

    if not record:
        record = create_record(table_id, item_id, q.get("question_text", ""))

    record_id = record["id"]
    push_image(table_id, record_id, "Question Image SVG", image_url)

    return table_name, record_id, "Pushed successfully"


def push_answer_image(q, option_num, image_url, airtable_cache=None):
    """Full workflow: find/create record, push answer image.

    Returns (table_name, record_id, status_message).
    """
    table_name, table_id = get_table_for_question(q)
    if not table_id:
        raise Exception(f"No Airtable table for subject={q.get('subject')}, category={q.get('category')}")

    item_id = q["item_id"]
    column = IMAGE_COLUMN_MAP.get(f"answer{option_num}")
    if not column:
        raise Exception(f"Invalid option_num: {option_num}")

    record = None
    if airtable_cache and item_id in airtable_cache:
        cached = airtable_cache[item_id]
        record_id = cached.get("record_id")
        if record_id:
            record = {"id": record_id}

    if not record:
        record = find_record(table_id, item_id)

    if not record:
        record = create_record(table_id, item_id, q.get("question_text", ""))

    record_id = record["id"]
    push_image(table_id, record_id, column, image_url)

    return table_name, record_id, "Pushed successfully"
