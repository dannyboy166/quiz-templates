# Final Stage — Status & Build Record

Where the "Final Stage" tab of the QuestionReview web app is up to, as of **8 Sep 2026**.

App: https://web-production-bce96.up.railway.app · Deploy: `git push origin main` (Railway,
auto-deploy). NEVER `railway up`. Related docs: `FINAL-REVIEW-TAB-PROPOSAL.md`,
`FINAL-STAGE-DB-FIELD-MAP.md`.

---

## What the Final Stage tab is

One place where Georgia/Zoe build a whole question to 100% — text, image, question voice-over,
per-option voice-overs, hints — then **approve it for upload**. It's the QC gate before Dan does
the (separate, manual) bulk upload into Victor's database.

- **List:** `/final` — every question with a progress bar + status pill (Approved / Ready /
  Needs work / Not started), search + filters.
- **Detail:** `/final/<item_id>` — student-style preview, inline editing, generate/regenerate
  everything, completeness checklist, approve button.

## Data flow (decided this session)

- **Google Sheets = source of truth** for text/options/hints/answers. The whole app now reads
  LIVE from the 3 master sheets (not the old stale xlsx snapshot). Editable in the app (writes
  straight back to the sheet).
- **App volume** = working media (generated images PNG, voice-overs MP3) + JSON state.
- **Airtable = image library/archive.** Every approved image is saved there (WebP). Browsable by
  the team. Auto-refreshed every 6h so preview URLs stay fresh.
- **Victor's DB/CDN = final destination**, reached via the MANUAL terminal upload step (NOT built
  yet). The app NEVER writes to Victor's DB.

## Features (all BUILT & DEPLOYED)

| Area | What it does |
|------|--------------|
| Live Google Sheets | Whole app reads live; live-first with a **loud red "stale" banner** + auto-retry on transient Google 503/429. Manual "reload" + `/api/data-source`. |
| Assembly + checklist | Per-question completeness gates (type-aware). Complete = all gates green. |
| Student preview | Question + speaker (plays audio), options as cards each with a speaker, **correct row green**, images inline, **Lottie animations actually play** (`<lottie-player>`). |
| Inline editing | Click any field (question/options/answer/hints) → "Save to sheet" writes to the live Google Sheet + logs the change. No app-only save; warns on unsaved edits. |
| Question image | Generate (OpenAI), **Tweak** (edit existing — keep it, change X), **Previous versions / revert** (keeps last 5), **Approve & send to Airtable**. |
| Question voice-over | Generate/regenerate (ElevenLabs). |
| Per-option voice-over | NEW: one MP3 per option (`{item_id}-option{n}.mp3`) → target DB col `SelectionOption.ReaderBlobID`. Required for completeness on options that have text. |
| Hints | Generate/regenerate hint audio per level. |
| Generate everything | One click fills every MISSING image + VO (skips existing unless forced; never sends an empty image prompt). |
| Final Approve | Only when 100% complete (server re-checks). Writes an approval ledger + `/api/final/manifest` (the upload list). |

## Completeness gates (what "Ready" means)

Per question type: Question text · Question type set · Correct answer · Answer matches an option ·
≥2 options · Question image · Image on every option (Select All) · Question voice-over · Each
option voiced (options with text) · Each hint voiced. True/False & Written skip the options gates;
Written doesn't require an Answer cell.

## Key files (review_app/)

- `gsheets_loader.py` — live Google Sheets read + write-back (`update_field`), retry, cache.
- `final_stage.py` — `assemble()` (whole-question view + gates), `Presence` (fast dir-listing
  cache), `summary_row()`.
- `final_state.py` — approval ledger (atomic writes).
- `app.py` — routes: `/final`, `/final/<id>`, `/api/final/{edit,approve,unapprove,manifest,
  generate-all,stats}`, `/api/generate-option/<id>/<n>`, `/api/data-source`, `/api/reload-questions`.
- `voiceover_engine.py` — `generate_for_option` (per-option VO).
- `templates/final_list.html`, `final_detail.html`.

## Auth / safety

- App gated by `ACCESS_PASSWORD` (+ `SECRET_KEY`). `/api/pipeline-stats` is gated (was leaking
  content); programmatic callers pass `X-Access-Token`. Only `/healthz` + `/api/data-source` open.
- State files write atomically (safe for concurrent Georgia + Zoe).
- Google service account: `GOOGLE_SA_JSON` (Railway) or `GOOGLE_SA_KEY` (local). Has read+write.

## Added since first status save (8 Sep, later)

- **Lottie animations PLAY** in the preview (`<lottie-player>`, served at `/assets/js/lottie-player.js`).
  Fixed a bug where that JS file was untracked in git → 404 on deploy.
- **Image "Tweak"** (edit existing image, keep it/change X, via `/api/images/edit`) + **"Previous
  versions" revert** (keeps last 5) — on BOTH Final Stage and Images tabs.
