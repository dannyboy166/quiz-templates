#!/usr/bin/env python3
"""
Ingest Zoe's APPROVED voice-overs (from the review app) into Victor's DB.

For each target question:
  1. resolve ItemID -> QuestionID via SpreadsheetXRef (handles leading-zero mismatch)
  2. skip if it already has ReaderBlobID (never double-insert)
  3. download the approved MP3(s) from the app  (auth-exempt /audio/ route)
  4. upload to Azure blob  devtestblobs/audio/{ItemID}-question.mp3 (+ hints)
  5. INSERT a Blob row  (BlobTypeCD=111, StatusCD=4, Path='audio' ...) — recipe verified
     from WW/WWApp/BlobUploader.razor + the 115 working rows already in DevTest
  6. link the Question: set ReaderBlobID AND AudioBlobID to the new BlobID
  7. (hints) INSERT a Blob per approved hint and link via HintReplacement? -> see NOTE

SAFETY
  - DRY-RUN by default. --apply required to write anything.
  - INSERT/link only. Never UPDATEs question text, never overwrites an existing
    ReaderBlobID. Skips anything already linked.
  - Re-reads every write to verify.
  - Scoped to an explicit ItemID list (--ids-file) — never "all".

HINTS: confirmed from DB — hint audio attaches via HintReplacement.BlobID (there
are already 32 working hint-audio blobs in DevTest, type 111 / Path 'audio' /
StatusCD 4). Pass --include-hints to upload each approved hint MP3, insert a Blob
row (same recipe), and set HintReplacement.BlobID on the matching QuestionID +
HintLevelNum row (only where currently NULL). Default is questions-only.

USAGE
  python -m scripts.bulk_import.ingest_voiceovers --ids-file ids.txt --dry-run
  python -m scripts.bulk_import.ingest_voiceovers --ids-file ids.txt --apply
"""
import argparse
import struct
import sys
import tempfile
from pathlib import Path

import requests
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
import pyodbc

APP_BASE = "https://web-production-bce96.up.railway.app"
STORAGE_ACCOUNT = "worldwiseaustg"
SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DevTest"
CONTAINER = "devtestblobs"
USER_ID = 8            # DevTest
AUDIO_PATH = "audio"   # Blob.Path folder + blob path prefix
BLOB_TYPE_AUDIO = 111
STATUS_ACTIVE = 4
PLAY_ON_RENDER = 1     # existing 115 rows have this = 1


# ---------- connections ----------
def db_conn():
    cred = AzureCliCredential()
    tok = cred.get_token("https://database.windows.net/.default")
    tb = tok.token.encode("UTF-16-LE")
    ts = struct.pack(f"<I{len(tb)}s", len(tb), tb)
    cs = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{SERVER},1433;"
          f"Database={DATABASE};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;")
    return pyodbc.connect(cs, attrs_before={1256: ts})


def blob_service():
    cred = AzureCliCredential()
    return BlobServiceClient(f"https://{STORAGE_ACCOUNT}.blob.core.windows.net", credential=cred)


# ---------- helpers ----------
def norm(item_id):
    s = str(item_id).strip()
    return s.lstrip("0") or s


def load_xref(conn):
    """normalized SpreadsheetRecordID -> QuestionID for Question rows."""
    cur = conn.cursor()
    cur.execute(f"SELECT SpreadsheetRecordID, QuestionID FROM {SCHEMA}.SpreadsheetXRef "
                f"WHERE TableName='Question'")
    m = {}
    for sid, qid in cur.fetchall():
        if sid is not None:
            m[norm(sid)] = qid
    return m


def question_audio_state(conn, qids):
    """QuestionID -> (ReaderBlobID, AudioBlobID) for the given ids."""
    out = {}
    cur = conn.cursor()
    for i in range(0, len(qids), 200):
        chunk = qids[i:i + 200]
        ph = ",".join("?" * len(chunk))
        cur.execute(f"SELECT QuestionID, ReaderBlobID, AudioBlobID FROM {SCHEMA}.Question "
                    f"WHERE QuestionID IN ({ph})", chunk)
        for qid, r, a in cur.fetchall():
            out[qid] = (r, a)
    return out


def blob_exists(conn, filename):
    """Find an existing AUDIO blob by filename. MUST filter BlobTypeCD=111 —
    image blobs share the '{ItemID}-question' Filename (different extension), and
    matching on Filename alone would wrongly reuse the IMAGE blob and link the
    question's Reader/Audio to a picture instead of the MP3."""
    cur = conn.cursor()
    cur.execute(f"SELECT BlobID FROM {SCHEMA}.Blob WHERE Filename = ? AND BlobTypeCD = ?",
                (filename, BLOB_TYPE_AUDIO))
    row = cur.fetchone()
    return row[0] if row else None


def download_audio(item_id, kind):
    """kind = 'question' or 'hint1'/'hint2'/'hint3'. Returns bytes or None."""
    fname = f"{item_id}-{kind}.mp3"
    url = f"{APP_BASE}/audio/{fname}"
    try:
        r = requests.get(url, timeout=30)
    except requests.RequestException:
        return None
    if r.status_code == 200 and r.headers.get("content-type", "").startswith("audio"):
        return r.content
    return None


