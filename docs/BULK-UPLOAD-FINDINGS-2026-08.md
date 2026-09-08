# Bulk Question Upload — Findings & Playbook (Aug/Sep 2026)

Everything learned loading the first "fully-finished" batch (the 244) into **DevTest**,
starting with the 42-question **Road Safety** test batch. Read this before the next
bulk upload — it captures the non-obvious gotchas that cost time.

Environment: DevTest schema (`wwa_dev` DB), UserID=8, container `devtestblobs`,
CDN `https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs`.

> **Companion doc:** `docs/QUESTION-STUDIO-FULL-SPEC.md` is the authoritative field-by-field
> map of a question (UI + DB + student runtime), built from Victor's source 7 Sep 2026.
> Read it for: must-set-or-insert-fails fields (Title, PlayAudioOnRenderFlag, IsNumericOnlyAnswer —
> bits with NO default; Question timestamps default NULL), per-type scoring keys (CorrectAnswerText
> encoding), which templates render the question image, Written needing WrittenAnswerOption rows,
> Sort/Link needing OptionGroups, and the ColorSchemeID gap in our importer.

---

## 0. The golden rules (Victor's, in writing)

From Victor's email 24 Aug 2026 ("Re: Question Upload"):
1. **Load order:** Blob DB records → blob files → Questions, OptionGroups, SelectionOptions → QuestionHints, HintReplacements.
2. **Idempotent:** always look up existing records by **business key** first; UPDATE if present, else INSERT. Safe to re-run, no duplicates.
3. **Use `hint-graphic-audio`** as the target for hint voice-overs (confirmed by him).
4. **Load as Pending** (StatusCD=3) so they can be "checked one-by-one as they are approved."
5. **Keep a note of the run time** so the DB can be restored if needed. → logged in `data/questions/backups/ingest_run_log.txt`.

CLAUDE.md safety rules still override everything: **never DELETE, never modify Victor's
existing records, only INSERT into DanTest/DevTest, Victor is the boss.**

---

## 1. Voice-over ingest — how it actually lands in the DB

Script: `scripts/bulk_import/ingest_voiceovers.py` (dry-run default; `--apply`, `--include-hints`, `--ids-file`).

**Question voice-over:**
- Blob row: `BlobTypeCD=111` (audio), `Path='audio'`, `FileTypeExtn='mp3'`, `StatusCD=4`, `CreatedUserID/LastModUserID=8`.
- Link: set **BOTH** `Question.ReaderBlobID` AND `Question.AudioBlobID` to the new BlobID, and `PlayAudioOnRenderFlag=1`.
  - `ReaderBlobID` = speaker on the **question text** (click to play).
  - `AudioBlobID` = speaker on the **question image** (hover to play).
- Idempotent: blob reused by **Filename**; question link updated-if-present.

**File naming (IMPORTANT — leading zeros):**
- Blob **files** and the `Blob.Filename` are stored **WITHOUT leading zeros**: `140601-question.mp3`, `140601-hint1.mp3`.
- The **ItemID** in the sheet/SpreadsheetXRef HAS leading zeros: `00140601`.
- ⚠️ **Gotcha that wasted time:** a verify script that builds the CDN URL from the *padded* ItemID (`00140601-question.mp3`) gets **404** for every file, looking like a total failure. It's not — the files are fine under the un-padded name. **Always build the CDN URL from `Blob.Path` + `Blob.Filename` + `Blob.FileTypeExtn` (what the app does), never from the raw ItemID.**

**Content-type note (minor, tell Victor):** MP3s serve as `application/octet-stream`, not `audio/mpeg`. Browsers still play them. Images serve correctly as `image/svg+xml`.

---

## 2. Hints — the TWO upload targets (this is the big one)

Victor's hint system = a hint **Level** (1/2/3) made of **"Block Replacements"**. Each
replacement **targets a TemplateElement** and swaps it in when that hint fires. The
QuestionStudio UI shows a **"Target Element" dropdown** — this is the choice between
"replace the text" vs "just add a voice-over."

