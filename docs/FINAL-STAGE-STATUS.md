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

## STILL TO DO (the last big piece)

**Terminal uploader** — reads `/api/final/manifest` (approved questions) and inserts each into
Victor's DB via `scripts/bulk_import/*`. Includes a NEW ingest step to link
`SelectionOption.ReaderBlobID` for per-option voice-overs (nothing does this yet). Build WITH Dan,
DevTest dry-run first, `verify_complete` after, never automatic, never prod first.

### Optional polish noticed
- Tidy the preview layout (smaller Lottie box, hide empty option-image circles when no image).
- Deeper version history (currently 5) if wanted.
- Rotate the SASCO service-account key (it appeared in chat during setup).

## Session commit range
`d9b9613` (WebP→Airtable, bypass Canva) … `10f7d39` (lottie-player.js). ~19 commits.
