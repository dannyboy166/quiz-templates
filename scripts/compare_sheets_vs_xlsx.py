"""Compare LIVE Google Sheets vs the xlsx snapshot the web app currently reads.

Read-only. Measures drift so we can decide whether to switch tabs to live Sheets.
Uses the SASCO service account (GOOGLE_SA_KEY in .env) — same auth as scan_hints_all.py.
"""
import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Live Google Sheet IDs (from scripts/scan_hints_all.py)
SHEETS = {
    "English":       "18SrUKQX_4qUq7LLifPh2ZzJa9f6iG_TZ_wf87Hi65j0",
    "Maths":         "1KE1IjGWVghWLfRmpxlx9Hnuj2p6TfLXDjsLLTo8swQQ",
    "OtherSubjects": "1ma2CqwygiP1-mW9C1478ZihH4o902ftEy1pUUbHZ4lU",
}

# xlsx snapshot the app reads (review_app/spreadsheet_loader.py)
XLSX_DIR = ROOT / "data" / "questions" / "drive_latest"
XLSX_FILES = {
    "English":       "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Maths":         "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "OtherSubjects": "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
}

# Fields we compare (the ones that matter for building a question)
FIELDS = ["QuestionType", "Subject", "Category", "Grade", "Topic", "QuestionText",
          "Option1", "Option2", "Option3", "Option4", "Answer", "Level",
          "MediaType", "ImageRequired", "Hint1", "Hint2", "Hint3", "GetHelp"]


def norm(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def rows_to_map(rows_iter, source_label):
    """rows_iter yields dict-like rows. Returns {item_id: {field: val}}, first-wins."""
    out = {}
    dupes = 0
    for row in rows_iter:
        iid = norm(row.get("ItemID", ""))
        qt = norm(row.get("QuestionText", ""))
        if not iid or not qt:
            continue
        if iid in out:
            dupes += 1
            continue
        out[iid] = {f: norm(row.get(f, "")) for f in FIELDS}
    return out, dupes


def load_live():
    key = os.environ.get("GOOGLE_SA_KEY")
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly",
              "https://www.googleapis.com/auth/drive.readonly"]
    gc = gspread.authorize(Credentials.from_service_account_file(key, scopes=scopes))
    combined = {}
    per_subject = {}
    for subj, sid in SHEETS.items():
        sh = gc.open_by_key(sid)
        rows = []
        for ws in sh.worksheets():
            recs = ws.get_all_records()  # first row = header
            rows.extend(recs)
        m, d = rows_to_map(rows, f"live/{subj}")
        per_subject[subj] = len(m)
        for k, v in m.items():
            combined.setdefault(k, v)
    return combined, per_subject


def load_xlsx():
    combined = {}
    per_subject = {}
    for subj, fn in XLSX_FILES.items():
        fp = XLSX_DIR / fn
        rows = []
        if fp.exists():
            xl = pd.ExcelFile(fp)
            for sn in xl.sheet_names:
                df = pd.read_excel(fp, sheet_name=sn, header=0,
                                   keep_default_na=False, na_values=[])
                rows.extend(df.to_dict("records"))
        m, d = rows_to_map(rows, f"xlsx/{subj}")
        per_subject[subj] = len(m)
        for k, v in m.items():
            combined.setdefault(k, v)
    return combined, per_subject


def main():
    print("Loading LIVE Google Sheets (SASCO service account)...")
    live, live_by = load_live()
    print("Loading xlsx snapshot (what the app reads)...")
    xlsx, xlsx_by = load_xlsx()

    print("\n=== COUNTS per subject (live vs xlsx) ===")
    for subj in SHEETS:
        print(f"  {subj:14s} live={live_by.get(subj,0):5d}  xlsx={xlsx_by.get(subj,0):5d}  "
              f"diff={live_by.get(subj,0)-xlsx_by.get(subj,0):+d}")
    print(f"  {'TOTAL':14s} live={len(live):5d}  xlsx={len(xlsx):5d}  diff={len(live)-len(xlsx):+d}")

    live_ids, xlsx_ids = set(live), set(xlsx)
    added = live_ids - xlsx_ids       # in live, not in app snapshot
    removed = xlsx_ids - live_ids     # in app snapshot, not in live
    common = live_ids & xlsx_ids

    print(f"\n=== ItemID membership ===")
    print(f"  New in live (app doesn't have): {len(added)}")
    print(f"  In app snapshot but gone from live: {len(removed)}")
    print(f"  Common to both: {len(common)}")
    if added:
        print("  sample new:", sorted(added)[:10])
    if removed:
        print("  sample removed:", sorted(removed)[:10])

    # Field-level diffs among common ItemIDs
    field_changes = defaultdict(int)
    changed_qs = []
    for iid in common:
        diffs = {f: (xlsx[iid][f], live[iid][f]) for f in FIELDS
                 if xlsx[iid][f] != live[iid][f]}
        if diffs:
            changed_qs.append((iid, diffs))
            for f in diffs:
                field_changes[f] += 1

    print(f"\n=== Field changes among {len(common)} common questions ===")
    print(f"  Questions with >=1 changed field: {len(changed_qs)}")
    for f, n in sorted(field_changes.items(), key=lambda x: -x[1]):
        print(f"    {f:16s} changed in {n} questions")

    print("\n=== Sample changed questions (first 15) ===")
    for iid, diffs in changed_qs[:15]:
        print(f"\n  ItemID {iid}:")
        for f, (old, new) in diffs.items():
            o = (old[:60] + "…") if len(old) > 60 else old
            n = (new[:60] + "…") if len(new) > 60 else new
            print(f"    {f}: [xlsx] {o!r}  ->  [live] {n!r}")


if __name__ == "__main__":
    main()
