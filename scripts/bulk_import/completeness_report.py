#!/usr/bin/env python3
"""
THE single source of truth for "is a question truly done?"  (READ-ONLY)

Why this exists: content lives in THREE places that drift apart —
  1. Spreadsheet   -> question text, options, HINT TEXTS (the real hint count)
  2. Review app    -> voiceovers + images(Airtable), each with an 'approved' flag
  3. Victor's DB   -> the actual live rows (may be stale from the May import, or behind on ingest)
Every confusing "is it done?" moment came from these disagreeing. This script checks all three
at once and returns ONE verdict per question, so we stop getting conflicting numbers.

For each question it computes, per source:
  spreadsheet: hint levels that have text; whether it has question text/answer
  app:         question VO approved? each hint VO approved? question image (Airtable) present?
  db:          ReaderBlobID=audio? ImageBlobID=image? per-hint: text row? audio row(111)?

Then a VERDICT:
  READY        - DB matches spreadsheet, VO+image+all hints voiced IN THE DB, audio-only hints. Can go Active.
                 (image MUST be in the DB — Airtable-only does NOT render in the portal.)
  NEEDS_INGEST - content done+approved in app, but audio not yet copied into the DB (run ingest_voiceovers).
  NEEDS_IMAGE_SYNC - image is in Airtable but NOT yet in the DB (run import_from_airtable). Won't render until synced.
  DB_EXTRA_HINTS - DB has stale hint texts the spreadsheet doesn't (May-import leftovers) -> cleanup.
  NEEDS_IMAGE  - no question image in Airtable OR DB (real Georgia work).
  NEEDS_VO     - question or a hint voiceover not done/approved in the app (real Zoe/Georgia work).
  NOT_IN_DB    - never imported (needs import_questions first).

USAGE
  python -m scripts.bulk_import.completeness_report                 # whole schema summary
  python -m scripts.bulk_import.completeness_report --verdict READY # list just those
  python -m scripts.bulk_import.completeness_report --topic "Road Safety"
  python -m scripts.bulk_import.completeness_report --csv out.csv   # full per-question CSV
  python -m scripts.bulk_import.completeness_report --qids-file q.txt

Writes NOTHING. Ever.
"""
import argparse
import os
import struct
import sys
import time
from collections import Counter

import requests
from azure.identity import AzureCliCredential
import pyodbc

# --- reuse the app's spreadsheet + airtable knowledge so there's one definition ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from review_app.spreadsheet_loader import load_all_questions  # noqa: E402
from review_app.airtable_loader import AIRTABLE_TABLES, AIRTABLE_BASE_ID  # noqa: E402

APP_BASE = "https://web-production-bce96.up.railway.app"
SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
BLOB_AUDIO = 111
BLOB_IMAGE = 110
TEXT_ELEM = "question-text-content"
HINT_AUDIO_ELEM = "hint-graphic-audio"


def norm(x):
    s = str(x).strip()
    return s.lstrip("0") or s


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def load_spreadsheet():
    """ItemID(norm) -> {hint_levels:set, has_text:bool, has_answer:bool, topic, type}"""
    questions, *_ = load_all_questions()
    rows = questions.values() if isinstance(questions, dict) else questions
    out = {}
    for q in rows:
        iid = str(q.get("item_id") or q.get("ItemID") or "").strip()
        if not iid:
            continue
        out[norm(iid)] = {
            "hint_levels": set(h for h in (1, 2, 3) if (q.get(f"hint{h}") or "").strip()),
            "topic": q.get("topic", "?"),
        }
    return out


def load_app():
    r = requests.get(f"{APP_BASE}/api/pipeline-stats", timeout=120)
    r.raise_for_status()
    return r.json()["items"]


def load_airtable_images():
    """Set of ItemID(norm) that have a question image in Airtable."""
    token = os.environ.get("AIRTABLE_TOKEN", "")
    if not token:
        # try .env
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        token = os.environ.get("AIRTABLE_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"}
    qimg = set()

    def has_att(v):
        return isinstance(v, list) and len(v) > 0

    for tid in AIRTABLE_TABLES.values():
        offset = None
        while True:
            p = {"pageSize": 100}
            if offset:
                p["offset"] = offset
            resp = requests.get(f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{tid}",
                                headers=headers, params=p, timeout=30)
            if resp.status_code != 200:
                break
            d = resp.json()
            for rec in d["records"]:
                f = rec["fields"]
                rid = str(f.get("Which Question it refers to", "")).strip()
                if not rid:
                    continue
                if (has_att(f.get("Question Image SVG")) or has_att(f.get("Question Image JSON"))
                        or has_att(f.get("Graphic File SVG")) or has_att(f.get("Graphic File JSON"))):
                    qimg.add(norm(rid))
            offset = d.get("offset")
            if not offset:
                break
            time.sleep(0.03)
    return qimg


