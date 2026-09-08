"""Clear Question.AudioBlobID on questions we bulk-loaded (keep ReaderBlobID).

Why: our earlier ingest set BOTH ReaderBlobID and AudioBlobID to the question voice-over.
AudioBlobID makes the student's IMAGE replay the question audio on hover — Zoe/Dan decided
the question audio should play from ONE place only (the Reader speaker on the question text),
so we null AudioBlobID on the already-loaded questions. (ingest_voiceovers.py no longer sets
it going forward.)

SAFE: DRY-RUN by default. --apply to write. Only nulls AudioBlobID; touches nothing else.
Only targets questions where AudioBlobID == ReaderBlobID (i.e. the ones WE set to the VO) —
never a question whose AudioBlobID is a different, deliberate blob. Writes a JSON snapshot of
(QuestionID, old AudioBlobID) so it can be reverted.

Usage:
  python -m scripts.bulk_import.clear_question_audioblob --dry-run
  python -m scripts.bulk_import.clear_question_audioblob --apply
  python -m scripts.bulk_import.clear_question_audioblob --revert snapshot.json --apply
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from azure.identity import AzureCliCredential
import pyodbc

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
USER_ID = 8


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def find_targets(conn):
    """Questions where AudioBlobID is set AND equals ReaderBlobID (the ones we set)."""
    cur = conn.cursor()
    cur.execute(f"""
        SELECT QuestionID, AudioBlobID, ReaderBlobID
          FROM {SCHEMA}.Question
         WHERE AudioBlobID IS NOT NULL
           AND AudioBlobID = ReaderBlobID
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def clear_audio(conn, qid):
    cur = conn.cursor()
    cur.execute(f"""UPDATE {SCHEMA}.Question
                       SET AudioBlobID = NULL, LastModTime = GETDATE(), LastModUserID = ?
                     WHERE QuestionID = ? AND AudioBlobID = ReaderBlobID""", (USER_ID, qid))
    n = cur.rowcount
    conn.commit()
    return n


def restore_audio(conn, qid, blob_id):
    cur = conn.cursor()
    cur.execute(f"""UPDATE {SCHEMA}.Question
                       SET AudioBlobID = ?, LastModTime = GETDATE(), LastModUserID = ?
                     WHERE QuestionID = ?""", (blob_id, USER_ID, qid))
    conn.commit()
    return cur.rowcount


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", help="path to a snapshot JSON to restore AudioBlobID from")
    ap.add_argument("--snapshot", default="audioblob_snapshot.json",
                    help="where to write the before-state (for revert)")
    args = ap.parse_args()
    apply = args.apply

    conn = db_conn()

    if args.revert:
        snap = json.loads(Path(args.revert).read_text())
        print(f"REVERT: restoring AudioBlobID on {len(snap)} questions from {args.revert}")
        if not apply:
            print("DRY-RUN — re-run with --apply to write."); return
        for row in snap:
            restore_audio(conn, row["QuestionID"], row["AudioBlobID"])
        print("Reverted.")
        return

    targets = find_targets(conn)
    print(f"Found {len(targets)} questions with AudioBlobID == ReaderBlobID (set by our ingest).")
    for qid, bid in targets[:10]:
        print(f"  QID {qid}: AudioBlobID {bid} -> NULL")
    if len(targets) > 10:
        print(f"  … and {len(targets) - 10} more")

    if not apply:
        print("\nDRY-RUN — nothing written. Re-run with --apply to clear AudioBlobID.")
        return

    # snapshot first (for revert)
    Path(args.snapshot).write_text(json.dumps(
        [{"QuestionID": q, "AudioBlobID": b} for q, b in targets], indent=2))
    print(f"Wrote snapshot to {args.snapshot}")

    cleared = sum(clear_audio(conn, qid) for qid, _ in targets)
    print(f"Cleared AudioBlobID on {cleared} questions.")


if __name__ == "__main__":
    main()
