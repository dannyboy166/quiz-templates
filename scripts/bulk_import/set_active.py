#!/usr/bin/env python3
"""
Flip an explicit list of questions StatusCD 3 (Pending) -> 4 (Active) in DevTest.
General-purpose (any batch). Reversible per-batch.

SAFETY
  - Snapshots each QID's CURRENT StatusCD to a per-batch revert file BEFORE changing.
  - --revert restores every question to its prior StatusCD from that file.
  - Only flips rows currently at StatusCD=3 that HAVE a voice-over (ReaderBlobID set) —
    a guard so we never activate a question that isn't actually loaded/complete.
  - Logs run time (Victor's restore requirement).

USAGE
  python -m scripts.bulk_import.set_active --qids-file qids.txt --dry-run
  python -m scripts.bulk_import.set_active --qids-file qids.txt --apply
  python -m scripts.bulk_import.set_active --qids-file qids.txt --revert
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
PENDING = 3
ACTIVE = 4
BK = Path(__file__).resolve().parent.parent.parent / "data/questions/backups"
LOG = BK / "ingest_run_log.txt"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def rows_for(cur, qids):
    ph = ",".join("?" * len(qids))
    cur.execute(f"""SELECT QuestionID, StatusCD, ReaderBlobID FROM {SCHEMA}.Question
                    WHERE QuestionID IN ({ph}) ORDER BY QuestionID""", qids)
    return cur.fetchall()


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qids-file", required=True, help="file with one QuestionID per line")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    qids = [int(l.strip()) for l in Path(args.qids_file).read_text().splitlines() if l.strip()]
    tag = Path(args.qids_file).stem
    snap_path = BK / f"status_revert_{tag}.json"

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
            cur.execute(f"""UPDATE {SCHEMA}.Question SET StatusCD=?, LastModTime=GETDATE(), LastModUserID=?
                            WHERE QuestionID=?""", (r["prev_status"], USER_ID, r["qid"]))
            n += cur.rowcount
        conn.commit()
        print(f"Reverted {n} rows to prior StatusCD (from {snap_path.name}).")
        log(f"\nSTATUS REVERT ({tag})\n  UTC: {utc}\n  reverted {n} rows\n")
        conn.close()
        return

    rows = rows_for(cur, qids)
    to_flip = [(q, s) for q, s, r in rows if s == PENDING and r is not None]
    no_vo = [q for q, s, r in rows if r is None]
    already_active = [q for q, s, r in rows if s == ACTIVE]

    print(f"Requested: {len(qids)}  | found: {len(rows)}")
    print(f"Will flip Pending->Active: {len(to_flip)}")
    if already_active:
        print(f"  already Active (skip): {len(already_active)}")
    if no_vo:
        print(f"  ⚠️  {len(no_vo)} have NO voice-over — NOT activating (not complete): {no_vo[:10]}")

    if not args.apply:
        print("\nDRY-RUN — nothing written. Re-run with --apply.")
        conn.close()
        return

    # snapshot ALL requested rows' current status before change
    snap = {"utc": str(utc), "tag": tag,
            "rows": [{"qid": q, "prev_status": s} for q, s, r in rows]}
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, indent=2))
    print(f"\nRevert snapshot: {snap_path}  ({len(rows)} rows)")

    ph = ",".join("?" * len(qids))
    cur.execute(f"""UPDATE {SCHEMA}.Question SET StatusCD=?, LastModTime=GETDATE(), LastModUserID=?
                    WHERE QuestionID IN ({ph}) AND StatusCD=? AND ReaderBlobID IS NOT NULL""",
                [ACTIVE, USER_ID] + qids + [PENDING])
    n = cur.rowcount
    conn.commit()

    rows2 = rows_for(cur, qids)
    active = sum(1 for q, s, r in rows2 if s == ACTIVE)
    print(f"Flipped {n} rows. Now Active: {active}/{len(rows2)}")
    log(f"\nSTATUS -> ACTIVE ({tag})\n  UTC: {utc}\n  flipped {n} rows 3->4 (revert: {snap_path.name})\n")
    conn.close()


if __name__ == "__main__":
    main()