def load_db(cur):
    """Returns (xref{itemnorm->qid}, dbq{qid->row}, dbhints{qid->{lvl:{text,audio}}})."""
    cur.execute(f"SELECT SpreadsheetRecordID, QuestionID FROM {SCHEMA}.SpreadsheetXRef WHERE TableName='Question'")
    xref = {norm(r): q for r, q in cur.fetchall()}

    cur.execute(f"""
        SELECT q.QuestionID, q.StatusCD, q.TemplateID,
          CASE WHEN rb.BlobTypeCD={BLOB_AUDIO} THEN 1 ELSE 0 END,
          CASE WHEN ib.BlobTypeCD={BLOB_IMAGE} THEN 1 ELSE 0 END
        FROM {SCHEMA}.Question q
        LEFT JOIN {SCHEMA}.Blob rb ON rb.BlobID=q.ReaderBlobID
        LEFT JOIN {SCHEMA}.Blob ib ON ib.BlobID=q.ImageBlobID
        WHERE q.CreatedUserID=8""")
    dbq = {}
    for qid, st, tid, ha, hi in cur.fetchall():
        dbq[qid] = {"status": st, "tid": tid, "audio": bool(ha), "image": bool(hi)}

    cur.execute(f"""
        SELECT hr.QuestionID, hr.HintLevelNum, hr.HTMLElementID,
          CASE WHEN hr.HintHTML IS NULL OR LEN(hr.HintHTML)=0 THEN 0 ELSE 1 END,
          CASE WHEN b.BlobTypeCD={BLOB_AUDIO} THEN 1 ELSE 0 END
        FROM {SCHEMA}.HintReplacement hr
        LEFT JOIN {SCHEMA}.Blob b ON b.BlobID=hr.BlobID""")
    dbhints = {}
    for qid, lvl, elem, ht, ha in cur.fetchall():
        d = dbhints.setdefault(qid, {})
        e = d.setdefault(lvl, {"text": 0, "audio": 0})
        if elem == TEXT_ELEM and ht:
            e["text"] = 1
        if elem == HINT_AUDIO_ELEM and ha:
            e["audio"] = 1
    return xref, dbq, dbhints


def app_hint_ok(app_item, lvl):
    hv = (app_item.get("hints") or {}).get(f"hint{lvl}")
    return bool(hv and hv.get("has_audio") and hv.get("status") == "approved")


def verdict_for(iid, sheet, app_items, at_qimg, xref, dbq, dbhints):
    """Return (verdict, detail_string)."""
    ni = norm(iid)
    sh = sheet.get(ni)
    if not sh:
        return "NO_SPREADSHEET", "not found in spreadsheet"
    app_item = app_items.get(ni) or app_items.get("20" + ni) or {}
    hint_levels = sorted(sh["hint_levels"])

    # --- app-side content readiness ---
    q_vo_ok = bool(app_item.get("has_vo_audio") and app_item.get("vo_status") == "approved")
    hints_vo_ok = all(app_hint_ok(app_item, l) for l in hint_levels)
    img_ok = ni in at_qimg  # airtable

    # --- db side ---
    qid = xref.get(ni)
    if not qid:
        # never imported. Is the content ready in app? report why not READY.
        if not img_ok:
            return "NOT_IN_DB", "never imported; also no image in Airtable"
        if not q_vo_ok or not hints_vo_ok:
            return "NOT_IN_DB", "never imported; VO not fully approved in app"
        return "NOT_IN_DB", "never imported (content ready — run import_questions)"

    d = dbq.get(qid, {})
    dh = dbhints.get(qid, {})
    db_text = set(l for l, v in dh.items() if v["text"])
    db_audio = set(l for l, v in dh.items() if v["audio"])
    sh_levels = set(hint_levels)

    # image: must be IN THE DB to render in the portal. Airtable-only = needs sync.
    if not d.get("image"):
        if img_ok:
            return "NEEDS_IMAGE_SYNC", "image in Airtable but not yet in DB (run import_from_airtable)"
        return "NEEDS_IMAGE", "no question image in DB or Airtable"

    # real VO not done in app -> genuine content gap
    if not q_vo_ok:
        return "NEEDS_VO", f"question VO not approved in app (status={app_item.get('vo_status')})"
    if not hints_vo_ok:
        missing = [l for l in hint_levels if not app_hint_ok(app_item, l)]
        return "NEEDS_VO", f"hint VO(s) not approved in app: levels {missing}"

    # content is ready in app. Now is the DB in sync?
    extra = db_text - sh_levels          # stale DB hint texts (May import)
    need_db_audio = sh_levels - db_audio  # spreadsheet hints lacking DB audio
    db_q_audio = d.get("audio")

    if not db_q_audio or need_db_audio:
        return "NEEDS_INGEST", (f"app-ready but DB behind: "
                                f"q_audio_in_db={db_q_audio}, hint audio missing in DB for {sorted(need_db_audio)}")
    if extra:
        return "DB_EXTRA_HINTS", f"DB has stale hint text at levels {sorted(extra)} not in spreadsheet"

    # DB matches spreadsheet, everything voiced. Are hints audio-only?
    text_for_voiced = db_text & sh_levels  # a voiced level should NOT also hold replacing text
    if text_for_voiced:
        return "NEEDS_INGEST", f"hints not audio-only in DB (text still set) at levels {sorted(text_for_voiced)}"

    return "READY", f"status={d.get('status')} (Active)" if d.get("status") == 4 else f"status={d.get('status')} (Pending)"


