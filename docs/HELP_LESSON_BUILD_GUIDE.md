# Help Lesson Build Guide

Step-by-step instructions for turning an approved narration script (.docx) into a working animated HTML help lesson.

See also: `GETHELP-PIPELINE.md` for the high-level overview and `HELP-LESSONS.md` for concept mapping.

## Prerequisites

- Node.js installed
- `.env` file with `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`
- `python-docx` installed (for reading scripts): `pip install python-docx`
- Approved script in `data/questions/help-scripts/reviewed/`
- Teacher video at `assets/videos/teacher-transparent.webm`
- Fonts in `fonts/` (ApfelGrotezk Regular, Mittel, Fett)

## Per-Lesson Workflow

### Step 1: Extract Narration from Reviewed Script

Read the `.docx` from `data/questions/help-scripts/reviewed/{Topic}.docx`.

**Script format:**
- **Metadata block** — title, subject, category, question types, scene count, status
- **Scene headings** — `Scene 0: Intro`, `Scene 1: Take Away`, etc.
- **Narration lines** — text in quotes (read aloud by teacher voice)
- **ON SCREEN directions** — starts with `ON SCREEN:` (animation instructions, NOT read aloud)
- **Final scene** — always "Your Turn!" (outro)

**What to extract per scene:**
1. Scene number and title → becomes the scene tab label
2. All narration lines → combine into a single text string (for audio generation)
3. ON SCREEN directions → informs visual design (Step 5)

**Example:**
```
Scene 1: Take Away
"Let's start with a simple one."
"6 take away 4 is ?"
"We start with 6 and remove 4."
ON SCREEN: Title 'Take away'. Show 8 objects, cross out 3...
```

Combined narration: `"Let's start with a simple one. 6 take away 4 is ? We start with 6 and remove 4."`

### Step 2: Add Audio Entries to generate-audio.js

Open `scripts/generate-audio.js` and add a new const array:

```javascript
const helpSubtractionAudio = [
  { file: 'audio/help-subtraction/scene-0-intro.mp3',
    text: "Hello! Today we're learning about subtraction. ..." },
  { file: 'audio/help-subtraction/scene-1-take-away.mp3',
    text: "Let's start with a simple one. ..." },
  // ... one entry per scene
  { file: 'audio/help-subtraction/scene-10-outro.mp3',
    text: "Now it's your turn! Try some subtraction questions yourself." },
];
```

Then add to `allTemplates`:
```javascript
'help-subtraction': helpSubtractionAudio,
```

**Naming conventions:**
- Array name: `help{PascalCase}Audio` (e.g., `helpSubtractionAudio`)
- Template key: `help-{kebab-case}` (e.g., `help-subtraction`)
- Audio path: `audio/help-{topic}/scene-{N}-{slug}.mp3`
- Scene slugs: lowercase, hyphens, descriptive (e.g., `take-away`, `missing-number`)

**Speed:** Default is `0.9`. Use `speed: 0.8` for dense scenes with lots of numbers/calculations (see Addition scenes 7-8 for reference).

### Step 3: Generate Audio with Timestamps

```bash
node scripts/generate-audio.js help-{topic} --timestamps
```

This creates:
- `audio/help-{topic}/scene-{N}-{slug}.mp3` — audio files
- `audio/help-{topic}/transcripts/scene-{N}-{slug}.json` — character-level timestamps

**Verify:** Check that all MP3s exist and sound correct. Listen for pronunciation issues with maths terms.

### Step 4: Calculate Timeline Timestamps

The transcript JSON contains character-level timing data:
```json
{
  "characters": ["H", "e", "l", "l", "o", "!", " ", ...],
  "character_start_times_seconds": [0.0, 0.058, 0.093, ...],
  "character_end_times_seconds": [0.058, 0.093, 0.128, ...]
}
```

**Process:**
1. Reconstruct the full text: join `characters` array
2. Find where each narration line starts in the character stream
3. Read `character_start_times_seconds[index]` for the timestamp
4. Round to 1 decimal place

**Each narration line becomes a TIMELINES entry:**
```javascript
{ time: 0.0, action: () => { show('s1-title'); setCallout("Let's start with a simple one."); } },
{ time: 2.6, action: () => { setCallout("6 take away 4 is ?"); show('s1-equation'); } },
```

**Tips:**
- Visual actions (`show()`) trigger at the same time as or slightly before the callout
- The first timeline entry is always `time: 0.0`
- Intro scene starts with `showTeacher()` at 0.0
- Outro scene shows teacher + "Try" button
- Fine-tune by ±0.2-0.5s after browser testing

### Step 5: Design Visual Elements

Read the ON SCREEN directions from the script. Map to existing CSS/HTML patterns:

**Reusable patterns (from existing lessons):**

| Pattern | CSS Classes | Used In |
|---------|-------------|---------|
| Scene title | `.scene-title` | All |
| Intro title + emoji | `.intro-title .emoji` | All |
| Info cards | `.info-cards .info-card` | All |
| Equations | `.equation .eq-part` | Addition, Partitioning |
| Gap/missing number | `.gap-equation .gap-box` | Addition |
| Number line + hops | `.number-line .nl-hop` | Addition |
| Ten-frames | `.ten-frame .tf-dot` | Partitioning, Addition |
| Place value chart | `.pv-chart .pv-col` | Partitioning |
| MAB blocks | `.mab-ten .mab-one` | Partitioning |
| Tally marks | `.tally-bundle .tally-line` | Partitioning |
| Object groups + plus/equals | `.apple-group .plus-sign` | Addition |
| Dot groups (doubles) | `.dot-group .d-dot` | Addition |
| True/False statement | `.statement-card .verdict` | Partitioning, Addition |
| Story/word problem | `.story-text .keyword .number-hl` | Addition |
| Sum cards (correct/wrong) | `.sum-card .result-icon` | Addition |
| Word cards + highlights | Various | Homophones |

