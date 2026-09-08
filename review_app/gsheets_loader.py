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

# Full read+write — the Final Stage tab edits cells back to the master sheet.
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Map the short "file" label (stored on each question as q["file"]) back to its sheet id,
# so write-back knows which spreadsheet to edit.
_FILE_TO_ID = {name: sid for name, sid in LIVE_SHEETS}

# The spreadsheet column header each editable question field lives under.
FIELD_TO_HEADER = {
    "question_text": "QuestionText",
    "option1": "Option1", "option2": "Option2", "option3": "Option3", "option4": "Option4",
    "answer": "Answer",
    "hint1": "Hint1", "hint2": "Hint2", "hint3": "Hint3",
    "topic": "Topic", "category": "Category", "grade": "Grade", "level": "Level",
    "media_type": "MediaType", "image_description": "ImageDescription", "get_help": "GetHelp",
}

# In-process cache of the last successful load (the 5-tuple + a timestamp string).
_cache = None
_cache_meta = {"loaded_at": None, "source": "google-sheets-live", "warnings": []}


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


# Transient Google API statuses that are worth retrying (server-side / rate limit).
_TRANSIENT_CODES = (429, 500, 502, 503, 504)


def _is_transient(exc):
    """True if the exception looks like a transient Google API error."""
    import time as _t  # noqa
    code = getattr(getattr(exc, "response", None), "status_code", None)
    if code in _TRANSIENT_CODES:
        return True
    txt = str(exc)
    return any(str(c) in txt for c in _TRANSIENT_CODES) or "unavailable" in txt.lower()


def _with_retry(fn, what, attempts=4, base_delay=1.0):
    """Call fn(), retrying transient failures with linear backoff. Raises the last error."""
    import time
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if not _is_transient(e) or i == attempts - 1:
                raise
            delay = base_delay * (i + 1)
            print(f"  [gsheets] transient error on {what} (attempt {i+1}/{attempts}): {e} — retrying in {delay:.0f}s")
            time.sleep(delay)
    raise last


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

    warnings = []
    for short_name, sheet_id in LIVE_SHEETS:
        try:
            # Retry transient Google API errors (503/429/timeout) before giving up —
            # a single blip shouldn't drop a whole subject's questions from the app.
            sh = _with_retry(lambda: gc.open_by_key(sheet_id), f"open '{short_name}'")
            worksheets = _with_retry(sh.worksheets, f"list worksheets '{short_name}'")
        except Exception as e:
            msg = f"could not open sheet '{short_name}' ({sheet_id}): {e}"
            print(f"  [gsheets] WARNING — {msg}")
            warnings.append(msg)
            continue
        for ws in worksheets:
            sheets.append((short_name, ws.title))
            try:
                # get_all_records() raises on duplicate/blank header cells; don't let one
                # bad worksheet abort the whole live load — skip it and keep going.
                records = _with_retry(ws.get_all_records, f"read '{short_name}/{ws.title}'")
            except Exception as e:
                msg = f"worksheet '{short_name}/{ws.title}' unreadable, skipped: {e}"
                print(f"  [gsheets] WARNING — {msg}")
                warnings.append(msg)
                continue
            for row in records:  # first row = header, same as pandas header=0
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

    if not questions:
        # A totally empty live load is almost certainly a real failure (auth/network/all
        # worksheets bad). Raise so the app falls back to the xlsx snapshot + red banner,
        # rather than silently serving an empty app.
        raise RuntimeError(
            "Live Google Sheets returned 0 questions" +
            (f" — {'; '.join(warnings)}" if warnings else "")
        )

    subjects = sorted(subjects_set)
    topics_by_subject = {s: sorted(t) for s, t in topics_by_subject.items()}
    _cache_meta["warnings"] = warnings

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


# ---------------------------------------------------------------------------
# Write-back — edit a question's field in the live master sheet
# ---------------------------------------------------------------------------

def update_field(q, field, new_value):
    """Update ONE field of a question in its live Google Sheet.

    q is the question dict (needs 'file', 'sheet', 'item_id'). field is a key from
    FIELD_TO_HEADER. Finds the question's row by ItemID in the correct worksheet and
    writes new_value into the mapped column's cell.

    Returns (old_value, cell_a1). Raises with a clear message if it can't locate the cell.
    The caller is responsible for updating the in-memory cache after a successful write.
    """
    header = FIELD_TO_HEADER.get(field)
    if not header:
        raise ValueError(f"Field '{field}' is not editable")

    sheet_id = _FILE_TO_ID.get(q.get("file"))
    if not sheet_id:
        raise RuntimeError(f"Unknown sheet for file '{q.get('file')}'")

    gc = _client()
    sh = _with_retry(lambda: gc.open_by_key(sheet_id), "open for edit")
    ws = _with_retry(lambda: sh.worksheet(q["sheet"]), f"open worksheet '{q['sheet']}'")

    all_values = _with_retry(ws.get_all_values, "read for edit")
    if not all_values:
        raise RuntimeError("Worksheet is empty")

    headers = all_values[0]
    # locate columns (case/space-insensitive match on header name)
    def _norm_h(h):
        return str(h).strip().lower().replace(" ", "")
    header_idx = {_norm_h(h): i for i, h in enumerate(headers)}
    col = header_idx.get(_norm_h(header))
    id_col = header_idx.get("itemid")
    if col is None:
        raise RuntimeError(f"Column '{header}' not found in worksheet")
    if id_col is None:
        raise RuntimeError("ItemID column not found in worksheet")

    target_id = str(q["item_id"]).strip()
    for r_i in range(1, len(all_values)):
        row = all_values[r_i]
        if id_col >= len(row):
            continue
        rid = str(row[id_col]).strip()
        if rid == target_id or (rid.lstrip("0") or rid) == target_id:
            old_value = row[col] if col < len(row) else ""
            # gspread is 1-indexed; row header is row 1, so data row r_i -> sheet row r_i+1
            cell_row = r_i + 1
            cell_col = col + 1
            cell_a1 = _rowcol_to_a1(cell_row, cell_col)
            _with_retry(lambda: ws.update_acell(cell_a1, new_value), f"write {cell_a1}")
            print(f"  [gsheets] wrote {q['item_id']}.{field} ({cell_a1}): {old_value!r} -> {new_value!r}")
            return old_value, cell_a1

    raise RuntimeError(f"ItemID {target_id} not found in worksheet '{q['sheet']}'")


def _rowcol_to_a1(row, col):
    """1-indexed (row, col) -> A1 like 'C5'. Small local impl (avoids gspread version drift)."""
    letters = ""
    c = col
    while c > 0:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"
