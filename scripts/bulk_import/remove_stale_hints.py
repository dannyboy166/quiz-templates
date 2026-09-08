#!/usr/bin/env python3
"""
Remove STALE hint levels from the DB — hints that exist in the database (from the old
May bulk import, which loaded 3 hint texts) but that the SPREADSHEET (source of truth)
does NOT have. Dan's rule: "# hint texts in the spreadsheet = # hints the question has."

Safe by construction:
  - SPREADSHEET is truth. We only touch a (QuestionID, HintLevelNum) whose level is NOT
    present in the spreadsheet for that ItemID. A real, spreadsheet-backed hint is never touched.
  - We also refuse to touch any level that has a hint-graphic-audio BLOB (never remove a voiced hint).
  - NO hard DELETE. We set HintReplacement.HintHTML = '' on the stale text rows and set the
    parent QuestionHint.StatusCD = 6 (Deactivated) so it stops being served. (CLAUDE.md: no deletes.)
  - Full revert snapshot written; --revert restores it.

USAGE
  python -m scripts.bulk_import.remove_stale_hints --qids-file q.txt            # dry-run
  python -m scripts.bulk_import.remove_stale_hints --qids-file q.txt --apply
  python -m scripts.bulk_import.remove_stale_hints --qids-file q.txt --revert
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from azure.identity import AzureCliCredential
import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from review_app.spreadsheet_loader import load_all_questions  # noqa: E402

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
STATUS_DEACTIVATED = 6
ROOT = Path(__file__).resolve().parent.parent.parent
BACKUPS = ROOT / "data/questions/backups"
LOG = BACKUPS / "ingest_run_log.txt"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def norm(x):
    s = str(x).strip()
    return s.lstrip("0") or s


def spreadsheet_hint_levels():
    """ItemID(norm) -> set of hint levels present in the spreadsheet."""
    questions, *_ = load_all_questions()
    rows = questions.values() if isinstance(questions, dict) else questions
    out = {}
    for q in rows:
        iid = str(q.get("item_id") or q.get("ItemID") or "").strip()
        if iid:
            out[norm(iid)] = set(h for h in (1, 2, 3) if (q.get(f"hint{h}") or "").strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qids-file", required=True, help="one QuestionID per line")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    ap.add_argument("--tag", default="", help="suffix for the revert snapshot file")
    args = ap.parse_args()

    qids = [int(x) for x in Path(args.qids_file).read_text().split() if x.strip()]
    tag = args.tag or Path(args.qids_file).stem
    snap_path = BACKUPS / f"stale_hints_revert_{tag}.json"

    cn = db_conn()
    cur = cn.cursor()

    if args.revert:
        if not snap_path.exists():
            print(f"No snapshot at {snap_path}")
            return
        snap = json.loads(snap_path.read_text())
        for r in snap["blanked_text"]:
            cur.execute(f"""UPDATE {SCHEMA}.HintReplacement SET HintHTML=?
                            WHERE QuestionID=? AND HintLevelNum=? AND TemplateName=? AND HTMLElementID=?""",
                        r["HintHTML"], r["QuestionID"], r["HintLevelNum"], r["TemplateName"], r["HTMLElementID"])
        for r in snap["deactivated_hint"]:
            cur.execute(f"""UPDATE {SCHEMA}.QuestionHint SET StatusCD=?
                            WHERE QuestionID=? AND HintLevelNum=?""",
                        r["StatusCD"], r["QuestionID"], r["HintLevelNum"])
        cn.commit()
        print(f"Reverted {len(snap['blanked_text'])} text rows + {len(snap['deactivated_hint'])} QuestionHint rows.")
        return

    # map qid -> itemid via SpreadsheetXRef
    ph = ",".join("?" * len(qids))
    cur.execute(f"""SELECT QuestionID, SpreadsheetRecordID FROM {SCHEMA}.SpreadsheetXRef
                    WHERE TableName='Question' AND QuestionID IN ({ph})""", qids)
    qid_item = {q: norm(r) for q, r in cur.fetchall()}

    sheet = spreadsheet_hint_levels()

    # find DB hint levels per qid
    cur.execute(f"""SELECT QuestionID, HintLevelNum FROM {SCHEMA}.QuestionHint
                    WHERE QuestionID IN ({ph})""", qids)
    db_levels = {}
    for q, lvl in cur.fetchall():
        db_levels.setdefault(q, set()).add(lvl)

    # determine stale levels = in DB but NOT in spreadsheet, AND with no audio blob
    stale = []   # (qid, level)
    for q in qids:
        item = qid_item.get(q)
        sh = sheet.get(item, set()) if item else set()
        for lvl in sorted(db_levels.get(q, set())):
            if lvl in sh:
                continue  # real hint per spreadsheet — never touch
            # guard: does this level have a voiced audio blob? if so, DO NOT remove.
            cur.execute(f"""SELECT COUNT(*) FROM {SCHEMA}.HintReplacement
                            WHERE QuestionID=? AND HintLevelNum=? AND HTMLElementID='hint-graphic-audio'
                              AND BlobID IS NOT NULL""", q, lvl)
            if cur.fetchone()[0]:
                print(f"  GUARD: QID {q} level {lvl} has audio — NOT removing (unexpected; check).")
                continue
            stale.append((q, lvl))

    print(f"Questions: {len(qids)}  |  stale hint levels to remove (in DB, not in spreadsheet, no audio): {len(stale)}")
    if stale[:12]:
        print("  sample:", stale[:12])

    if not args.apply:
        print("\nDRY-RUN — nothing written. Re-run with --apply.")
        return

    # snapshot everything we will change
    blanked_text, deactivated_hint = [], []
    for q, lvl in stale:
        cur.execute(f"""SELECT QuestionID, HintLevelNum, TemplateName, HTMLElementID, HintHTML
                        FROM {SCHEMA}.HintReplacement WHERE QuestionID=? AND HintLevelNum=?""", q, lvl)
        for row in cur.fetchall():
            blanked_text.append({"QuestionID": row[0], "HintLevelNum": row[1], "TemplateName": row[2],
                                 "HTMLElementID": row[3], "HintHTML": row[4]})
        cur.execute(f"SELECT StatusCD FROM {SCHEMA}.QuestionHint WHERE QuestionID=? AND HintLevelNum=?", q, lvl)
        r = cur.fetchone()
        if r:
            deactivated_hint.append({"QuestionID": q, "HintLevelNum": lvl, "StatusCD": r[0]})

    snap_path.write_text(json.dumps({"blanked_text": blanked_text, "deactivated_hint": deactivated_hint}, indent=1))
    print(f"Revert snapshot: {snap_path}  ({len(blanked_text)} replacement rows, {len(deactivated_hint)} QuestionHint rows)")

    # apply: blank the text rows, deactivate the QuestionHint for the stale level
    for q, lvl in stale:
        cur.execute(f"""UPDATE {SCHEMA}.HintReplacement SET HintHTML=''
                        WHERE QuestionID=? AND HintLevelNum=? AND HTMLElementID='question-text-content'""", q, lvl)
        cur.execute(f"""UPDATE {SCHEMA}.QuestionHint SET StatusCD=?
                        WHERE QuestionID=? AND HintLevelNum=?""", STATUS_DEACTIVATED, q, lvl)
    cn.commit()
    print(f"Applied: blanked stale text + deactivated {len(stale)} stale QuestionHint levels.")

    from datetime import datetime, timezone
    with open(LOG, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} | remove_stale_hints tag={tag}: "
                f"removed {len(stale)} stale hint levels (spreadsheet-confirmed). snapshot {snap_path.name}\n")


if __name__ == "__main__":
    main()
