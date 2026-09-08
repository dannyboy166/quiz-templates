"""Load questions LIVE from the current Google Sheets (source of truth).

Mirrors spreadsheet_loader.load_all_questions() exactly — same question dict keys and the
same 5-tuple return — so it's a drop-in for the Final Stage tab. Difference: reads the live
Google Sheets via the SASCO service account instead of a committed/volume xlsx snapshot.

The live sheets are the source of truth (Dan, 8 Sep 2026). The old xlsx snapshot the other
tabs read is stale — see docs / memory project_app_reads_stale_xlsx.

Auth: GOOGLE_SA_KEY (path to service-account json) in the environment. If gspread or the key
is unavailable, load_all_questions_live() raises — callers should fall back to the xlsx loader.

Results are cached in-process; call refresh() (or load_all_questions_live(force=True)) to re-fetch.
"""

import json
import os
from collections import defaultdict

# Same friendly-name -> TemplateID map as spreadsheet_loader (keep in sync)
QUESTION_TYPE_MAP = {
    "Select One": 1,
    "Select All": 2,
    "True/False": 3,
    "Written": 4,
    "Sort": 5,
    "Link": 6,
}
TEMPLATE_NAMES = {v: k for k, v in QUESTION_TYPE_MAP.items()}

# Live Google Sheet IDs (verified 8 Sep 2026; from scripts/scan_hints_all.py).
# Each maps to a short "file" label mirroring the xlsx stems so the UI reads the same.
LIVE_SHEETS = [
    ("Krisite Stage One English Questions WORLD WISE",     "18SrUKQX_4qUq7LLifPh2ZzJa9f6iG_TZ_wf87Hi65j0"),
    ("Kristie Stage One Mathematics Questions WORLD WISE", "1KE1IjGWVghWLfRmpxlx9Hnuj2p6TfLXDjsLLTo8swQQ"),
    ("Kristie Stage One Other Subjects Questions WORLD WISE", "1ma2CqwygiP1-mW9C1478ZihH4o902ftEy1pUUbHZ4lU"),
]

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# In-process cache of the last successful load (the 5-tuple + a timestamp string).
_cache = None
_cache_meta = {"loaded_at": None, "source": "google-sheets-live"}


def _normalize(val):
    """Identical to spreadsheet_loader._normalize — stripped string, '' for None/NaN/none."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def _have_credentials_source():
    """True if a credential source is configured (inline JSON or a key file path).

    - GOOGLE_SA_JSON: the service-account JSON content inline (use this on Railway).
    - GOOGLE_SA_KEY:  a path to the service-account json file (local dev).
    """
    if os.environ.get("GOOGLE_SA_JSON", "").strip():
        return True
    key = os.environ.get("GOOGLE_SA_KEY", "").strip()
    return bool(key) and os.path.exists(key)


def is_available():
    """True if we can attempt a live load (gspread importable + a credential source)."""
    try:
        import gspread  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
    except ImportError:
        return False
    return _have_credentials_source()


def _credentials():
    from google.oauth2.service_account import Credentials
    inline = os.environ.get("GOOGLE_SA_JSON", "").strip()
    if inline:
        info = json.loads(inline)
        return Credentials.from_service_account_info(info, scopes=_SCOPES)
    key = os.environ.get("GOOGLE_SA_KEY", "").strip()
    if key and os.path.exists(key):
        return Credentials.from_service_account_file(key, scopes=_SCOPES)
    raise RuntimeError(
        "No Google credentials — set GOOGLE_SA_JSON (inline json) or GOOGLE_SA_KEY (file path)"
    )


def _client():
    import gspread
    return gspread.authorize(_credentials())


def _row_to_question(row, short_name, sheet_name):
    """Build the question dict with the SAME keys spreadsheet_loader produces."""
    item_id = _normalize(row.get("ItemID", ""))
    if not item_id:
        return None
    question_text = _normalize(row.get("QuestionText", ""))
    if not question_text:
        return None

    q_type = _normalize(row.get("QuestionType", ""))
    return {
        "item_id": item_id,
        "file": short_name,
        "sheet": sheet_name,
        "subject": _normalize(row.get("Subject", "")),
        "category": _normalize(row.get("Category", "")),
        "grade": _normalize(row.get("Grade", "")),
        "topic": _normalize(row.get("Topic", "")),
        "question_type": q_type,
        "template_id": QUESTION_TYPE_MAP.get(q_type),
        "question_text": question_text,
        "option1": _normalize(row.get("Option1", "")),
        "option2": _normalize(row.get("Option2", "")),
        "option3": _normalize(row.get("Option3", "")),
        "option4": _normalize(row.get("Option4", "")),
        "answer": _normalize(row.get("Answer", "")),
        "level": _normalize(row.get("Level", "")),
        "media_type": _normalize(row.get("MediaType", "")),
        "image_required": _normalize(row.get("ImageRequired", "")),
        "image_description": _normalize(row.get("ImageDescription", "")),
        "hint1": _normalize(row.get("Hint1", "")),
        "hint2": _normalize(row.get("Hint2", "")),
        "hint3": _normalize(row.get("Hint3", "")),
        "get_help": _normalize(row.get("GetHelp", "")),
        "notes": _normalize(row.get("Notes", "")),
    }


def load_all_questions_live(force=False):
    """Fetch all questions live from Google Sheets.

    Returns the SAME 5-tuple as spreadsheet_loader.load_all_questions():
        (questions, questions_list, subjects, topics_by_subject, sheets)
    Cached in-process; pass force=True to re-fetch. Raises on auth/network failure.
    """
    global _cache, _cache_meta
    if _cache is not None and not force:
        return _cache

    gc = _client()

    questions = {}
    questions_list = []
    subjects_set = set()
    topics_by_subject = defaultdict(set)
    sheets = []

    for short_name, sheet_id in LIVE_SHEETS:
        sh = gc.open_by_key(sheet_id)
        for ws in sh.worksheets():
            sheets.append((short_name, ws.title))
            for row in ws.get_all_records():  # first row = header, same as pandas header=0
                q = _row_to_question(row, short_name, ws.title)
                if not q:
                    continue
                if q["item_id"] not in questions:  # first occurrence wins (same as xlsx loader)
                    questions[q["item_id"]] = q
                    questions_list.append(q)
                if q["subject"]:
                    subjects_set.add(q["subject"])
                if q["subject"] and q["topic"]:
                    topics_by_subject[q["subject"]].add(q["topic"])

    subjects = sorted(subjects_set)
    topics_by_subject = {s: sorted(t) for s, t in topics_by_subject.items()}

    _cache = (questions, questions_list, subjects, topics_by_subject, sheets)
    try:
        from .image_state import now_iso as _now
        _cache_meta["loaded_at"] = _now()
    except Exception:
        _cache_meta["loaded_at"] = "unknown"
    print(f"  [gsheets] Loaded {len(questions)} questions LIVE from {len(sheets)} worksheets")
    return _cache


def refresh():
    """Force a re-fetch from Google Sheets. Returns the new 5-tuple."""
    return load_all_questions_live(force=True)


def cache_meta():
    return dict(_cache_meta)
