# Get Help Lessons - Production Pipeline

## What We Built

An interactive HTML help lesson system that teaches students concepts when they click "Get Help" on a question. The first proof-of-concept is **Partitioning Numbers** (Year 1 Maths) — covering all 225 questions under that topic.

**Live demo:** Open `help/partitioning/index.html` in a browser.

## How It Works (Student Experience)

1. Student is stuck on a question (e.g., "37 is made up of 3 tens and 7 ones — True or False?")
2. Clicks **Get Help**
3. Teacher character appears, explains the concept using a **different number** (34, not 37) — teaches the skill without giving away the answer
4. Animated visuals build on screen as the teacher speaks (ten-frames, place-value charts, blocks, tally marks)
5. Student can navigate between scenes, replay, or skip ahead
6. Closes the help and returns to their question with the concept understood

## What's in Each Lesson

Each topic = **one HTML file** with multiple **scenes** (chapters). Each scene covers a different sub-skill.

Example — Partitioning Numbers has **9 scenes**:

| Scene | Title | Teaches | Question styles it covers |
|-------|-------|---------|--------------------------|
| 0 | Intro | What partitioning means | (setup) |
| 1 | Tens & Ones | Break a number into tens and ones | "Which number is 3 tens and 4 ones?" |
| 2 | How Many? | Count tens/ones in a number | "How many tens in 46?" |
| 3 | True/False | Check partition statements | "37 = 3 tens and 7 ones" (T/F) |
| 4 | Another Way | Non-standard partitioning | "Another way to represent 23" |
| 5 | Picture | Read block diagrams | "Which number is shown?" |
| 6 | Tally | Read tally marks | "What does this tally represent?" |
| 7 | Big & Small | Arrange digits | "Biggest number from 4, 1, 6?" |
| 8 | Outro | Call to action | "Now try it yourself!" |

Students can be **deep-linked to a specific scene** based on their question type — they don't have to watch the whole thing.

## Technical Components

Each lesson is a **single self-contained HTML file** with:

1. **Teacher voiceover** (MP3) — generated via ElevenLabs with word-level timestamps
2. **Animated visuals** — pure HTML/CSS/JS, no video rendering needed
3. **Teacher character video** — transparent WebM overlaid in a corner (the existing 3D teacher)
4. **Scene navigation** — tabs, prev/next buttons, auto-advance
5. **Progress bar** — draggable, seekable
6. **Deep linking** — `?scene=3` URL parameter jumps to a specific scene
7. **Responsive** — works on desktop, iPad, and phone
8. **VTT captions** — for accessibility

No Adobe suite, no video rendering, no manual compositing. Everything is code.

## Production Pipeline (How to Make Hundreds)

### What Julie/Kristie Provides

For each topic, we need:
1. **A script** — voiceover text + on-screen visual descriptions for each scene (like the Partitioning PDF)
2. **Question-bank coverage map** — which scenes cover which question styles
3. **Curriculum alignment** — NSW syllabus outcomes

Julie's Claude can help write these scripts efficiently. The Partitioning script took one conversation to produce.

### What Dan/Claude Builds

For each topic:

| Step | What | How | Time |
|------|------|-----|------|
| 1 | Generate audio | Run `node scripts/generate-audio.js` with script text | 2 min (automated) |
| 2 | Build HTML | Claude generates the HTML/CSS/JS from the script | 30-60 min |
| 3 | Test & polish | Open in browser, check animations sync with audio | 15-30 min |
| 4 | Upload | Run `import_blobs.py` to upload to `devblobs->helpcontent` | 2 min (automated) |

**Estimated per-topic time: ~1 hour** (compared to 4-8 hours for full Adobe video production)

### Scaling Strategy

1. **Phase 1 (Now):** Build 3-5 Maths topics to prove the pipeline (Addition, Subtraction, Partitioning, Counting, Patterns)
2. **Phase 2:** Build remaining Maths topics (~28 total for Stage 1)
3. **Phase 3:** English topics (~97 topics — will need different visual styles: word animations, phonics sounds, etc.)
4. **Phase 4:** Other subjects (~60 topics)
5. **Phase 5:** Stage 2 topics (~27 Maths + more)

As we build more, we'll develop reusable animation components:
- Ten-frames (Partitioning, Place Value, Addition)
- Number lines (Counting, Ordering, Skip Counting)
- MAB blocks (Place Value, Addition, Subtraction)
- Fraction shapes (Fractions)
- Clock faces (Time)
- Coin images (Money)

### What Victor Needs to Do

1. Wire up the "Get Help" button to load the HTML file from `devblobs->helpcontent`
2. Pass a `?scene=N` parameter based on the question type (so students land on the right scene)
3. The HTML files are self-contained — they just need to be served from the CDN

## File Structure

```
help/
  partitioning/
    index.html                    # The lesson (single file, ~1800 lines)
  (future topics here)

audio/help-partitioning/
  scene-0-intro.mp3               # 9 audio files
  scene-1-tens-and-ones.mp3
  ...
  scene-8-outro.mp3
  transcripts/                    # Word-level timestamps (for animation sync)
    scene-0-intro.json
    ...

data/gethelp/
  Help Video Script - Partitioning Numbers (Year 1).pdf    # Julie's script
  partitioning_00_intro.vtt       # Julie's VTT captions
  ...
```

## Comparison: HTML Lessons vs Full Video Production

| Factor | HTML Lessons | Adobe Video |
|--------|-------------|-------------|
| Time per topic | ~1 hour | 4-8 hours |
| Tools needed | Code editor + ElevenLabs | Character Animator + After Effects + Premiere |
| Teacher character | Transparent WebM overlay | Full green-screen compositing |
| Deep linking to scenes | Built in (URL params) | Requires chapter markers |
| Responsive (phone/tablet) | Native (HTML reflows) | Need 2 exports (16:9 + 9:16) |
| Updating text/numbers | Edit code, regenerate audio | Re-render entire video |
| Interactive elements | Can add buttons, hover effects, etc. | Baked into video, not interactive |
| Accessibility | Live text, screen readers, TTS | Captions only |
| File size | ~50-100KB HTML + ~3MB audio | ~50-100MB video |
| Can AI help build them? | Yes — Claude generates ~90% of the code | Limited — still need manual Adobe work |

## What Julie's Scripts Look Like

Julie's Claude produced a complete script for Partitioning that includes:
- Voiceover text for each scene
- On-screen visual descriptions
- Question-bank coverage map
- NSW syllabus alignment

This format works perfectly as input to our pipeline. Each new topic follows the same structure.

## Next Steps

1. **Julie reviews the Partitioning demo** and confirms the approach
2. **Julie + Claude produce scripts** for the next few topics (Addition, Subtraction, Counting, etc.)
3. **Dan + Claude build the HTML lessons** from those scripts
4. **Victor wires up the Get Help button** to load these files from blob storage
5. **Scale up** across all ~212 topics
