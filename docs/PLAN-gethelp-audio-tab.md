# Plan — "Get Help Audio Generation" tab (QuestionReview app)

**Dan's idea (14 Sep 2026):** The audio is the bottleneck for Get Help lessons. Decouple audio from video: give Zoe/Georgia a tab where they see each SCENE of each lesson (from Kristie's Drive scripts), generate its ElevenLabs narration, listen, and regenerate until perfect. Dan then builds the animated scene from the known-good audio. This replaces the "full AI video-builder" idea with something far simpler and achievable.

## Why this is the right shape
- Splits the two hard things: **audio perfection** (Zoe/Georgia) vs **scene animation** (Dan). No more doing both at once.
- Reuses what the app already has: ElevenLabs voiceover engine, **audio version history + restore** (`get_audio_versions`/`restore_version` — exactly "regenerate until perfect, keep old takes"), Drive-scoped service account, audio serving, versioned regeneration.
- Output = a folder of approved MP3s per lesson, named `scene-{N}-{slug}.mp3` — the exact input Dan's lesson-build workflow already expects.

## Source of the scripts (decision needed)
Kristie's Get Help scripts live in Google Drive as **`.docx`** (in "Scripts Completed" / "Script and Video completed" folders), NOT in the Sheets the app reads. Options:
- **A (recommended):** Read the `.docx` scripts directly from Drive via the service account (already has `drive` scope). Parse each into scenes (the format is consistent: `## Scene N: Title`, quoted narration lines, `ON SCREEN:` directions). Cache parsed scripts.
- **B:** One-time convert the ~44 `.docx` into a structured store (JSON per lesson) committed to the repo; the tab reads that. Simpler/faster in-app, but scripts then go stale vs Drive.
- Recommendation: **A**, with a local cache + "refresh from Drive" button.

## Data model (per scene)
```
lesson: { topic, subject, scenes: [ {n, title, narration, onScreen, audioStatus} ] }
```
- `narration` = the combined quoted lines for that scene (what gets sent to ElevenLabs).
- `audioStatus` = none | generated | approved.
- MP3 saved as `audio/help-{topic}/scene-{n}-{slug}.mp3` (matches Dan's build convention), with version history.

## The tab UI
1. **Lesson list** — all Get Help lessons (from Drive scripts): topic, subject, #scenes, audio progress (e.g. "5/8 approved").
2. **Lesson detail** — one row per scene:
   - Scene title + the narration text (editable, so Zoe/Georgia can fix wording that TTS mispronounces).
   - **Generate** button → ElevenLabs (Vonnie voice) → audio player appears.
   - **Regenerate** (re-roll — same as our "fuzzy, redo" flow), with **version history** to compare/restore takes.
   - **Approve** toggle per scene (marks that scene's audio as final).
   - Optional: speed control per scene (the generator already supports `speed`).
3. **Progress + export** — when all scenes approved, the lesson's MP3s are ready; Dan pulls them into the build. (Later: a "download lesson audio ZIP" button.)

## Reuse map (what already exists)
- Audio gen: `review_app/voiceover_engine.py` → `generate_for_question` pattern; underlying `scripts/generate-audio.js`/`generate_voiceovers.py` + ElevenLabs (voice `cupfa8...`). Add a small `generate_for_scene(text, out_path, speed)` wrapper.
- Versioning: `get_audio_versions` / `restore_version` — reuse verbatim for "regenerate until perfect".
- Audio serving: `/audio/<filename>` route already exists.
- Drive: service account (`GOOGLE_SA_JSON`/`GOOGLE_SA_KEY`) already has `drive` scope; add `python-docx` to requirements to parse scripts.
- Nav: add `<a href="/gethelp" class="nav-link">Get Help Audio</a>` to `base.html`.

## New pieces to build
- `review_app/gethelp_scripts.py` — read + parse the `.docx` scripts from Drive into the scene model (with cache).
- `review_app/gethelp_audio.py` — per-scene generate/regenerate/approve state (mirror `state.py`/`image_state.py`).
- Routes: `/gethelp` (list), `/gethelp/<topic>` (detail), `/api/gethelp/generate/<topic>/<scene>`, `/api/gethelp/approve/<topic>/<scene>`, `/api/gethelp/edit-narration/<topic>/<scene>`, reuse audio-versions/restore.
- Templates: `gethelp_list.html`, `gethelp_detail.html` (model on the existing question_list/question_detail patterns).

## Phasing (each is a checkpoint)
1. **Phase 1 — Read + show scripts (no audio yet).** Parse Drive `.docx` → lesson list + scene view in the tab. Prove the scripts load correctly and scenes are right. ✋ Dan reviews.
2. **Phase 2 — Generate + approve audio per scene.** Wire generate/regenerate/version/approve to ElevenLabs. Test on ONE lesson end-to-end (e.g. Ordering Numbers). ✋ Dan reviews.
3. **Phase 3 — Polish + export.** Progress indicators, per-scene speed, download-ZIP, tidy UI for Zoe/Georgia.
4. **Deploy** via `git push origin main` (NEVER `railway up`).

## Guardrails
- Deploy only via git push. Never `railway up`.
- Don't touch the existing Questions/Images/Final Stage tabs' behaviour.
- Audio generation costs ElevenLabs credits — generation is per-scene, explicit-button only (no auto/bulk on load).
- Store approved audio on the Railway volume (same place as question voiceovers) + committable so Dan can pull it.

## Decisions needed from Dan before building
1. **Script source:** read `.docx` live from Drive (A) or convert-once to JSON (B)? (Recommend A.)
2. **Which lesson to pilot in Phase 2** (suggest one with an approved script + that Dan wants next — e.g. Ordering Numbers or Money).
3. **Voice:** confirm same Vonnie voice `cupfa8uelkW7cWxLMRa7` for all scene audio.