Create new patterns as needed — keep CSS naming consistent with `s{N}-{name}` convention.

### Step 6: Build the HTML File

Create `help/{topic}/index.html`. Structure:

```
1. DOCTYPE + head
2. Font loading (Apfel Grotezk — 3 weights)
3. Shared CSS (~150 lines — overlay, stage, controls, etc.)
4. Topic-specific CSS (varies — 50-200 lines)
5. Body:
   a. Back button
   b. Trigger button (topic name + emoji)
   c. Help overlay:
      - Close button, title
      - Scene tabs
      - Stage (380px, scenes inside)
      - Teacher video panel
      - Callout bar
      - Progress bar
      - Controls (Prev, Replay, Next, Got it)
      - Debug panel
   d. Audio elements (one per scene)
6. JavaScript:
   a. Refs (overlay, callout, progress, teacher)
   b. TIMELINES object
   c. Helper functions (topic-specific)
   d. resetScene() (topic-specific)
   e. Playback engine (shared boilerplate)
   f. Controls + event listeners (shared)
   g. Seeking (shared)
   h. Deep linking (shared)
```

**Stage background colours:**
- Maths: `linear-gradient(180deg, #E8F5E9 0%, #C8E6C9 100%)` (green)
- English: `linear-gradient(180deg, #FFF3E0 0%, #FFE0B2 100%)` (warm orange)
- Science: TBD
- PDHPE: TBD

**Copy boilerplate from:**
- Maths lessons → `help/addition/index.html`
- English lessons → `help/homophones/index.html`

### Step 7: Test in Browser

Open `help/{topic}/index.html` in Chrome/Safari.

**Checklist:**
- [ ] All scenes play through without console errors
- [ ] Audio syncs with callout text (within ~0.5s)
- [ ] Visual elements appear at correct times
- [ ] Teacher video appears on intro + outro
- [ ] Progress bar tracks and is seekable (drag to any position)
- [ ] Scene tabs switch correctly
- [ ] Auto-advance works (scene ends → next starts after 1s)
- [ ] Prev/Next/Replay buttons work
- [ ] Deep link works: `?scene=3` opens scene 3
- [ ] "Got it" button closes overlay
- [ ] Responsive at 600px width (Chrome DevTools → iPhone/iPad)
- [ ] No overlapping elements in stage area

### Step 8: Update Tracking

1. **PLAN.md** (`data/questions/help-scripts/PLAN.md`):
   - Update lesson status to "HTML BUILT" with date

2. **help/index.html**:
   - Add lesson card following existing pattern

3. **Commit** the new files:
   - `help/{topic}/index.html`
   - `audio/help-{topic}/*.mp3`
   - `audio/help-{topic}/transcripts/*.json`
   - Updated `scripts/generate-audio.js`
   - Updated `data/questions/help-scripts/PLAN.md`
   - Updated `help/index.html`

## Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| HTML file | `help/{topic}/index.html` | `help/subtraction/index.html` |
| Audio dir | `audio/help-{topic}/` | `audio/help-subtraction/` |
| Audio file | `scene-{N}-{slug}.mp3` | `scene-1-take-away.mp3` |
| Transcript | `transcripts/scene-{N}-{slug}.json` | `transcripts/scene-1-take-away.json` |
| JS array | `help{PascalCase}Audio` | `helpSubtractionAudio` |
| Template key | `help-{kebab-case}` | `help-subtraction` |
| Scene element | `id="scene-{N}"` | `id="scene-1"` |
| Audio element | `id="audio-{N}"` | `id="audio-1"` |
| Scene-specific el | `id="s{N}-{name}"` | `id="s1-equation"` |

## Responsive Rules

All lessons must work on different screen sizes. Victor's portal embeds lessons in an iframe of unknown dimensions.

**Stage height** — use `min()` not fixed px:
```css
.stage { height: min(380px, 55vh); }
/* At 600px breakpoint: */
.stage { height: min(300px, 50vh); }
```

**Stage overflow** — scroll, don't clip:
```css
.stage { overflow-y: auto; overflow-x: hidden; }
```

**Info cards** — always wrap on narrow screens:
```css
.info-cards { flex-wrap: wrap; justify-content: center; }
```

**Media query at 600px** — every lesson must have one. Scale down:
- `.scene-title` → 18px
- `.intro-title` → 26px
- `.callout` → 13px
- `.info-card` → 12px, padding 6px 12px
- `.scene-tab` → 10px
- `.teacher-panel` → 70x100px
- Large equations/answers → scale proportionally
- Topic-specific elements → scale as needed

**Testing** — check each lesson at:
- Full screen (desktop)
- 600px width (tablet)
- 400px width (phone)
- Use Chrome DevTools responsive mode

## ElevenLabs Settings

| Setting | Value |
|---------|-------|
| Model | `eleven_multilingual_v2` |
| Output format | `mp3_44100_128` |
| Stability | `0.5` |
| Similarity boost | `0.75` |
| Default speed | `0.9` |
| Slow speed (dense scenes) | `0.8` |

## Lesson Status Progression

```
Script generated → Uploaded to Drive → Teacher reviewed → Script approved
    → Audio generated → HTML built → Tested → LIVE on CDN
```