- **Audio version history**: every VO regenerate archives the previous take (`{stem}-v{N}.mp3`,
  keeps 5). "↩ Previous takes" on question VO / each hint / each option → listen + revert
  (non-destructive). Endpoints `/api/audio-versions/<stem>`, `/api/restore-audio/<stem>/<n>`.
- **Voiced options** now have 🔊 play + Regenerate (was showing only "✓ voiced", no controls).
- **ElevenLabs 502 fix**: `generate_audio` now has a 90s timeout + retry on transient
  (429/500/502/503/504/network). A hung call previously bubbled up as a gunicorn 502. UI shows
  "Server was busy — please click again" for 5xx.
- **Airtable cache** kept image URLs + auto-refreshes on boot and every 6h (previews stay fresh).

## Added since (8 Sep, evening)

- **Voiced options** get play + Regenerate + revert (were controls-less). **Audio version
  history** on question/hint/option VOs. **ElevenLabs 502 fix** (timeout + retry).
- **"Tweak image"** works on Airtable-only raster images (downloads first). Old SVG/Lottie
  images are NOT tweakable (would lose the cutout) — they show "Make new image" instead
  (`q_image_tweakable` flag). Genuine raster images tweak/revert fine.
- **Hint image generation**: per-hint optional image (`{item_id}-hint{n}.png` → DB element
  `hint-graphic`), with version history. "Approve & send to Airtable" pushes WebP to the
  existing **`Hint 1/2/3 Image`** Airtable columns (verified they exist). Endpoints
  `/api/images/generate-hint/<id>/<n>`; approve via `image_type:"hint"` + `hint_num`.
- **"Change how it's read aloud"** editor per question / hint / option: a speech-override
  (SSML) that changes the AUDIO only, never the real text — add pauses `<break time="0.5s"/>`,
  reword for clearer speech. Stored as `speech_override` (already honored by the generators).
  Endpoints: `/api/update-speech`, `/api/update-hint-speech`, `/api/update-option-speech`,
  `/api/speech-text` (returns current override + default to pre-fill + Reset).

## Airtable image columns (verified 8 Sep)
Question → "Question Image SVG"; Options → "Answer A/B/C/D Image"; Hints → "Hint 1/2/3 Image".
(`review_app/airtable_push.py` IMAGE_COLUMN_MAP.)

## Georgia's feedback round (8 Sep) — 11 items shipped

Fixed/added: VO no leading break + ends on period (#9); mid-sentence 'a' lowercase (#11);
VO speed control (#8); speech editor available pre-VO (#1,#7); True/False answer VOs (#10);
per-option image generation (#6); image gate = question image OR all-option images (#15);
upload-image button (ChatGPT etc → PNG→WebP→Airtable, #16); hint image can use the question
graphic (#2); flag + notes per question (#12); topic filter+sort + flagged filter (#5).

Investigated (answers, no build): transparent=checkered IS real transparency (#3); 20012115
image IS in Airtable, app auto-refreshes now (#4); multiple question images = only ~5 of 5353
questions have >1 attachment, app shows first (#13, edge case). DEFERRED: "Uploaded" tab (#14)
until the terminal uploader exists.

## Known issues / feedback logged

- **WebP alpha corruption (Victor's side):** after Victor converted the image library to WebP,
  transparent / fake-SVG-wrapped-PNG images render broken (black box / white silhouette) in the
  student portal. Full report: `docs/WEBP-ALPHA-BUG-for-victor.md`. Fix = re-convert from the REAL
  image, preserve alpha. Not our app. SEND TO VICTOR.
- **AudioBlobID on questions (fixed our side):** our ingest set the question VO on BOTH
  ReaderBlobID and AudioBlobID; AudioBlobID makes hovering the student image replay the question
  audio (audio from two places). Decision: Reader only. `ingest_voiceovers.link_question` fixed
  going forward; `scripts/bulk_import/clear_question_audioblob.py` nulls AudioBlobID on
  already-loaded questions (dry-run default, --apply, --revert). RUN MANUALLY on DevTest.

## STILL TO DO

1. **Terminal uploader** (the last big piece) — reads `/api/final/manifest` (approved questions)
   and inserts each into Victor's DB via `scripts/bulk_import/*`. Includes a NEW ingest step to
   link `SelectionOption.ReaderBlobID` for per-option voice-overs (nothing does this yet). Build
   WITH Dan, DevTest dry-run first, `verify_complete` after, never automatic, never prod first.
2. **Run `clear_question_audioblob.py`** on DevTest (manual, dry-run first) to fix already-loaded Qs.
3. **Send Victor** `docs/WEBP-ALPHA-BUG-for-victor.md`.

### Optional polish
- Tidy the preview layout (smaller Lottie box, hide empty option-image circles when no image).
- Rotate the SASCO service-account key (it appeared in chat during setup).

## Deploy health (verified 8 Sep, later)
`/healthz` 200 · `/api/data-source` mode=live 7456 · `/final` 302 · lottie-player.js 200 · audio-versions route live.