The relevant `TemplateElement`s (exist per-template; same across all 6 templates):

| HTMLElementID | ElementTypeCD | Victor's Title (verbatim) | Effect when a hint targets it |
|---|---|---|---|
| `question-text-content` | 118 (text) | "The main question text area" | **Replaces the question text** with hint wording. UI shows a **Hint Text (HTML)** box. |
| `hint-graphic` | 120 (visual) | "A small graphic shown as a hint beside the question text" | Shows a hint **picture**. UI shows a **blob picker**. |
| **`hint-graphic-audio`** | **119 (audio)** | **"An audio clip played from the hint graphic speaker"** | **Plays a hint voice-over; text untouched.** Companion to `hint-graphic` — "the graphic wears the speaker symbol when this is populated." UI shows a **blob picker**. |
| `question-audio` | 119 (audio) | "An audio clip played alongside the question" | Swaps the question hover-audio for a hint clip. |
| `question-reader` | 119 (audio) | "A human voice reading the question text aloud" | Swaps the read-aloud voice for a hint reader. |

**The two options Dan spotted in the UI:**
- **"Replace the question text with the hint"** → target = `question-text-content` (a TEXT hint, `HintHTML` populated, `BlobID` NULL).
- **"Just the hint voice-over, don't change the text"** → target = **`hint-graphic-audio`** ("an audio clip played from the hint graphic speaker"), `BlobID` populated, `HintHTML=''`.

**How our ingest handles it (correct, per Victor):**
- The hint **text** already lives on `question-text-content` (loaded earlier). **We never touch it.**
- Hint **audio** = a **NEW, SEPARATE** HintReplacement row per level with
  `HTMLElementID='hint-graphic-audio'`, `HintHTML=''`, `BlobID=<audio blob>`, `TemplateName`
  copied from that question's existing text-hint row.
- Business key for upsert: `QuestionID + HintLevelNum + TemplateName + HTMLElementID='hint-graphic-audio'`.
- Result verified in DB: e.g. QID 4966 L1 has **two** rows — the text hint on
  `question-text-content` (intact) + our audio on `hint-graphic-audio`. Both coexist. ✅

**UI rule to know:** for a given replacement, **Text and Media/Blob are mutually exclusive**
(choosing one clears the other). Audio/Reader are always-optional add-ons. That's why hint
audio is its **own row on an audio element**, not a BlobID bolted onto the text-hint row.
(An early version of our script wrongly tried to set BlobID on the text row — fixed before it ran.)

---

## 3. Template rendering gotcha — Select All hides the question image

**Symptom:** a Road Safety question (00140602, "ride a bike or scooter…") has an image in
the DB (Blob 595, serves fine), but the picture **does not appear** in the portal.

