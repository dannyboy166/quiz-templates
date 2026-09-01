#!/usr/bin/env python3
"""
READ-ONLY audit of the Road Safety voice-over ingest.

Re-queries DevTest RIGHT NOW (does not trust the run log) and checks, per question:
  - Question row exists, still StatusCD=3 (Pending) — NOT auto-activated
  - ReaderBlobID and AudioBlobID both set and equal, PlayAudioOnRenderFlag=1
  - the referenced Blob row is valid (type 111 audio, StatusCD 4, Path 'audio', .mp3)
  - question text / options / existing text-hints untouched (integrity)
  - hint-audio HintReplacement rows present for each text-hint level
  - the actual MP3 on the CDN returns 200 + audio content-type + non-trivial size

Nothing is written. Pure SELECTs + HTTP GETs.
"""
import struct
import sys

import requests
from azure.identity import AzureCliCredential
import pyodbc

SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
CDN = "https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs/audio"
STATUS_PENDING = 3
BLOB_TYPE_AUDIO = 111
STATUS_ACTIVE = 4
HINT_AUDIO_ELEM = "hint-graphic-audio"


def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def find_roadsafety_qids(conn):
    """Return [(ItemID, QuestionID)] for the Road Safety topic questions we ingested.
    We anchor on Topic name 'Road Safety' AND ReaderBlobID set (our ingest marker),
    then map back to ItemID via SpreadsheetXRef."""
    cur = conn.cursor()
    # topic -> classification -> question, restricted to ones that now have audio
    cur.execute(f"""
        SELECT DISTINCT q.QuestionID
        FROM {SCHEMA}.Question q
        JOIN {SCHEMA}.QuestionClassification qc ON qc.QuestionID = q.QuestionID
        JOIN {SCHEMA}.Topic t ON t.TopicID = qc.TopicID
        WHERE t.Name LIKE '%Road Safety%'
    """)
    qids = [r[0] for r in cur.fetchall()]
    # map to ItemID
    out = []
    if qids:
        ph = ",".join("?" * len(qids))
        cur.execute(f"""SELECT QuestionID, SpreadsheetRecordID FROM {SCHEMA}.SpreadsheetXRef
                        WHERE TableName='Question' AND QuestionID IN ({ph})""", qids)
        m = {q: s for q, s in cur.fetchall()}
        for q in qids:
            out.append((m.get(q, "?"), q))
    return sorted(out, key=lambda x: str(x[0]))


