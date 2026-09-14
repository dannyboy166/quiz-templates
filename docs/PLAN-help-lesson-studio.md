# Plan — Help Lesson Studio (data-driven lessons + AI editor + voiceovers)

**Goal:** A tool where the current 7 help lessons live, can be edited by hand or via AI chat, new lessons get built from the Google Drive scripts, and ElevenLabs voiceovers are generated in-app — mirroring the "complete question" web app already built. Big project, built in careful phases, each with a checkpoint.

---

## What exists today (verified, not assumed)

- **7 built lessons**, bespoke hand-coded HTML at `help/<topic>/index.html`; each scene is a `<div class="scene" id="scene-N">` with unique inline visuals. 60 scenes total. Audio in `audio/help-<topic>/scene-*.mp3`. Live at GitHub Pages gallery.
- **Only Partitioning + Addition are on Victor's CDN** (in the student portal). The other 5 are gallery-only.
- **44 teacher-approved scripts** in Google Drive (`Scripts Completed` = 21, `Script and Video completed` = 23; `To be Checked` empty). Scripts have a consistent structure: meta header, `Topics Covered`, `Scene-Topic Mapping`, then `## Scene N:` blocks with quoted narration + `ON SCREEN:` visual directions.
- **QuestionReview app** (Flask, Railway): `review_app/app.py`, per-feature engines (`voiceover_engine.py`, `image_engine.py`, `final_stage.py`), `state.py`, Jinja templates, nav in `base.html` (Dashboard/Questions/Library/Images/Final Stage). Deploy = `git push origin main`. NEVER `railway up`.
- **Voiceover engine already reusable:** `review_app/voiceover_engine.py` wraps `generate_voiceovers.py`, ElevenLabs, "Vonnie" voice ID `cupfa8uelkW7cWxLMRa7`, settings finalised. This is the same machinery the question app uses — the lesson editor calls it too.

## Core idea

Turn each lesson from bespoke HTML into **data (JSON)** + **one renderer**. A scene becomes `{ id, title, narration, visual, items, onScreen }` where `visual` is one of a fixed menu of visual types derived from what the 7 lessons actually do (ten-frame, number-line, object-groups, clock, calendar, word-cards, equation, etc.). Then:
- AI edits = edit small JSON (cheap, ~fraction of a cent/edit — each edit is its own short request, not one growing megathread).
- Teachers edit = safe fields, can't break layout.
- New lesson = parse a Drive script → JSON (agents can do this in parallel).
- Audio = per-scene ElevenLabs on an explicit "generate" button (controls the one real cost).

---

## Phase 0 — Cost & risk guardrails (bake in from the start)
- **Text edits** use a cheap model (Haiku) with only the single lesson JSON in context, stateless per edit — no accumulating conversation. Target < 1 cent/edit.
- **Audio** generated only on explicit button, per-scene, and cached — never auto-regenerate on every keystroke. Show a "N scenes need new audio" indicator.
- Every AI edit returns a **diff preview** the user accepts/rejects before it's saved — no silent overwrites.
- Keep a per-lesson version history (JSON snapshots) so any edit is revertable.

## Phase 1 — Format + renderer (the make-or-break proof)  ✋ checkpoint
1. Design the scene JSON schema + enumerate the visual-type menu by auditing all 7 existing lessons' scenes.
2. Build ONE self-contained `renderer` (HTML/CSS/JS) that plays any lesson JSON: scene nav tabs, progress bar, audio sync, replay, auto-advance, `?scene=N` deep-link, responsive — matching current lessons' behaviour.
3. **Convert Addition to JSON** and render it. Put original vs data-driven side by side.
4. **STOP. You review:** does the data-driven Addition look as good as the hand-built one? If not, we fix the format now, on one lesson, before scaling. If the renderer can't match quality, we reconsider before building 44.

## Phase 2 — Convert the rest to data  ✋ checkpoint
1. Convert the other 6 built lessons → JSON (must render identically; nothing regresses).
2. Build a **Drive script parser**: read a `.docx` from Drive → structured scenes (narration + on-screen notes) → draft lesson JSON. Test on 2–3 scripts (e.g. Spelling & Editing, 2D Shapes).
3. **You review** a couple of auto-converted lessons for quality before batch-running all ~37.

## Phase 3 — The Studio tab (in QuestionReview app)  ✋ checkpoint
1. Add a **"Help Lessons"** nav item + list view (all lessons: built / draft / has-audio / on-CDN status).
2. Detail view: **live preview on the left, AI chat on the right** (the "like working with Claude" part). Chat edits the JSON → diff preview → accept → live re-render → save. Manual field editing too (reword narration, swap emoji/visual) for non-AI users.
3. Wire the **"Generate voiceover"** button per scene/lesson to the existing `voiceover_engine` (Vonnie voice). Reuse, don't rebuild.
4. Reads Drive scripts in-app so a new lesson can be started from its script with one click.

## Phase 4 — Batch build + deploy  ✋ checkpoint
1. Use agents to convert all remaining approved scripts → lesson JSON (parallel, cheap).
2. Generate audio per lesson (batched, resumable, your ElevenLabs key).
3. Regenerate the gallery from data. Hand the built set to Victor for CDN upload (needs his final container path) — take the portal from 2 → all.

---

## Decisions CONFIRMED with Dan (2026-09-14)
1. **Where it lives:** ✅ New **"Help Lessons"** tab inside the existing QuestionReview Flask app (reuses auth, deploy, Vonnie voiceover engine). Not a standalone app.
2. **Quality bar:** ✅ The data format MUST reproduce the current 7 hand-built lessons. This is the hard Phase 1 gate — if the renderer can't match them, we stop and rethink before scaling.
3. **Phase 1 scope:** ✅ Build the renderer + convert **ONLY Addition** to JSON, then STOP for Dan's side-by-side review. No mass conversion until approved.

## Still to confirm (not blocking Phase 1)
- **ElevenLabs:** "Vonnie" voice `cupfa8uelkW7cWxLMRa7` + existing `.env` key/quota OK for lesson audio. (Only needed at Phase 2/3 when generating new audio — Phase 1 reuses existing Addition MP3s.)

## Guardrails
- Deploy only via `git push origin main`. Never `railway up`.
- Don't touch Victor's DB or existing question/image/voiceover features.
- Nothing auto-uploads to the CDN — that stays a deliberate handoff to Victor.
- The 7 existing lessons are the reference; they must not regress.