**Cause (NOT an upload bug — confirmed by reading Victor's Razor templates):**
- `Template1.razor` (**Select One**) renders the question image: `var questionImageData = ... ?? ImageData; @if(hasQuestionImage){ <img ...> }`.
- `Template2.razor` (**Select All**) has **no question-image render at all** — it's built as an
  *image-grid of the answer options* ("Select All - Image grid with multiple selection").
  It shows question text + hints + **option images**, and **ignores `Question.ImageBlobID`.**

So a **Select All** question whose picture is on the *question* (not the options) will not
display that picture. Data is correct; the template just has no slot for it.

**Scope in the 42:** 30 Select One (image shows), 7 True/False (no image), **5 Select All
with a question image that won't show** — QIDs 4967, 4974, 4986, 4996, 5003
(ItemIDs 00140602, 00140609, 00140621, 00140631, 00140638).

**Resolution is a Julie/Victor call** (do NOT silently change type or move images):
- (a) Victor adds question-image rendering to Template2, or
- (b) accept the picture is illustrative and won't show in Select All, or
- (c) Julie reworks those 5 so the images ARE the options (true "tap all the safe pictures").

**➡️ Pre-flight check for next batch:** flag any **Select All** question that has
`Question.ImageBlobID` set but **zero** option images — its picture will be invisible.

---

## 3b. ⚠️ "DONE" ≠ what the app's approved flag says — hint-count mismatch (CRITICAL)

**The app marks a question "approved/ready" based on question-VO + image. It does NOT
require every hint level to be voiced.** So "244 complete" overstated readiness under the
real definition: *if a question has N hints, all N should have voice-overs.*

**The DB and the app disagree on how many hints each question has:**
- DB carries hint *text* from the May import — usually **3 levels** per question (`question-text-content`).
- The app has only the hints Zoe actually **voiced + approved** — often **1** (sometimes 2).
- Of the 240: **106 match**, **134 mismatch** (111 are DB-3/app-1, 21 are DB-3/app-2).
- The app's own `/api/pipeline-stats` says **240/240 done** — but that's "all hints THE APP KNOWS
  ABOUT are voiced," not "all 3 DB hint texts are voiced."

**Unresolved decision (Zoe/Julie only):** is the target **1 curated hint** per question
(app = source of truth → they're done, DB has 2 stale text-hints to drop) OR **3 progressive
hints** (DB = truth → Zoe still needs to record hints 2 & 3)? Memory `project_data_alignment`
leans "app/sheet = source of truth, DB needs sync" → probably the former, but CONFIRM before
uploading the rest or activating anything.

**Verify true completeness with the APP, not just the DB:** `GET {app}/api/pipeline-stats`
returns per-question + per-hint `has_audio`/`status`. A question is truly done when
`vo_status=approved & has_vo_audio` AND every hint it lists is `status=approved & has_audio`.
But reconcile the hint COUNT against the DB (above) — that's the real gap.

**Also:** only the 42 Road Safety were ever ingested to the DB. The other ~198 have approved
audio IN THE APP but were never loaded — so a DB-only completeness check shows them "missing"
when the audio actually exists in the app awaiting ingest.

## 4. Status / findability (the 42)

- Victor asked for **Pending**. We initially loaded Pending, then (Dan's call, 31 Aug) flipped
  the 42 to **Active (StatusCD=4)** so Julie can find/review them live — DevTest is ~all-Pending
  (7,600+ Pending vs a handful Active), so Active makes the finished batch stand out.
- **Reversible:** `scripts/bulk_import/set_active_roadsafety.py --revert` restores each to its
  snapshotted prior status (snapshot: `data/questions/backups/roadsafety_status_revert.json`).
- ⚠️ This is **against Victor's stated "load as Pending" preference** — give him a heads-up if
  scaling this to the full 244. For a batch this size, prefer: load Pending + hand Julie a
  topic-grouped CSV, OR ask Victor before activating.

---

## 5. Verification recipe (always run after an --apply)

`scripts/bulk_import/verify_roadsafety.py` re-queries the DB live (doesn't trust the run log):
per question checks ReaderBlobID=AudioBlobID, PlayAudioOnRenderFlag, StatusCD, Blob validity
(type111/StatusCD4/path 'audio'), hint-audio rows, options intact, and hits the **real CDN URL**.

**Build the CDN URL from `Blob.Path`/`Filename`/`FileTypeExtn`, not the ItemID** (see §1).
Check images the same way (they serve as `image/svg+xml`).

---

## 7. ⚠️ BLOB FILENAME COLLISION BUG — voice-over linked to the IMAGE (found + fixed 1 Sep 2026)

**The exact mistake:** Georgia's newer question images are stored with `Filename = "{ItemID}-question"`
(extension `.svg`, `BlobTypeCD=110`). The audio voice-over uses the **same** `Filename` base
`"{ItemID}-question"` (extension `.mp3`, `BlobTypeCD=111`). The ingest's `blob_exists()` matched on
**`Filename` only**, so for any such question it found the **image** blob, concluded "audio already
exists," and set `Question.ReaderBlobID`/`AudioBlobID` to the **picture**. Result: the speaker button
would try to play an SVG — a broken voice-over, with **no error** (silent corruption).

- **Impact when found:** exactly 1 question live-broken (10014001). But **1,120 image blobs are named
  `*-question`**, so this would have silently broken the VO on *any* of those as batches scaled.
- **Why it stayed hidden:** no exception is thrown — the link just points at the wrong blob type. Only a
  manual "does the speaker actually play the MP3?" check surfaced it.
- **THE FIX (in `ingest_voiceovers.py`):** `blob_exists()` now filters `AND BlobTypeCD = 111`, so it only
  ever reuses an **audio** blob and can never grab an image blob again. Verified: re-ingest of 10014001
  linked Reader→a real `.mp3` (type 111), 0 broken VOs remain in DevTest.
- **MANDATORY post-ingest guard (add to every verify):**
  `SELECT COUNT(*) FROM {schema}.Question q JOIN {schema}.Blob b ON b.BlobID=q.ReaderBlobID
   WHERE q.ReaderBlobID IS NOT NULL AND b.BlobTypeCD<>111` — must be **0**.
- **Lesson:** small test batches + per-question manual audio/image checks caught a bug that would have
  corrupted ~1,120 voice-overs. Keep testing small and eyeballing.

## 8. ⚠️ IMAGE COMPLETENESS — every question needs an image; IGNORE the `ImageRequired` column (corrected 1 Sep 2026)

- **The mistake:** the completeness filter treated spreadsheet `ImageRequired = N` as "no image needed →
  complete without an image," and activated 18 image-less questions. **Wrong.**
- **The rule (from Dan/Julie):** EVERY question must have a question image. `ImageRequired` only means
  "is the image needed to *answer* the question" — it does NOT mean "skip the image." **Ignore that column
  for completeness gating.**
- **Image source of truth = the DATABASE (`Question.ImageBlobID`) / CDN, NOT the review app.** The app's
  `question_image.has_image`/`status` is UNRELIABLE — it reported `False` for questions that demonstrably
  have images in the DB and serve HTTP 200 from the CDN. Always check images via the DB/CDN.
- **Select All also needs OPTION images** (its template renders an option-image grid, see §3). As of 1 Sep,
  **0** audio-complete Select All questions have all option images → Select All is BLOCKED on Georgia's
  option images; don't load any yet.
- **TRUE completeness = audio-complete (app: VO + every spreadsheet hint voiced & approved) AND
  `Question.ImageBlobID` set in DB (+ option images if Select All).** Under this correct rule: **202**
  truly complete (not 153/244/362 — those mis-counted images). Correction applied: the 18 image-less were
  reverted to Pending; only the 2 with real images stayed Active.

## 9. REQUIRED LOAD SEQUENCE (per batch) + the running mistake log

**Sequence — do every step, in order, per batch:**
1. Pick truly-complete only (§8): app-audio-complete ∩ has-image-in-DB (+option images if Select All).
2. `ingest_voiceovers.py --ids-file <itemids> --include-hints --apply` (idempotent UPDATE; never re-inserts).
3. `set_hints_audio_only.py --qids-file <qids> --apply` — Zoe's rule: hints are audio-only, question text
   NOT replaced. Only blanks levels that HAVE audio (never leaves an empty hint). **Never skip this.**
4. **Verify (all must pass before activating):** Reader=Audio & Reader is type 111 (§7 guard), image blob set
   & serves 200, every hint voiced & serves, 0 text-replace hint rows, still no dup blobs/hint rows.
5. `set_active.py --qids-file <qids> --apply` (optional; Dan's call — against Victor's "load as Pending";
   reversible via `--revert`, per-batch snapshot).

**Mistakes made this cycle (all caught + corrected — kept here so we don't repeat them):**
- Called batches "100%/complete" trusting the app's approved flag — it doesn't require all hints voiced,
  nor images. Real completeness needs the §8 rule.
- Activated 18 questions missing images (ImageRequired misread) → reverted to Pending.
- Forgot the audio-only hint step on the first 20 → applied it after Dan flagged it. Now step 3 of the sequence.
- Blob-collision bug linked a VO to an image (§7) → fixed script + repaired the one question.
- Review-app outage: pointed the Railway healthcheck at an auth-gated path after `ACCESS_PASSWORD` was
  enabled → 502s, deploys "FAILED". Fixed with `/healthz` (trivial, auth-exempt). NO data lost. NEVER
  `railway up` (274MB, and it overrides git deploy) — deploy is git-push only.

## 10. FULL AUDIT (1 Sep 2026) — DB is clean; tooling hardened

A 3-agent read-only audit (DB integrity + both web apps + scripts/sequence) ran after the
collision bug. **Headline: the DATABASE is healthy** — the collision was a single isolated
incident (QID 7544, fixed). Across 7,643 questions / 2,251 blobs:
- **0** wrong-type links (Reader/Audio→non-audio, Image→non-image, options too)
- **0** dangling FKs, **0** duplicate questions/blobs/hint rows
- All CDN spot-checks pass. Only 22 questions Active; 7,620 correctly Pending.

**Structural risk (not a live bug):** 76 blobs share the `{ItemID}-question` Filename base across
image(110)+audio(111). This is the collision *surface* — mitigated by making every blob lookup
BlobTypeCD-aware (done, below).

**Fixes applied (all tooling, no data touched):**
- **NEW `verify_complete.py`** — bulletproof read-only verifier, supersedes verify_roadsafety.py.
  Checks: VO linked & both audio(111) [collision guard], question image present/type-110/serves,
  EVERY hint level voiced(111) & serves, audio-only (0 text-replace rows), Select All option images,
  status, dup rows — and a **fleet-wide guard** (`--fleet-guard`) for wrong-type links/dangling FKs
  across the whole schema. **Builds all CDN URLs from Blob.Path/Filename/FileTypeExtn, never the ItemID.**
  Usage: `verify_complete.py --qids-file <qids> [--expect-active]` or `--fleet-guard`.
- **`import_from_airtable.blob_exists_in_db`** now filters `BlobTypeCD=110` (was Filename-only — the
  mirror of the collision bug on the image side).
- **`ingest_voiceovers`** now normalizes every ids-file ItemID to un-padded form (matches the app +
  CDN + DB naming). A padded `00110039` no longer 404s the download / mis-names the blob.
- **`set_active.py`** (per-batch revert) supersedes `set_active_roadsafety.py` (single-file revert that
  could clobber on re-run). Use `set_active.py` going forward.
- **verify_roadsafety.py is DEPRECATED** — it built CDN URLs from the raw ItemID (false 404s for padded
  IDs) and didn't check images/hints/text-blank/fleet-collision. Use `verify_complete.py`.

**Known-but-fine (from audit, no action):** app's image-state tracks its own local PNGs (not the DB) —
never trust the app for "has image", check the DB/CDN. 13 Active demo/interactive questions (no ItemID)
have hint-audio on non-standard elements — Victor's test questions, flag if asked. BlobTypeCD 122 =
EdContent HTML help lessons (legend gap only). Audio serves as application/octet-stream (browsers fine).

## 6. Still-open items for the full 244

- **184** question voice-overs still to link (56 already done incl. the 42), **~459** approved hint VOs to attach.
- **4 brand-new** questions (140209, 140210, 140211, 20023007) need full question INSERT via `import_questions.py` first.
- **~42 images** still to link from Airtable (`import_from_airtable.py`).
- **20 DB text typo fixes** identified (sheet-fixed typos not yet pushed to DB); 2 sheet typos (`fasle`) already fixed.
- Re-run the **Select All + question-image** pre-flight check (§3) across the full 244.
- Environment note: the local `venv/` broke after a Python 3.14 upgrade (empty `bin/`). Rebuild:
  `python3 -m venv venv && venv/bin/python -m pip install pyodbc azure-identity azure-storage-blob requests pillow`.
  ODBC "Driver 18 for SQL Server" is installed. Auth = `AzureCliCredential` (run `az login` first).

## 7. Session 7 Sep 2026 — new tools, findings & first real complete batch

**New scripts (all read-only or reversible):**
- **`completeness_report.py`** — THE single source of truth. Reconciles spreadsheet + review app + DB
  into ONE verdict per question: READY / NEEDS_INGEST / NEEDS_IMAGE_SYNC / DB_EXTRA_HINTS / NEEDS_IMAGE /
  NEEDS_VO / NOT_IN_DB. Run this instead of ad-hoc counts. Full detail: `reference_completeness_report` memory.
- **`remove_stale_hints.py`** — removes hint levels that are in the DB but NOT in the spreadsheet
  (May-import leftovers). Spreadsheet = truth; never touches a real/voiced hint; blanks text + sets
  QuestionHint.StatusCD=6; per-batch revert snapshot; `--revert`.
- **`docs/QUESTION-STUDIO-FULL-SPEC.md`** — authoritative field-by-field map of a question (UI+DB+runtime).

**Key findings:**
- **"READY" requires the image IN THE DB, not just Airtable.** Airtable-only images don't render in the
  portal → verdict NEEDS_IMAGE_SYNC (run `import_from_airtable`). `verify_complete` blocks activation if
  ImageBlobID is NULL. (This corrected an over-loose earlier check that would've activated image-less Qs.)
- **verify_complete FIX:** it now only counts hint levels whose QuestionHint.StatusCD=4 (Active) — matching
  what GetNextQuestion serves. Deactivated (stale) levels are ignored. Before the fix it false-flagged
  removed stale hints as "NO voice-over".
- **The three sources drift.** App/Airtable are far ahead of the DB. 7 Sep whole-schema:
  READY 4 · NEEDS_INGEST ~264-397 · NEEDS_IMAGE_SYNC 4383 · DB_EXTRA_HINTS 41 · NEEDS_IMAGE 2086 ·
  NEEDS_VO 807 · NOT_IN_DB 318. The real backlog is CONTENT (Zoe VO + Georgia images); the movable-now
  part is OUR ingest/sync.

**⚠️ IMAGE BLOAT — raster-in-SVG (systemic, ~85% of images):**
- Georgia's images (via Canva→Airtable) are saved as **SVGs with a full-res PNG embedded in base64** —
  not true vectors. Median ~1.5 MB, up to 4.5 MB. Of 2,467 loaded: **2,107 fake-SVG (~4.2 GB)**, 154 real
  vector SVG (~19 KB ea, leave alone), 134 Lottie json (fine).
- **Fix: convert to WebP** (unwrap PNG → WebP). Proven: 3.1 MB → 144 KB (~95%), no visible quality loss.
  Do it at sync time + a retro pass over the 2,107. **The SVG already contains full-quality pixels — no
  originals needed**, nobody's work is wasted. Skip real vector SVGs (they have no embedded raster).
- Portal renders images via plain `<img>` (only `.json`=Lottie is special-cased) → WebP will display.
  BLOCKER: emailed Victor 7 Sep to confirm (1) CDN serves `.webp` with right content-type, (2) no upload
  validation rejects WebP. NOT built yet — pending his reply. Does NOT block uploading (swap later, no rework).
- Does NOT truly scale (it's a fixed 1536px raster in an SVG costume); WebP keeps it exactly as-is, lighter.

**⚠️ ElevenLabs OUT OF CREDITS (7 Sep):** VO generator throws `quota_exceeded 401` — workspace at
0/238,890 credits. Georgia/Zoe blocked from generating NEW voiceovers until topped up/upgraded at
https://elevenlabs.io/app/subscription (or monthly reset). Does NOT block ingesting already-generated audio.

**✅ FIRST REAL COMPLETE BATCH LIVE (7 Sep):** 31 Personal Hygiene questions Active in DevTest —
image + question VO + hint VO (audio-only), all verified 0 problems. 4 of 35 held (Select All missing
option images → Georgia). Also synced Creative Arts images (575). Full flow that worked:
`completeness_report` → `ingest_voiceovers --include-hints --apply` → `set_hints_audio_only --apply` →
`remove_stale_hints --apply` → `verify_complete` → split clean vs flagged → `set_active --apply`.
Per-batch revert snapshots in `data/questions/backups/`.
