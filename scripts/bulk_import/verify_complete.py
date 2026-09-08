#!/usr/bin/env python3
"""
Bulletproof READ-ONLY verifier for loaded questions. Supersedes verify_roadsafety.py.

Checks EVERY completeness + integrity dimension the audit (1 Sep 2026) said were missing:
  - Reader/Audio linked AND both are AUDIO blobs (type 111)  ← catches the collision bug
  - question IMAGE present, correct type (110), serves from CDN
  - every hint TEXT level has a hint-graphic-audio row (type 111) that serves  ← "N hints => N voiced"
  - hints are audio-only: 0 question-text-content rows still holding text (for voiced levels)
  - StatusCD as expected, PlayAudioOnRenderFlag=1
  - CDN URLs built from Blob.Path/Filename/FileTypeExtn (NEVER the ItemID)
  - fleet-wide collision guard: no Reader/AudioBlobID points at a non-111 blob
  - no duplicate blobs / hint rows for the batch

Scope: --qids-file (explicit list) or --all (whole schema, lighter checks + fleet guard).
Writes NOTHING. Exit code 0 if all pass, 1 if any problem.

USAGE
  python -m scripts.bulk_import.verify_complete --qids-file qids.txt
  python -m scripts.bulk_import.verify_complete --qids-file qids.txt --expect-active
  python -m scripts.bulk_import.verify_complete --fleet-guard   # just the DB-wide integrity guards
"""
import argparse
import struct
import sys

import requests
from azure.identity import AzureCliCredential
import pyodbc

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
CDN = "https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs"
BLOB_AUDIO = 111
BLOB_IMAGE = 110
STATUS_PENDING = 3
STATUS_ACTIVE = 4
TEXT_ELEM = "question-text-content"
HINT_AUDIO_ELEM = "hint-graphic-audio"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def cdn_ok(path, filename, ext, min_bytes=1000):
    """Build the CDN URL from Blob fields (NEVER the ItemID) and GET it."""
    url = f"{CDN}/{path}/{filename}.{ext}"
    try:
        r = requests.get(url, timeout=30)
        return r.status_code == 200 and len(r.content) >= min_bytes, r.status_code, len(r.content)
    except requests.RequestException as e:
        return False, str(e), 0


def fleet_guards(cur):
    """DB-wide integrity guards (independent of any batch). Returns list of problems."""
    problems = []
    # collision guard: Reader/Audio must be audio(111); Image must be image(110)
    for col, want, label in [("ReaderBlobID", BLOB_AUDIO, "Reader"),
                             ("AudioBlobID", BLOB_AUDIO, "Audio"),
                             ("ImageBlobID", BLOB_IMAGE, "Image")]:
        cur.execute(f"""SELECT COUNT(*) FROM {SCHEMA}.Question q JOIN {SCHEMA}.Blob b ON b.BlobID=q.{col}
                        WHERE q.{col} IS NOT NULL AND b.BlobTypeCD<>?""", (want,))
        n = cur.fetchone()[0]
        if n:
            problems.append(f"FLEET: {n} questions have {label}BlobID pointing at a wrong-type blob")
    # hint-graphic-audio rows must be audio(111)
    cur.execute(f"""SELECT COUNT(*) FROM {SCHEMA}.HintReplacement hr JOIN {SCHEMA}.Blob b ON b.BlobID=hr.BlobID
                    WHERE hr.HTMLElementID=? AND b.BlobTypeCD<>?""", (HINT_AUDIO_ELEM, BLOB_AUDIO))
    n = cur.fetchone()[0]
    if n:
        problems.append(f"FLEET: {n} hint-graphic-audio rows point at a non-audio blob")
    # dangling FKs
    for col in ["ImageBlobID", "ReaderBlobID", "AudioBlobID"]:
        cur.execute(f"""SELECT COUNT(*) FROM {SCHEMA}.Question q
                        WHERE q.{col} IS NOT NULL AND NOT EXISTS
                        (SELECT 1 FROM {SCHEMA}.Blob b WHERE b.BlobID=q.{col})""")
        n = cur.fetchone()[0]
        if n:
            problems.append(f"FLEET: {n} questions have a dangling {col}")
    return problems