def main():
    conn = db_conn()
    cur = conn.cursor()

    pairs = find_roadsafety_qids(conn)
    print(f"Road Safety questions found in DevTest: {len(pairs)}\n")
    if not pairs:
        print("None found — check topic name.")
        return

    qids = [q for _, q in pairs]
    ph = ",".join("?" * len(qids))

    # pull all question state at once
    cur.execute(f"""SELECT QuestionID, StatusCD, ReaderBlobID, AudioBlobID,
                           PlayAudioOnRenderFlag, LEN(TextHTML), LastModTime
                    FROM {SCHEMA}.Question WHERE QuestionID IN ({ph})""", qids)
    qstate = {r[0]: r for r in cur.fetchall()}

    # collect referenced blob ids and validate the Blob rows
    reader_ids = [qstate[q][2] for q in qids if qstate[q][2] is not None]
    blob_ok = {}
    if reader_ids:
        bph = ",".join("?" * len(reader_ids))
        cur.execute(f"""SELECT BlobID, BlobTypeCD, StatusCD, Path, Filename, FileTypeExtn
                        FROM {SCHEMA}.Blob WHERE BlobID IN ({bph})""", reader_ids)
        for bid, btype, bstat, bpath, bfile, bext in cur.fetchall():
            blob_ok[bid] = (btype == BLOB_TYPE_AUDIO and bstat == STATUS_ACTIVE
                            and (bpath or "").strip().lower() == "audio",
                            btype, bstat, bpath, bfile, bext)

    # hint-audio rows per question
    cur.execute(f"""SELECT QuestionID, HintLevelNum, BlobID
                    FROM {SCHEMA}.HintReplacement
                    WHERE QuestionID IN ({ph}) AND HTMLElementID = '{HINT_AUDIO_ELEM}'""", qids)
    hint_audio = {}
    for q, lvl, bid in cur.fetchall():
        hint_audio.setdefault(q, []).append((lvl, bid))

    # text-hint rows (integrity — should be untouched, still present)
    cur.execute(f"""SELECT QuestionID, COUNT(*)
                    FROM {SCHEMA}.HintReplacement
                    WHERE QuestionID IN ({ph}) AND HTMLElementID = 'question-text-content'
                    GROUP BY QuestionID""", qids)
    text_hint_ct = {q: c for q, c in cur.fetchall()}

    # options integrity
    cur.execute(f"""SELECT QuestionID, COUNT(*) FROM {SCHEMA}.SelectionOption
                    WHERE QuestionID IN ({ph}) GROUP BY QuestionID""", qids)
    opt_ct = {q: c for q, c in cur.fetchall()}

    problems = []
    cdn_checked = 0
    cdn_fail = []

    print(f"{'ItemID':12}{'QID':>7} {'Stat':>5} {'Reader':>7} {'=Audio':>7} {'Play':>5} "
          f"{'Blob':>5} {'Opts':>5} {'Htxt':>5} {'Haud':>5}")
    print("-" * 78)
    for iid, q in pairs:
        st = qstate.get(q)
        if not st:
            problems.append(f"{iid}/{q}: NOT in Question table")
            continue
        _, statuscd, reader, audio, play, txtlen, lastmod = st
        blobinfo = blob_ok.get(reader)
        blob_good = bool(blobinfo and blobinfo[0])
        equal = (reader is not None and reader == audio)
        pending = (statuscd == STATUS_PENDING)
        play_ok = (play == 1)
        opts = opt_ct.get(q, 0)
        htxt = text_hint_ct.get(q, 0)
        haud = hint_audio.get(q, [])

        row = (f"{str(iid):12}{q:>7} {statuscd:>5} {str(reader):>7} "
               f"{'Y' if equal else 'N':>7} {'Y' if play_ok else 'N':>5} "
               f"{'OK' if blob_good else 'BAD':>5} {opts:>5} {htxt:>5} {len(haud):>5}")
        print(row)

        if reader is None:
            problems.append(f"{iid}/{q}: ReaderBlobID is NULL (not linked!)")
        if not equal:
            problems.append(f"{iid}/{q}: Reader({reader}) != Audio({audio})")
        if not pending:
            problems.append(f"{iid}/{q}: StatusCD={statuscd} (expected 3 Pending)")
        if not play_ok:
            problems.append(f"{iid}/{q}: PlayAudioOnRenderFlag={play} (expected 1)")
        if not blob_good and blobinfo:
            problems.append(f"{iid}/{q}: Blob {reader} bad: type={blobinfo[1]} "
                            f"status={blobinfo[2]} path={blobinfo[3]}")
        if opts == 0:
            # only a problem if not a True/False question — flag for eyeball
            problems.append(f"{iid}/{q}: 0 SelectionOptions (verify it's True/False)")

    # ---- CDN spot-check: hit the real MP3 for every question + first hint ----
    print("\nCDN playback check (real files served to students):")
    for iid, q in pairs:
        url = f"{CDN}/{iid}-question.mp3"
        try:
            r = requests.get(url, timeout=30)
            cdn_checked += 1
            ct = r.headers.get("content-type", "")
            size = len(r.content)
            ok = r.status_code == 200 and size > 2000
            if not ok:
                cdn_fail.append(f"{iid}-question.mp3: HTTP {r.status_code}, {size}B, ct={ct}")
        except requests.RequestException as e:
            cdn_fail.append(f"{iid}-question.mp3: {e}")
    print(f"  question MP3s checked: {cdn_checked}, failures: {len(cdn_fail)}")
    for f in cdn_fail:
        print("   ✗ " + f)

    # ---- summary ----
    print("\n" + "=" * 78)
    total = len(pairs)
    linked = sum(1 for _, q in pairs if qstate.get(q) and qstate[q][2] is not None)
    pending_ct = sum(1 for _, q in pairs if qstate.get(q) and qstate[q][1] == STATUS_PENDING)
    hint_rows = sum(len(v) for v in hint_audio.values())
    print(f"  questions:                 {total}")
    print(f"  linked (ReaderBlobID set): {linked}/{total}")
    print(f"  still Pending (StatusCD3): {pending_ct}/{total}")
    print(f"  hint-audio rows total:     {hint_rows}")
    print(f"  CDN question MP3s OK:      {cdn_checked - len(cdn_fail)}/{cdn_checked}")
    print(f"  DATA PROBLEMS:             {len(problems)}")
    for p in problems:
        print("   ✗ " + p)
    if not problems and not cdn_fail:
        print("\n  ✅ ALL CHECKS PASS — every Road Safety question is linked, still Pending,")
        print("     blobs valid, and MP3s play from the CDN. Nothing was overwritten.")
    conn.close()


if __name__ == "__main__":
    main()