def main():
    ap = argparse.ArgumentParser(description="Single source of truth for question completeness (read-only).")
    ap.add_argument("--verdict", help="filter to one verdict (e.g. READY, NEEDS_INGEST)")
    ap.add_argument("--topic", help="filter to a topic name (substring match)")
    ap.add_argument("--qids-file", help="only these ItemIDs (one per line)")
    ap.add_argument("--csv", help="write full per-question CSV here")
    ap.add_argument("--no-airtable", action="store_true", help="skip Airtable (faster; image=DB only)")
    args = ap.parse_args()

    print("Loading spreadsheet...", flush=True)
    sheet = load_spreadsheet()
    print(f"  {len(sheet)} questions in spreadsheet", flush=True)
    print("Loading review app pipeline-stats...", flush=True)
    app_items = load_app()
    print(f"  {len(app_items)} items in app", flush=True)
    at_qimg = set()
    if not args.no_airtable:
        print("Loading Airtable images (all tables)...", flush=True)
        at_qimg = load_airtable_images()
        print(f"  {len(at_qimg)} question-images in Airtable", flush=True)
    print("Loading DB...", flush=True)
    cn = db_conn()
    cur = cn.cursor()
    xref, dbq, dbhints = load_db(cur)
    print(f"  {len(xref)} questions mapped in DB", flush=True)

    # which itemids to report on
    if args.qids_file:
        with open(args.qids_file) as f:
            ids = [norm(x) for x in f.read().split() if x.strip()]
    else:
        ids = list(sheet.keys())

    results = []
    for iid in ids:
        v, detail = verdict_for(iid, sheet, app_items, at_qimg, xref, dbq, dbhints)
        topic = sheet.get(norm(iid), {}).get("topic", "?")
        if args.topic and args.topic.lower() not in (topic or "").lower():
            continue
        if args.verdict and v != args.verdict.upper():
            continue
        results.append((norm(iid), v, topic, detail))

    counts = Counter(v for _, v, _, _ in results)
    print("\n=== COMPLETENESS VERDICTS ===")
    order = ["READY", "NEEDS_INGEST", "NEEDS_IMAGE_SYNC", "DB_EXTRA_HINTS", "NEEDS_IMAGE", "NEEDS_VO", "NOT_IN_DB", "NO_SPREADSHEET"]
    for v in order:
        if counts.get(v):
            print(f"   {v:<16} {counts[v]}")
    for v in counts:
        if v not in order:
            print(f"   {v:<16} {counts[v]}")
    print(f"   {'TOTAL':<16} {sum(counts.values())}")

    if args.verdict or args.topic:
        print(f"\n--- {len(results)} questions ---")
        for ni, v, topic, detail in sorted(results, key=lambda r: (r[1], r[2], r[0]))[:200]:
            print(f"   {ni:<10} {v:<15} {topic:<28} {detail}")
        if len(results) > 200:
            print(f"   ... and {len(results) - 200} more (use --csv for all)")

    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ItemID", "verdict", "topic", "detail"])
            for row in sorted(results, key=lambda r: (r[1], r[2], r[0])):
                w.writerow(row)
        print(f"\nWrote {len(results)} rows -> {args.csv}")


if __name__ == "__main__":
    main()
