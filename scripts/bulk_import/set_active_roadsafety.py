#!/usr/bin/env python3
"""
Flip the 42 Road Safety batch questions StatusCD 3 (Pending) -> 4 (Active) in DevTest.

REVERSIBLE BY DESIGN:
  - Before changing anything, snapshots each QuestionID's CURRENT StatusCD to a
    revert file (data/questions/backups/roadsafety_status_revert.json).
  - --revert reads that file and restores every question to its prior StatusCD.
  - Only touches the explicit ID range 4966-5010 (the 42 we ingested), and only
    rows currently at StatusCD=3 (won't disturb anything already Active).
  - Logs run time (Victor asked us to keep timestamps for DB restore).

USAGE
  python -m scripts.bulk_import.set_active_roadsafety --dry-run
  python -m scripts.bulk_import.set_active_roadsafety --apply
  python -m scripts.bulk_import.set_active_roadsafety --revert
"""
import argparse
import json
import struct
from datetime import datetime
from pathlib import Path

from azure.identity import AzureCliCredential
import pyodbc

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
USER_ID = 8
PENDING = 3
ACTIVE = 4
QID_LO, QID_HI = 4966, 5010     # the 42 Road Safety questions we ingested
REVERT = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/roadsafety_status_revert.json"
LOG = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/ingest_run_log.txt"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def current_rows(cur):
    """Return [(QuestionID, StatusCD, ReaderBlobID)] for our ingested batch."""
    cur.execute(f"""SELECT QuestionID, StatusCD, ReaderBlobID
                    FROM {SCHEMA}.Question
                    WHERE QuestionID BETWEEN ? AND ? AND ReaderBlobID IS NOT NULL
                    ORDER BY QuestionID""", (QID_LO, QID_HI))
    return cur.fetchall()


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT SYSUTCDATETIME()")
    utc = cur.fetchone()[0]

    if args.revert:
        if not REVERT.exists():
            print(f"No revert file at {REVERT} — nothing to revert.")
            return
        snap = json.loads(REVERT.read_text())
        print(f"Reverting {len(snap['rows'])} questions to their pre-flip StatusCD...")
        n = 0
        for row in snap["rows"]:
            qid, prev = row["qid"], row["prev_status"]
            cur.execute(f"""UPDATE {SCHEMA}.Question
                            SET StatusCD=?, LastModTime=GETDATE(), LastModUserID=?
                            WHERE QuestionID=?""", (prev, USER_ID, qid))
            n += cur.rowcount
        conn.commit()
        # verify
        rows = current_rows(cur)
        pend = sum(1 for _, s, _ in rows if s == PENDING)
        print(f"Reverted {n} rows. Now Pending: {pend}/{len(rows)}")
        log(f"\nROADSAFETY STATUS REVERT\n  UTC: {utc}\n  reverted {n} rows -> prior StatusCD\n")
        conn.close()
        return

    rows = current_rows(cur)
    print(f"Batch questions found (4966-5010, audio-linked): {len(rows)}")
    by_status = {}
    for _, s, _ in rows:
        by_status[s] = by_status.get(s, 0) + 1
    print(f"Current StatusCD: {by_status}")
    to_flip = [(q, s) for q, s, _ in rows if s == PENDING]
    print(f"Will flip {len(to_flip)} rows from Pending(3) -> Active(4)")
    already = [q for q, s, _ in rows if s == ACTIVE]
    if already:
        print(f"  ({len(already)} already Active — left untouched)")

    if not args.apply:
        print("\nDRY-RUN — nothing written. Re-run with --apply to flip.")
        conn.close()
        return

    # snapshot BEFORE changing (revert safety) — records every row's prior status
    snap = {"utc": str(utc),
            "rows": [{"qid": q, "prev_status": s} for q, s, _ in rows]}
    REVERT.parent.mkdir(parents=True, exist_ok=True)
    REVERT.write_text(json.dumps(snap, indent=2))
    print(f"\nRevert snapshot written: {REVERT}")

    cur.execute(f"""UPDATE {SCHEMA}.Question
                    SET StatusCD=?, LastModTime=GETDATE(), LastModUserID=?
                    WHERE QuestionID BETWEEN ? AND ? AND ReaderBlobID IS NOT NULL
                          AND StatusCD=?""",
                (ACTIVE, USER_ID, QID_LO, QID_HI, PENDING))
    n = cur.rowcount
    conn.commit()

    # verify
    rows2 = current_rows(cur)
    active = sum(1 for _, s, _ in rows2 if s == ACTIVE)
    print(f"Flipped {n} rows. Now Active: {active}/{len(rows2)}")
    log(f"\nROADSAFETY STATUS -> ACTIVE\n  UTC: {utc}\n  flipped {n} rows 3->4 "
        f"(revert file: {REVERT.name})\n")
    conn.close()


if __name__ == "__main__":
    main()