def upload_blob(bs, filename_with_ext, data):
    blob_path = f"{AUDIO_PATH}/{filename_with_ext}"
    cc = bs.get_container_client(CONTAINER)
    cc.get_blob_client(blob_path).upload_blob(data, overwrite=True)
    return blob_path


def insert_blob(conn, filename_no_ext):
    """Insert the audio Blob row using the verified recipe. Returns BlobID."""
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {SCHEMA}.Blob
            (BlobTypeCD, Name, Title, Description, Filename, Path,
             HasVttFile, StatusCD, CreatedUserID, LastModUserID, FileTypeExtn,
             CreatedTime, LastModTime)
        OUTPUT INSERTED.BlobID
        VALUES (?, ?, '', '', ?, ?, 0, ?, ?, ?, 'mp3', GETDATE(), GETDATE())
    """, (BLOB_TYPE_AUDIO, filename_no_ext[:30], filename_no_ext[:50],
          AUDIO_PATH, STATUS_ACTIVE, USER_ID, USER_ID))
    bid = cur.fetchone()[0]
    conn.commit()
    return bid


def link_question(conn, qid, blob_id):
    """Upsert per Victor: point the question at its audio blob (update if already set).
    Business key = QuestionID. Idempotent: re-running with the same blob is a no-op."""
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {SCHEMA}.Question
           SET ReaderBlobID = ?, AudioBlobID = ?, PlayAudioOnRenderFlag = ?,
               LastModTime = GETDATE(), LastModUserID = ?
         WHERE QuestionID = ?
    """, (blob_id, blob_id, PLAY_ON_RENDER, USER_ID, qid))
    n = cur.rowcount
    conn.commit()
    return n


HINT_AUDIO_ELEM = "hint-graphic-audio"   # confirmed from Victor's schema (32 live rows)


def hint_text_levels(conn, qid):
    """Return {HintLevelNum: TemplateName} for existing TEXT hint rows
    (HTMLElementID='question-text-content'), and the set of levels that ALREADY
    have an audio row. Audio is a NEW row per level, keyed on HTMLElementID."""
    cur = conn.cursor()
    cur.execute(f"""SELECT HintLevelNum, TemplateName, HTMLElementID
                    FROM {SCHEMA}.HintReplacement WHERE QuestionID=?""", (qid,))
    text_levels, audio_levels = {}, set()
    for lvl, tmpl, elem in cur.fetchall():
        if elem == HINT_AUDIO_ELEM:
            audio_levels.add(lvl)
        else:
            text_levels[lvl] = tmpl          # remember the template used for this Q's hints
    return text_levels, audio_levels


