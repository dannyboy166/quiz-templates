#!/usr/bin/env python3
"""
Make hints AUDIO-ONLY (Zoe's decision): the hint voice-over plays, but the question
text is NOT replaced by hint wording.

MECHANISM (verified against Victor's code):
  - Student app only replaces the question text if the `question-text-content`
    HintReplacement row has NON-EMPTY HintHTML (BaseQuestionTemplate.GetHintHtmlForElement).
  - So we set HintHTML='' on those rows. The app then shows the original question text.
  - The `hint-graphic-audio` rows (the voice-over) are LEFT UNTOUCHED.

SAFETY
  - NO DELETE. Only UPDATE HintHTML -> '' on question-text-content rows (CLAUDE.md compliant).
  - Snapshots each row's original HintHTML to a revert file BEFORE changing.
  - --revert restores every original HintHTML from the snapshot.
  - Scoped to an explicit QID range (default the 42 Road Safety: 4966-5010).
  - Logs run time to ingest_run_log.txt (Victor's restore requirement).

USAGE
  python -m scripts.bulk_import.set_hints_audio_only --dry-run
  python -m scripts.bulk_import.set_hints_audio_only --apply
  python -m scripts.bulk_import.set_hints_audio_only --revert
"""
import argparse
import json
import struct
from pathlib import Path

from azure.identity import AzureCliCredential
import pyodbc

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
USER_ID = 8
QID_LO, QID_HI = 4966, 5010
TEXT_ELEM = "question-text-content"
SNAP = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/hints_audio_only_revert.json"
LOG = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/ingest_run_log.txt"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def _scope(cur, qids):
    """Return (where_clause, params) restricting to an explicit QID list if given,
    else the default Road Safety range."""
    if qids:
        ph = ",".join("?" * len(qids))
        return f"QuestionID IN ({ph})", list(qids)
    return "QuestionID BETWEEN ? AND ?", [QID_LO, QID_HI]


def target_rows(cur, qids=None):
    """question-text-content hint rows with text — but ONLY where a matching
    hint-graphic-audio voice-over exists for that Q+level (never leaves an empty hint)."""
    where, params = _scope(cur, qids)
    cur.execute(f"""SELECT tr.QuestionID, tr.HintLevelNum, tr.TemplateName, tr.HintHTML
                    FROM {SCHEMA}.HintReplacement tr
                    WHERE tr.{where}
                      AND tr.HTMLElementID = ?
                      AND tr.HintHTML IS NOT NULL AND tr.HintHTML <> ''
                      AND EXISTS (SELECT 1 FROM {SCHEMA}.HintReplacement ar
                                  WHERE ar.QuestionID=tr.QuestionID
                                    AND ar.HintLevelNum=tr.HintLevelNum
                                    AND ar.HTMLElementID='hint-graphic-audio'
                                    AND ar.BlobID IS NOT NULL)
                    ORDER BY tr.QuestionID, tr.HintLevelNum""",
                params + [TEXT_ELEM])
    return cur.fetchall()


def orphan_text_rows(cur, qids=None):
    """Text-replace rows that would be blanked EXCEPT they have no audio — we skip these
    so we never create an empty hint. Reported for visibility."""
    where, params = _scope(cur, qids)
    cur.execute(f"""SELECT tr.QuestionID, tr.HintLevelNum
                    FROM {SCHEMA}.HintReplacement tr
                    WHERE tr.{where}
                      AND tr.HTMLElementID = ?
                      AND tr.HintHTML IS NOT NULL AND tr.HintHTML <> ''
                      AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.HintReplacement ar
                                  WHERE ar.QuestionID=tr.QuestionID
                                    AND ar.HintLevelNum=tr.HintLevelNum
                                    AND ar.HTMLElementID='hint-graphic-audio'
                                    AND ar.BlobID IS NOT NULL)""",
                params + [TEXT_ELEM])
    return cur.fetchall()


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qids-file", help="file with one QuestionID per line (else Road Safety range)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    qids = None
    tag = "roadsafety"
    if args.qids_file:
        qids = [int(l.strip()) for l in Path(args.qids_file).read_text().splitlines() if l.strip()]
        tag = Path(args.qids_file).stem
    # per-batch revert snapshot so batches never clobber each other
    snap_path = SNAP.parent / f"hints_audio_only_revert_{tag}.json"

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT SYSUTCDATETIME()")
    utc = cur.fetchone()[0]

    if args.revert:
        if not snap_path.exists():
            print(f"No revert file at {snap_path} — nothing to revert.")
            return
        snap = json.loads(snap_path.read_text())
        n = 0
        for r in snap["rows"]:
            cur.execute(f"""UPDATE {SCHEMA}.HintReplacement SET HintHTML=?,
                            LastModTime=GETDATE(), LastModUserID=?
                            WHERE QuestionID=? AND HintLevelNum=? AND TemplateName=? AND HTMLElementID=?""",
                        (r["HintHTML"], USER_ID, r["QuestionID"], r["HintLevelNum"], r["TemplateName"], TEXT_ELEM))
            n += cur.rowcount
        conn.commit()
        print(f"Reverted {n} rows from {snap_path.name} — original hint text restored.")
        log(f"\nHINTS AUDIO-ONLY REVERT ({tag})\n  UTC: {utc}\n  restored HintHTML on {n} rows\n")
        conn.close()
        return

    rows = target_rows(cur, qids)            # only rows WITH matching audio (safe)
    orphans = orphan_text_rows(cur, qids)    # text rows WITHOUT audio — skipped, reported

    print(f"Text-replace rows that will be blanked (all have matching audio): {len(rows)}")
    if orphans:
        print(f"  SKIPPING {len(orphans)} text hint(s) that have NO audio (would go empty): "
              f"{[(q,l) for q,l in orphans][:10]}")

    if not args.apply:
        print("\nSample of what will be blanked (text stays in DB backup, question text will show again):")
        for q, l, t, h in rows[:5]:
            print(f"  QID {q} L{l}: {h[:70]!r} -> ''")
        print("\nDRY-RUN — nothing written. Re-run with --apply.")
        conn.close()
        return

    # snapshot BEFORE (per-batch file)
    snap = {"utc": str(utc), "tag": tag,
            "rows": [{"QuestionID": q, "HintLevelNum": l, "TemplateName": t, "HintHTML": h}
                     for q, l, t, h in rows]}
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, indent=2))
    print(f"\nRevert snapshot written: {snap_path}  ({len(rows)} rows)")

    n = 0
    for q, l, t, h in rows:
        cur.execute(f"""UPDATE {SCHEMA}.HintReplacement SET HintHTML='',
                        LastModTime=GETDATE(), LastModUserID=?
                        WHERE QuestionID=? AND HintLevelNum=? AND TemplateName=? AND HTMLElementID=?""",
                    (USER_ID, q, l, t, TEXT_ELEM))
        n += cur.rowcount
    conn.commit()

    left = target_rows(cur, qids)
    print(f"Blanked {n} rows. Text-replace rows (with audio) still holding text: {len(left)} (expect 0)")
    log(f"\nHINTS AUDIO-ONLY ({tag})\n  UTC: {utc}\n  blanked HintHTML on {n} text rows; "
        f"audio hints untouched; {len(orphans)} orphan text rows left as-is (revert: {snap_path.name})\n")
    conn.close()


if __name__ == "__main__":
    main()
