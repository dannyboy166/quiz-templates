"""Load questions from the 3 Stage One spreadsheets into memory."""

import os
from pathlib import Path
from collections import defaultdict

import pandas as pd

# Check multiple locations for spreadsheet files
# Local dev: data/questions/drive_latest/
# Railway: /data/voiceovers/questions/drive_latest/ (on persistent volume)
_LOCAL_DIR = Path("data/questions/drive_latest")
_VOLUME_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers")) / "questions" / "drive_latest"

DRIVE_DIR = _VOLUME_DIR if _VOLUME_DIR.exists() else _LOCAL_DIR

FILENAMES = [
    "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
]

SPREADSHEET_FILES = [DRIVE_DIR / f for f in FILENAMES]

QUESTION_TYPE_MAP = {
    "Select One": 1,
    "Select All": 2,
    "True/False": 3,
    "Written": 4,
    "Sort": 5,
    "Link": 6,
}

TEMPLATE_NAMES = {v: k for k, v in QUESTION_TYPE_MAP.items()}


def _normalize(val):
    """Convert value to stripped string, empty string for None/NaN."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def load_all_questions():
    """Load all questions from the 3 spreadsheet files.

    Returns:
        questions: dict of {item_id: question_dict}
        questions_list: list of all question dicts (ordered by file/sheet)
        subjects: sorted list of unique subjects
        topics_by_subject: dict of {subject: sorted list of topics}
        sheets: list of (short_filename, sheet_name) pairs
    """
    questions = {}
    questions_list = []
    subjects_set = set()
    topics_by_subject = defaultdict(set)
    sheets = []

    for filepath in SPREADSHEET_FILES:
        if not filepath.exists():
            print(f"  WARNING: {filepath} not found, skipping")
            continue

        short_name = filepath.stem
        xl = pd.ExcelFile(filepath)

        for sheet_name in xl.sheet_names:
            sheets.append((short_name, sheet_name))

            df = pd.read_excel(
                filepath, sheet_name=sheet_name, header=0,
                keep_default_na=False, na_values=[]
            )

            for _, row in df.iterrows():
                item_id = _normalize(row.get("ItemID", ""))
                if not item_id:
                    continue

                question_text = _normalize(row.get("QuestionText", ""))
                if not question_text:
                    continue

                q_type = _normalize(row.get("QuestionType", ""))
                template_id = QUESTION_TYPE_MAP.get(q_type)
                subject = _normalize(row.get("Subject", ""))
                category = _normalize(row.get("Category", ""))
                topic = _normalize(row.get("Topic", ""))
                media_type = _normalize(row.get("MediaType", ""))

                q = {
                    "item_id": item_id,
                    "file": short_name,
                    "sheet": sheet_name,
                    "subject": subject,
                    "category": category,
                    "grade": _normalize(row.get("Grade", "")),
                    "topic": topic,
                    "question_type": q_type,
                    "template_id": template_id,
                    "question_text": question_text,
                    "option1": _normalize(row.get("Option1", "")),
                    "option2": _normalize(row.get("Option2", "")),
                    "option3": _normalize(row.get("Option3", "")),
                    "option4": _normalize(row.get("Option4", "")),
                    "answer": _normalize(row.get("Answer", "")),
                    "level": _normalize(row.get("Level", "")),
                    "media_type": media_type,
                    "image_required": _normalize(row.get("ImageRequired", "")),
                    "image_description": _normalize(row.get("ImageDescription", "")),
                    "hint1": _normalize(row.get("Hint1", "")),
                    "hint2": _normalize(row.get("Hint2", "")),
                    "hint3": _normalize(row.get("Hint3", "")),
                    "get_help": _normalize(row.get("GetHelp", "")),
                    "notes": _normalize(row.get("Notes", "")),
                }

                if item_id not in questions:
                    questions[item_id] = q
                    questions_list.append(q)

                if subject:
                    subjects_set.add(subject)
                if subject and topic:
                    topics_by_subject[subject].add(topic)

    subjects = sorted(subjects_set)
    topics_by_subject = {s: sorted(topics) for s, topics in topics_by_subject.items()}

    print(f"  Loaded {len(questions)} questions from {len(sheets)} sheets")
    return questions, questions_list, subjects, topics_by_subject, sheets
