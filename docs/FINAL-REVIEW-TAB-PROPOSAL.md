# "Final Review" Tab — Design Proposal

A new tab in the QuestionReview web app that mirrors Victor's QuestionStudio, shows each
question **fully assembled and 100% complete** (exactly as it will appear in the student
portal), and lets Zoe/Georgia **generate or regenerate any missing piece inline** before it
ships to Victor's database as approved.

Status: PROPOSAL (Dan's idea, 1 Sep 2026). Not built yet.

> **UPDATE 8 Sep 2026** — two things changed since this was written:
> 1. **Canva is gone.** The image path is now OpenAI → WebP → Airtable directly (no manual Canva
>    export). The "image round-trip is the hard part" caveat in §5 is largely obsolete — image
>    delivery is now near-instant. See `docs/BULK-UPLOAD-FINDINGS` and the images.js/app.py approve flow.
> 2. **Two new requirements from Dan:** (a) **per-option voice-over** — generate a separate ElevenLabs
>    VO for each selection option (verified target column exists: `SelectionOption.ReaderBlobID`);
>    (b) a **"Generate Complete Question" / "Generate All Remaining"** button that fills every missing
>    image + VO (question, options, hints) in one click, with inline text editing.
> Verified DB/field map for the whole build: **`docs/FINAL-STAGE-DB-FIELD-MAP.md`**.
> Confirmed: DB writes stay terminal-only (deployed app has no azure/pyodbc), so "Approve" here is a
> staging/approved-state action; Dan runs the verified bulk upload from the terminal.

---

## 0. PREREQUISITE (do this FIRST) — prove a perfect upload of EACH question type

Before building the Final Review tab, we must be able to upload ONE fully-complete question of
**every question type** that our content uses, end-to-end, verified perfect — because we hit real
problems this cycle (image/answer mismatch, blob-collision bug, missing images, forgotten audio-only
hints). The Final Review tab is only worth building on top of a bulletproof upload foundation.

**Content uses only 4 types** (verified 1 Sep 2026 across all 7,903 questions):
Select One 5,836 · True/False 1,183 · Select All 560 · Written 324. **Sort & Link: 0** — not used
(only relevant if the tab must *support* them for future authoring).

**Per-type readiness to test a perfect upload (verified against app-audio ∩ DB-image):**
| Type | Complete candidates (VO+all hints+question image) | Status |
|------|------|--------|
| Select One | 156 | ✅ READY — upload one, verify perfect |
| True/False | 34 | ✅ DONE — 110039 loaded + verified |
| Select All | 12 have Q-image but **0 have all OPTION images** | ⚠️ BLOCKED — template needs option images (Georgia) |
| Written | 5 have audio, **0 have an image** | ⚠️ BLOCKED — needs a complete example (image) |

**Action list to close the prerequisite:**
1. Select One — pick one clean complete example, run the full sequence, verify with `verify_complete.py`. (Confirm 10014001's pictograph answer first, or pick another.)
2. True/False — DONE (110039); keep as the reference example.
3. Select All — get Georgia to deliver **option images** for at least one; then it needs the load to link `SelectionOption.ImageBlobID` (via `import_from_airtable`), and verify the option grid renders.
4. Written — needs one example with an image (+ confirm Written's answer/CompareText loads right). Written has no options list — verify the Written Answer Options path.
5. For EACH: capture the exact working recipe + a passing `verify_complete` run as the "golden path" per type. Log any new bug in `BULK-UPLOAD-FINDINGS-2026-08.md`.

Only after all 4 types have a proven-perfect upload do we build the tab.

## 1. The problem it solves

Today the pipeline is **fragmented across separate tools and people**, and "is this question
actually 100% done?" can only be answered by cross-referencing 3 systems — which is exactly
how we shipped incomplete/mislinked questions this cycle (missing images, unvoiced hint levels,
a voice-over linked to an image). Current state:

- **Images:** review app generates (OpenAI) → approve → Canva (Connect API) → Georgia downloads
  a new format → uploads to **Airtable** → later synced into Victor's QuestionStudio/DB.
- **Voice-overs:** review app generates (ElevenLabs) → uploaded **straight into Victor's
  QuestionStudio/DB** (via our `scripts/bulk_import/ingest_voiceovers.py`).
- **Question text / options / hints / type:** live in the **master spreadsheet**, imported to the
  DB via `scripts/bulk_import/import_questions.py`.
- The three never meet in one screen. No single place shows the finished question.

**The idea:** one "Final Review" screen that looks like QuestionStudio, assembles the whole
question from all sources, shows completeness at a glance, and provides a Generate/Regenerate
button next to **every** part (question text, each option, each hint, question image, option
images, question voice-over, each hint voice-over). Reviewers fix anything missing right there,
then click Approve → it lands in Victor's DB as a complete, verified record.

---

## 2. Current app architecture (what we're extending)

- **Flask app**, one repo (`quiz-templates`), `review_app/`, deployed to Railway
  (https://web-production-bce96.up.railway.app), auto-deploys on `git push origin main`.
- **Tabs today:** Dashboard (`/`), Questions (`/questions` — voiceovers + hints), Library
  (`/library`), Images (`/images`). Nav in `templates/base.html`.
- **KEY FACT — the app does NOT currently talk to Victor's Azure SQL DB.** It runs entirely off:
  - the **master spreadsheet** (`spreadsheet_loader.py` — question text, type, options, Hint1/2/3),
  - **local generated files** on the Railway volume (`data/voiceovers/` MP3s, `data/images_generated/` PNGs),
  - **Airtable** (`airtable_loader.py` / `airtable_push.py` — Georgia's images),
  - approval state in JSON on the volume (`state.py`, `image_state.py`).
- **DB writes happen OUT-OF-BAND** via `scripts/bulk_import/*` run from a terminal (import_questions,
  ingest_voiceovers, import_from_airtable, set_hints_audio_only, set_active, verify_complete).
- Engines already present: `voiceover_engine.py` (ElevenLabs + SSML, question & hints),
  `image_engine.py` (OpenAI gpt-image, question + answer images, edit/versions),
  `canva_uploader.py` (Canva Connect OAuth upload), `airtable_push.py` (push to Airtable).

**Design consequence:** the Final Review tab is where the app would FINALLY need to read (and
optionally write) Victor's DB — or keep DB writes out-of-band and just drive them. See §5 options.

---

## 3. What "100% complete" means (the gate this tab enforces)

From the hard-won rules (see `BULK-UPLOAD-FINDINGS-2026-08.md` §7–§9). A question is complete when:
1. Question text present; correct answer set; options present (≥2, except True/False).
2. **Question image present** (EVERY question needs one — `ImageRequired` column is IGNORED; it only
   means "needed to answer"). Image verified in the **DB/CDN**, not the app's local-PNG state.
3. **Select All also needs an image on every option** (its template renders an option-image grid).
4. Question **voice-over** present, and it links to an AUDIO blob (type 111) — never an image.
5. **Every hint level has its own voice-over** (N hints → N voiced).
6. Hints are **audio-only** (question text not replaced) — Zoe's rule.
7. Template type is set and correct.

The tab should show a per-question checklist of these 7, green/red, and block "Approve to portal"
until all pass. Reuse `scripts/bulk_import/verify_complete.py`'s logic as the completeness engine.

---

## 4. Proposed UI — the "Final Review" tab

Mirror QuestionStudio's layout (see §6 for the exact section map) so reviewers see the real thing.
Per question, one full-page "studio" view with:

- **Header:** ItemID, Subject/Topic, **Template type** (with the type selector, read-only or editable),
  Status (Pending/Active), and a **completeness checklist** (the 7 gates, green/red).
- **A faithful PREVIEW** of the assembled question rendered like the student portal
  (question text + image + options + the hint/speaker affordances), so they see the final result.
- **Inline Generate / Regenerate next to EVERY part:**
  - Question text → edit box (final text tweaks) + save.
  - Each option text + correct-answer toggle.
  - Question **voice-over** → play / (re)generate (ElevenLabs) / SSML editor / approve. (already exists)
  - Each **hint** text + hint **voice-over** → play / (re)generate / approve. (already exists)
  - Question **image** → generate/regenerate (OpenAI) → **but delivery goes via Canva→Airtable**
    (see §5 image caveat) → then re-sync into this view.
  - Option **images** (Select All) → same image path per option.
- **"Approve → Portal"** button: only enabled when all 7 gates pass; runs the verified load
  sequence into Victor's DB as Pending (or Active per policy), then re-verifies with verify_complete.

---

## 5. The hard part — image round-trip, and DB integration options

**Image caveat (unavoidable today):** images can't be generated straight into the final format.
The path is OpenAI → **Canva** (reformats) → Georgia downloads → **Airtable** → sync. So in the
Final Review tab, "regenerate image" starts that async loop; the tab must **poll/refresh** from
Airtable (and/or the DB/CDN once uploaded) to show the finished image. It won't be instant like
audio. Options: (a) show "image pending in Canva/Airtable" state with a refresh, (b) later, if
Canva→SVG can be automated, collapse the loop. Text/audio/hint changes CAN be immediate.

**DB integration — three build options (pick per appetite):**
- **A. Read-only mirror + drive existing scripts.** Tab READS Victor's DB (add pyodbc/AzureCliCredential
  to the app — but Railby has no `az login`; needs a service principal / SQL cred in env) to show real
  completeness, and "Approve" enqueues the SAME `scripts/bulk_import` steps. Lowest risk, reuses proven
  tooling, keeps writes auditable. **Recommended first version.**
- **B. Full read/write in the app.** The tab writes Question/SelectionOption/Blob/HintReplacement
  directly (replicating QuestionStudio's save). Most "studio-like" but re-implements Victor's save
  logic and raises the stakes (must honour idempotency, no-overwrite, load order, StatusCD rules).
- **C. Keep DB out-of-band.** Tab only assembles + shows completeness from spreadsheet+Airtable+local
  files (no DB), and exports a verified per-question manifest that we run through the scripts as now.
  Simplest, but "Approve → Portal" isn't one click.

**Auth note:** the app currently uses `AzureCliCredential` for DB (needs `az login`). Railway can't
`az login` — DB access from the deployed app requires a **service principal** or a **SQL login** stored
as a Railway env var (Victor would need to provision). This is the main blocker for options A/B and
should be raised with Victor.

---

## 6. QuestionStudio structure to mirror (from the code audit, 1 Sep 2026)

Source: `/Users/danielsamus/WW/WWApp/Components/Pages/Question/QuestionStudio.razor` (1907 lines)
+ `.razor.cs` (3929 lines). Two-column layout; left column = collapsible cards.

**Card order (mirror this):**
1. **Basic Information** — Question Type*, Title, Color Scheme*, Teacher Notes, Help content picker
   (+ Help scene), Incorrect-T/F-hint (T/F only).
2. **Question Configuration** (only after a type is chosen) — Template, Status, the **Template Elements
   table** (this is where question text/image/audio/reader live — NOT a separate media card), Correct
   Answer, Selection Options list.
3. **Classification** — Topic*, Difficulty*.
4. **Connection Rules** — Link questions only.
5. **Written Answer Options** — Written only.
6. **Question Hints** — hint levels + "Block Replacements".
7. **Preview Settings** — session/feedback toggles.

**Type handling (CRITICAL — two different codes):** the dropdown value is the **QuestionType CD**
(`ReferenceData.CD`: Select One=31, Written=32, Select All=33, True/False=34, Sort=115, Link=116),
which is DIFFERENT from **TemplateID** (1–6). Template is auto-narrowed from the type via
`TemplateTypeCD`. Our CLAUDE.md maps friendly names → TemplateID; keep BOTH mappings straight.
- Options list shows for Select One / Select All / Sort / Link; **hidden for True/False & Written**.
- True/False: no options, a True/False select + Incorrect-T/F-hint.
- Select All: options can each be Text OR Image (mutually exclusive) + optional Audio/Reader — this is
  where **option images** for the grid come from.
- Written → Written Answer Options table (CompareText/Score%/Hint). Link → SOURCE/TARGET groups.

**Media = the Template Elements table**, one row per `TemplateElement.HTMLElementID`, mapped to a
Question column (`MapElementToQuestionField`): `question-text-content`→TextHTML, `question-image`→ImageBlobID,
`question-audio`→AudioBlobID, `question-reader`→ReaderBlobID. `hint-*` elements are NOT question fields —
they're populated only by HintReplacement rows. All media picked via a shared `<BlobPicker>` (selects an
EXISTING BlobID by type; the studio never creates blobs). Mandatory elements show a "Required" pill and
block preview until set (`IsElementConfigured`/`IsMandatory`). → **Final Review must load the chosen
template's elements and show each one's configured/missing state.**

**Hints = "Block Replacements":** each hint level has replacements; each replacement targets an element
via a dropdown. **The audio-only-vs-replace-text choice IS the element you target** (there's no separate
radio): target `question-text-content` → text-only replacement (replaces question text); target
`hint-graphic-audio` → audio-blob-only (plays, doesn't replace). Exactly matches what we implemented.

**Preview = Victor's REAL student renderer.** `/Question/PreviewContent/{id}` renders
`<QuestionRenderer>` (the actual Template1–6 student components) in an iframe, with a preview-cache for
unsaved edits. → **Best option for a faithful preview: embed Victor's `/Question/PreviewContent/{id}`
iframe once the question is saved, rather than rebuilding the renderer in Flask.** (Needs the WWApp URL +
auth; a Victor ask.)

**Save = plain EF Core** (`SaveQuestionAsync`, no stored proc). Insert sets TemplateID, StatusCD default
PENDING, then adds QuestionClassification, SelectionOptions (StatusCD=Active), OptionGroups (Link),
WrittenAnswerOptions, QuestionHints + HintReplacements. **StatusCD is permission-gated** — Active forced
to Pending unless the user can set Active. Full field→column map is in the audit (Question, SelectionOption,
QuestionClassification, OptionGroup, WrittenAnswerOption, QuestionHint, HintReplacement).

**QuestionStudio's own "ready" gate** (complements our media gate §3): Save-valid = Topic + Difficulty +
Color Scheme + a specified Correct Answer + field validation; AND for preview, **all mandatory template
elements configured**. Our Final Review "100% complete" should be the UNION of this gate + the media gate.

**Don't mirror `QuestionForm.razor`** — it's a legacy simple modal, not the studio.

---

## 7. Open questions / to discuss
- Victor: OK to give the app a DB service principal / SQL login (for read, and maybe write)? Or keep
  writes via our scripts (option A/C)?
- Julie/Zoe: is one-click "Approve → Portal" wanted, or is a manual verified upload step fine?
- Image loop: acceptable to have images be async (Canva→Airtable refresh) while text/audio are instant?
- Scope: build read-only completeness view first (fastest win, uses `verify_complete.py`), add inline
  generate next, add DB write last?