def verify_batch(cur, qids, expect_active, sample_cdn=True):
    problems = []
    ph = ",".join("?" * len(qids))
    cur.execute(f"""SELECT QuestionID, StatusCD, ReaderBlobID, AudioBlobID, ImageBlobID, PlayAudioOnRenderFlag, TemplateID
                    FROM {SCHEMA}.Question WHERE QuestionID IN ({ph})""", qids)
    qrows = {r[0]: r for r in cur.fetchall()}
    want_status = STATUS_ACTIVE if expect_active else None

    for qid in qids:
        r = qrows.get(qid)
        if not r:
            problems.append(f"QID {qid}: not found in DB")
            continue
        _, status, reader, audio, image, play, tid = r

        # 1. VO linked + both are audio type
        if reader is None:
            problems.append(f"QID {qid}: ReaderBlobID NULL (no voice-over)")
        elif reader != audio:
            problems.append(f"QID {qid}: Reader({reader})!=Audio({audio})")
        else:
            cur.execute(f"SELECT BlobTypeCD,Path,Filename,FileTypeExtn FROM {SCHEMA}.Blob WHERE BlobID=?", (reader,))
            bt, p, fn, ext = cur.fetchone()
            if bt != BLOB_AUDIO:
                problems.append(f"QID {qid}: Reader blob {reader} is type {bt} not audio(111) — COLLISION BUG")
            elif sample_cdn:
                ok, code, sz = cdn_ok(p, fn, ext)
                if not ok:
                    problems.append(f"QID {qid}: question audio CDN fail {code} ({p}/{fn}.{ext})")

        # 2. image present + correct type + serves
        if image is None:
            problems.append(f"QID {qid}: ImageBlobID NULL (every question needs an image)")
        else:
            cur.execute(f"SELECT BlobTypeCD,Path,Filename,FileTypeExtn FROM {SCHEMA}.Blob WHERE BlobID=?", (image,))
            bt, p, fn, ext = cur.fetchone()
            if bt != BLOB_IMAGE:
                problems.append(f"QID {qid}: Image blob {image} is type {bt} not image(110)")
            elif sample_cdn:
                ok, code, sz = cdn_ok(p, fn, ext, min_bytes=500)
                if not ok:
                    problems.append(f"QID {qid}: question image CDN fail {code} ({p}/{fn}.{ext})")

        # 3. every hint text level has a voiced hint-graphic-audio row that serves
        cur.execute(f"""SELECT DISTINCT HintLevelNum FROM {SCHEMA}.HintReplacement
                        WHERE QuestionID=? AND HTMLElementID=? AND HintHTML<>''""", (qid, TEXT_ELEM))
        text_levels = {row[0] for row in cur.fetchall()}
        cur.execute(f"""SELECT hr.HintLevelNum, b.BlobTypeCD, b.Path, b.Filename, b.FileTypeExtn
                        FROM {SCHEMA}.HintReplacement hr JOIN {SCHEMA}.Blob b ON b.BlobID=hr.BlobID
                        WHERE hr.QuestionID=? AND hr.HTMLElementID=?""", (qid, HINT_AUDIO_ELEM))
        audio_levels = {}
        for lvl, bt, p, fn, ext in cur.fetchall():
            audio_levels[lvl] = (bt, p, fn, ext)
        # every ACTIVE hint level must have audio. Only count levels whose parent QuestionHint
        # is StatusCD=4 (Active) — deactivated (stale) levels are not served by the portal
        # (GetNextQuestion counts only StatusCD=4 hints), so they must be ignored here too.
        cur.execute(f"""SELECT DISTINCT hr.HintLevelNum
                        FROM {SCHEMA}.HintReplacement hr
                        JOIN {SCHEMA}.QuestionHint qh
                          ON qh.QuestionID=hr.QuestionID AND qh.HintLevelNum=hr.HintLevelNum
                        WHERE hr.QuestionID=? AND hr.HTMLElementID=? AND qh.StatusCD=?""",
                    (qid, TEXT_ELEM, STATUS_ACTIVE))
        all_text_levels = {row[0] for row in cur.fetchall()}
        for lvl in all_text_levels:
            if lvl not in audio_levels:
                problems.append(f"QID {qid}: hint level {lvl} has NO voice-over")
            else:
                bt, p, fn, ext = audio_levels[lvl]
                if bt != BLOB_AUDIO:
                    problems.append(f"QID {qid}: hint {lvl} audio blob is type {bt} not 111")
                elif sample_cdn:
                    ok, code, sz = cdn_ok(p, fn, ext)
                    if not ok:
                        problems.append(f"QID {qid}: hint {lvl} audio CDN fail {code}")

        # 4. audio-only: no text-replace rows still holding text (for levels that have audio)
        cur.execute(f"""SELECT COUNT(*) FROM {SCHEMA}.HintReplacement
                        WHERE QuestionID=? AND HTMLElementID=? AND HintHTML<>''""", (qid, TEXT_ELEM))
        still_text = cur.fetchone()[0]
        if still_text and any(l in audio_levels for l in text_levels):
            problems.append(f"QID {qid}: {still_text} hint-text rows still replace the question text (not audio-only)")

        # 5. Select All needs option images
        if tid == 2:
            cur.execute(f"""SELECT COUNT(*), SUM(CASE WHEN ImageBlobID IS NOT NULL THEN 1 ELSE 0 END)
                            FROM {SCHEMA}.SelectionOption WHERE QuestionID=?""", (qid,))
            nopt, nimg = cur.fetchone()
            nimg = nimg or 0
            if nopt and nimg < nopt:
                problems.append(f"QID {qid}: Select All has {nimg}/{nopt} option images (template needs all)")

        # 6. status
        if want_status and status != want_status:
            problems.append(f"QID {qid}: StatusCD {status}, expected {want_status}")
        if reader is not None and play != 1:
            problems.append(f"QID {qid}: PlayAudioOnRenderFlag={play} (expected 1)")

    # duplicates within the batch
    cur.execute(f"""SELECT QuestionID,HintLevelNum,HTMLElementID,COUNT(*) c
                    FROM {SCHEMA}.HintReplacement WHERE QuestionID IN ({ph})
                    GROUP BY QuestionID,HintLevelNum,HTMLElementID HAVING COUNT(*)>1""", qids)
    for q, l, e, c in cur.fetchall():
        problems.append(f"QID {q}: duplicate HintReplacement L{l}/{e} (x{c})")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qids-file", help="file with one QuestionID per line")
    ap.add_argument("--fleet-guard", action="store_true", help="run only the DB-wide integrity guards")
    ap.add_argument("--expect-active", action="store_true", help="assert the batch is StatusCD=4")
    ap.add_argument("--no-cdn", action="store_true", help="skip CDN GETs (faster, DB-only)")
    args = ap.parse_args()

    conn = db_conn()
    cur = conn.cursor()

    print("=== FLEET-WIDE INTEGRITY GUARDS ===")
    fp = fleet_guards(cur)
    if fp:
        for p in fp:
            print("  ✗ " + p)
    else:
        print("  ✓ no wrong-type links, no dangling FKs (whole schema)")

    bp = []
    if not args.fleet_guard:
        if not args.qids_file:
            print("\n(no --qids-file given; ran fleet guards only)")
        else:
            qids = [int(l.strip()) for l in open(args.qids_file) if l.strip()]
            print(f"\n=== BATCH VERIFY ({len(qids)} questions) ===")
            bp = verify_batch(cur, qids, args.expect_active, sample_cdn=not args.no_cdn)
            if bp:
                for p in bp:
                    print("  ✗ " + p)
            else:
                print(f"  ✓ all {len(qids)} fully complete: VO+image+every hint voiced+audio-only"
                      + (", Active" if args.expect_active else ""))

    total = len(fp) + len(bp)
    print("\n" + "=" * 50)
    print(f"  PROBLEMS: {total}")
    conn.close()
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