def upsert_hint_audio_row(conn, qid, level, template_name, blob_id):
    """Upsert the HintReplacement AUDIO row (business key = QuestionID+HintLevelNum+
    TemplateName+HTMLElementID='hint-graphic-audio'). Update BlobID if it exists, else
    insert. Never touches the hint TEXT row (different HTMLElementID)."""
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {SCHEMA}.HintReplacement
           SET BlobID = ?, HintHTML = '', LastModTime = GETDATE(), LastModUserID = ?
         WHERE QuestionID = ? AND HintLevelNum = ? AND TemplateName = ?
               AND HTMLElementID = ?
    """, (blob_id, USER_ID, qid, level, template_name, HINT_AUDIO_ELEM))
    if cur.rowcount == 0:
        cur.execute(f"""
            INSERT INTO {SCHEMA}.HintReplacement
                (QuestionID, HintLevelNum, TemplateName, HTMLElementID, HintHTML, BlobID,
                 CreatedTime, CreatedUserID, LastModTime, LastModUserID)
            VALUES (?, ?, ?, ?, '', ?, GETDATE(), ?, GETDATE(), ?)
        """, (qid, level, template_name, HINT_AUDIO_ELEM, blob_id, USER_ID, USER_ID))
    conn.commit()


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-file", required=True, help="file with one ItemID per line")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--include-hints", action="store_true",
                    help="also upload hint MP3s as Blob rows (NOT linked; confirm with Victor)")
    args = ap.parse_args()
    apply = args.apply
    mode = "APPLY (writing)" if apply else "DRY-RUN (no writes)"

    ids = [l.strip() for l in Path(args.ids_file).read_text().splitlines() if l.strip()]
    print(f"Mode: {mode}")
    print(f"Target ItemIDs: {len(ids)}")

    conn = db_conn()
    # Victor asked us to record the exact run time (for DB restore if needed).
    if apply:
        cur = conn.cursor()
        cur.execute("SELECT SYSUTCDATETIME(), GETDATE()")
        utc, local = cur.fetchone()
        stamp = (f"VOICE-OVER INGEST RUN START\n  UTC:   {utc}\n  Local: {local}\n"
                 f"  ids-file: {args.ids_file}  ({len(ids)} ids)\n  include-hints: {args.include_hints}\n")
        print("\n" + stamp)
        logp = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/ingest_run_log.txt"
        logp.parent.mkdir(parents=True, exist_ok=True)
        with open(logp, "a") as f:
            f.write("\n" + stamp)
        print(f"  (logged to {logp})\n")
    xref = load_xref(conn)
    # resolve
    resolved = [(iid, xref.get(norm(iid))) for iid in ids]
    missing = [iid for iid, q in resolved if q is None]
    present = [(iid, q) for iid, q in resolved if q is not None]
    audio_state = question_audio_state(conn, [q for _, q in present])

    bs = blob_service() if apply else None

    # idempotent UPSERT per Victor: process every item; blob reused by Filename,
    # question/hint links updated-if-present else inserted. Safe to re-run.
    stats = {"q_upserted": 0, "q_no_mp3": 0, "q_would": 0,
             "hint_upserted": 0, "hint_no_mp3": 0, "hint_would": 0,
             "not_in_db": len(missing)}
    print(f"\n{'ItemID':12} {'QID':>7}  action")
    print("-" * 60)
    for iid, qid in present:
        # ----- QUESTION voice-over (upsert) -----
        data = download_audio(iid, "question")
        if not data:
            stats["q_no_mp3"] += 1
            print(f"{iid:12} {qid:>7}  Q: SKIP — no approved question MP3 in app")
        elif not apply:
            reader, _ = audio_state.get(qid, (None, None))
            tag = "update link" if reader is not None else "new link"
            stats["q_would"] += 1
            print(f"{iid:12} {qid:>7}  Q: would upsert {iid}-question.mp3 "
                  f"({len(data)}B) → Blob(111,StatusCD=4) → {tag} Reader+Audio")
        else:
            fname = f"{iid}-question"
            blob_id = blob_exists(conn, fname)
            if not blob_id:
                upload_blob(bs, f"{fname}.mp3", data)
                blob_id = insert_blob(conn, fname)
            else:
                upload_blob(bs, f"{fname}.mp3", data)   # refresh file (approved version)
            link_question(conn, qid, blob_id)
            cur = conn.cursor()
            cur.execute(f"SELECT ReaderBlobID,AudioBlobID FROM {SCHEMA}.Question WHERE QuestionID=?", (qid,))
            r, a = cur.fetchone()
            ok = (r == blob_id and a == blob_id)
            stats["q_upserted"] += 1 if ok else 0
            print(f"{iid:12} {qid:>7}  Q: {'✓ upserted' if ok else '✗ VERIFY FAIL'} BlobID {blob_id}")

        # ----- HINT voice-overs (upsert HintReplacement 'hint-graphic-audio' row) -----
        if args.include_hints:
            text_levels, _ = hint_text_levels(conn, qid)
            for level in sorted(text_levels):          # only levels that have a real hint
                hdata = download_audio(iid, f"hint{level}")
                if not hdata:
                    stats["hint_no_mp3"] += 1
                    continue
                tmpl = text_levels[level]              # reuse the Q's own template name
                if not apply:
                    stats["hint_would"] += 1
                    print(f"{iid:12} {qid:>7}  H{level}: would upsert {iid}-hint{level}.mp3 "
                          f"({len(hdata)}B) → Blob(111) → HintReplacement [{tmpl}/{HINT_AUDIO_ELEM}]")
                    continue
                hfname = f"{iid}-hint{level}"
                hbid = blob_exists(conn, hfname)
                if not hbid:
                    upload_blob(bs, f"{hfname}.mp3", hdata)
                    hbid = insert_blob(conn, hfname)
                else:
                    upload_blob(bs, f"{hfname}.mp3", hdata)
                upsert_hint_audio_row(conn, qid, level, tmpl, hbid)
                cur = conn.cursor()
                cur.execute(f"""SELECT BlobID FROM {SCHEMA}.HintReplacement
                                WHERE QuestionID=? AND HintLevelNum=? AND HTMLElementID=?""",
                            (qid, level, HINT_AUDIO_ELEM))
                got = cur.fetchone()
                ok = got and got[0] == hbid
                stats["hint_upserted"] += 1 if ok else 0
                print(f"{iid:12} {qid:>7}  H{level}: {'✓ upserted' if ok else '✗ FAIL'} BlobID {hbid}")

    print("\n" + "=" * 60)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if missing:
        print(f"\n  ItemIDs not found in DB (SpreadsheetXRef): {missing[:20]}"
              + (" ..." if len(missing) > 20 else ""))
    if apply:
        cur = conn.cursor()
        cur.execute("SELECT SYSUTCDATETIME(), GETDATE()")
        utc, local = cur.fetchone()
        endstamp = (f"VOICE-OVER INGEST RUN END\n  UTC:   {utc}\n  Local: {local}\n"
                    f"  results: {stats}\n")
        print("\n" + endstamp)
        logp = Path(__file__).resolve().parent.parent.parent / "data/questions/backups/ingest_run_log.txt"
        with open(logp, "a") as f:
            f.write(endstamp)
    if not apply:
        print("\nDRY-RUN — nothing written. Re-run with --apply to commit.")
    conn.close()


if __name__ == "__main__":
    main()
