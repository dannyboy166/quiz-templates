# Quiz Templates - Developer Integration Guide

## Overview

These templates are **UI/UX prototypes** demonstrating interactive question types for the education portal. Victor will need to:

1. Recreate these as **Blazor components**
2. Set up **Excel import** with a `template_type` column
3. Map Excel columns to each template's required data fields

---

## Template Types & Required Data Fields

### 1. Draggable Clock (`clock`)

Student drags clock hands to show a time. Supports difficulty-based random generation.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"clock"` |
| `question_text` | string | No | Default: "Set each clock to show the time below it" |
| `difficulty` | string | Yes | `"hours-only"`, `"half-hours"`, `"quarters"`, `"five-minutes"` |

**Difficulty Options:**
- `hours-only` - Only :00 times (3 o'clock, 9 o'clock)
- `half-hours` - :00 and :30 times (3:00, 3:30, half past 3)
- `quarters` - :00, :15, :30, :45 (quarter past, half past, quarter to)
- `five-minutes` - Any 5-minute interval (3:05, 3:10, 6:25, etc.)

**Example Excel Row:**
```
template_type: clock
difficulty: half-hours
```

**Standalone Mode:**
The template generates 4 random times per round based on the selected difficulty. Students set all 4 clocks, then check their answers. Different times are generated each time the activity is played.

---

### 2. Drag & Drop Sorting (`drag-drop`)

Drag items into categorized containers (e.g., shapes into jars by sides).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"drag-drop"` |
| `question_text` | string | Yes | Instructions |
| `items` | JSON array | Yes | Items to sort: `[{"id": "triangle", "label": "Triangle", "category": "3"}]` |
| `categories` | JSON array | Yes | Containers: `[{"id": "3", "label": "3 Sides"}, {"id": "4", "label": "4 Sides"}]` |

**Example Excel Row:**
```
template_type: drag-drop
question_text: Sort the shapes by number of sides
items: [{"id":"tri","label":"Triangle","image":"triangle.svg","category":"3"},{"id":"square","label":"Square","image":"square.svg","category":"4"}]
categories: [{"id":"3","label":"3 Sides"},{"id":"4","label":"4 Sides"},{"id":"5","label":"5 Sides"}]
```

**Note:** For complex JSON, consider a separate "question bank" table with relationships, or a JSON config file per question set.

---

### 3. Colour the Blocks (`color-blocks`)

**Standalone Auto-Generated Template** - No Excel import needed!

Click 3D isometric blocks to colour tens and ones to make a number. Fully auto-generated with 10 questions per round.

| Setting | Value | Description |
|---------|-------|-------------|
| Questions per round | 10 | Fixed challenge length |
| Block style | 3D isometric SVG | Matching base10-blocks visual style |
| Progress tracking | Yes | Compass progress bar + Question X of 10 |

**Difficulty Options (selected on start screen):**
- `Ones Only` - Numbers 1-9 (single digits, no tens columns)
- `Easy` - Numbers 10-50 (small two-digit)
- `Medium` - Numbers 51-99 (large two-digit)
- `Hard` - Numbers 100-999 (with hundreds)

**How It Works:**
1. Student selects difficulty on start screen
2. Template generates 10 random target numbers within that range
3. For each question, student clicks blocks to colour the correct amount
4. Progress bar updates after each correct answer
5. Final score shown after 10 questions

**Features:**
- 3D isometric SVG blocks matching base10-blocks style:
  - Orange cubes (ones)
  - Red columns (tens, 10 each)
  - Blue flats (hundreds, 100 each)
- Paint/Erase/Clear tools
- Blocks auto-adjust based on target number
- Read aloud, help, and hint functionality
- Score tracking across all 10 questions

**Note:** This template requires NO Excel import - it's ready to use as-is!

---

### 4. Spelling Letters (`spelling`)

Drag letters to spell a word shown by a picture.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"spelling"` |
| `word` | string | Yes | Word to spell (e.g., "dog") |
| `image_url` | string | Yes | Picture of the word |
| `extra_letters` | string | No | Distractor letters (e.g., "xyz") |

**Example Excel Row:**
```
template_type: spelling
word: cat
image_url: /images/cat.png
extra_letters: bfm
```

**System generates:** Letter bubbles from word + extra_letters, shuffled.

---

### 5. Word Match (`word-match`)

Match words to pictures by dragging.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"word-match"` |
| `question_text` | string | Yes | Instructions |
| `pairs` | JSON array | Yes | `[{"word": "cat", "image_url": "/images/cat.png"}]` |
| `distractor_words` | JSON array | No | Extra wrong words: `["dog", "rat"]` |

**Example Excel Row:**
```
template_type: word-match
question_text: Match each word to its picture
pairs: [{"word":"ear","image":"/img/ear.png"},{"word":"hat","image":"/img/hat.png"}]
distractor_words: ["car","bat","map"]
```

---

### 6. Number Order (`number-order`)

Drag numbers into order from smallest to biggest.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"number-order"` |
| `question_text` | string | Yes | Instructions |
| `numbers` | JSON array | No | Specific numbers: `[5, 12, 3, 8]` |
| `random_min` | integer | No | Generate random numbers from this min |
| `random_max` | integer | No | Generate random numbers up to this max |
| `random_count` | integer | No | How many random numbers to generate |
| `order` | string | No | `"ascending"` (default) or `"descending"` |

**Example Excel Row (specific numbers):**
```
template_type: number-order
question_text: Put these numbers in order, smallest to biggest
numbers: [15, 3, 28, 11, 7]
```

**Example Excel Row (random):**
```
template_type: number-order
question_text: Order smallest to biggest
random_min: 1
random_max: 50
random_count: 5
order: ascending
```

---

### 7. Sound Select (`sound-select`)

Select all images that begin with a target letter sound (phonics). Multi-select.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"sound-select"` |
| `target_sound` | string | Yes | The letter/sound (e.g., "m", "s", "b") |
| `question_text` | string | Yes | e.g., "Select images that begin with the m sound" |
| `images` | JSON array | Yes | `[{"name": "moon", "image_url": "/img/moon.png", "starts_with_sound": true}]` |
| `hint` | string | No | Hint text for the sound |

**Example Excel Row:**
```
template_type: sound-select
target_sound: m
question_text: Select the images that begin with the m sound.
images: [{"name":"mouse","image_url":"/img/mouse.png","starts_with_sound":true},{"name":"apple","image_url":"/img/apple.png","starts_with_sound":false},{"name":"moon","image_url":"/img/moon.png","starts_with_sound":true}]
hint: Say each picture's name out loud. Does it start with "mmm"?
```

**Note:** `starts_with_sound: true` marks correct answers. Students must select ALL correct images.

---

### 8. Line Match (`line-match`)

Draw lines to connect matching pairs (shapes to sides, animals to sounds, numbers to words, etc.).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"line-match"` |
| `question_text` | string | Yes | Instructions for the matching |
| `left_items` | JSON array | Yes | Items on left side with match IDs |
| `right_items` | JSON array | Yes | Items on right side |
| `hint` | string | No | Hint text |

**Left Items Structure:**
```json
[
  {"id": "triangle", "type": "shape", "shape": "triangle", "color": "#CDDC39", "match": "3"},
  {"id": "dog", "type": "emoji", "emoji": "🐕", "match": "woof"},
  {"id": "n1", "type": "number", "text": "1", "match": "one"}
]
```

**Right Items Structure:**
```json
[
  {"id": "3", "type": "label", "text": "3 sides"},
  {"id": "woof", "type": "label", "text": "Woof!"}
]
```

**Item Types:**
- `shape`: SVG shape (triangle, square, rectangle, oval, semicircle)
- `emoji`: Emoji character
- `number`: Number display
- `label`: Text label (typically for right side)

**Example Excel Row:**
```
template_type: line-match
question_text: Match each animal to its sound
left_items: [{"id":"dog","type":"emoji","emoji":"🐕","match":"woof"},{"id":"cat","type":"emoji","emoji":"🐱","match":"meow"}]
right_items: [{"id":"woof","type":"label","text":"Woof!"},{"id":"meow","type":"label","text":"Meow!"}]
hint: Think about what sound each animal makes!
```

**Note:** The `match` field in left_items must correspond to an `id` in right_items.

---

### 9. Word Sort (`word-sort`)

Sort words into categories based on spelling patterns (e.g., st__ vs __st, -ing vs -ed endings).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"word-sort"` |
| `question_text` | string | Yes | Instructions for sorting |
| `words` | JSON array | Yes | Words to sort with their category |
| `categories` | JSON array | Yes | Category definitions with patterns |
| `hint` | string | No | Hint text |

**Words Structure:**
```json
[
  {"word": "stop", "category": "st-start"},
  {"word": "nest", "category": "st-end"},
  {"word": "star", "category": "st-start"}
]
```

**Categories Structure:**
```json
[
  {"id": "st-start", "header": "st__", "example": "stop", "pattern": "^st"},
  {"id": "st-end", "header": "__st", "example": "nest", "pattern": "st$"}
]
```

**Pattern Format:** Uses regex patterns - `^st` means starts with "st", `st$` means ends with "st".

**Example Excel Row:**
```
template_type: word-sort
question_text: Sort these words by their spelling pattern
words: [{"word":"stop","category":"st-start"},{"word":"nest","category":"st-end"},{"word":"star","category":"st-start"},{"word":"best","category":"st-end"}]
categories: [{"id":"st-start","header":"st__","example":"stop"},{"id":"st-end","header":"__st","example":"nest"}]
hint: Look at where the 'st' appears in each word!
```

**Note:** Words appear as bullet-point lists in notebook-style drop zones.

---

### 10. Missing Letters (`missing-letters`)

Choose missing letters to complete a word. Great for spelling rules like "i before e except after c".

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"missing-letters"` |
| `question_text` | string | Yes | Instructions |
| `word` | string | Yes | The complete word (e.g., "believe") |
| `blank_positions` | JSON array | Yes | 0-indexed positions of missing letters: `[3, 4]` |
| `options` | JSON array | Yes | Letter choices: `["ie", "ei"]` |
| `correct_option` | string | Yes | The correct choice (e.g., "ie") |
| `meaning` | string | No | Definition/hint about the word |
| `hint` | string | No | Hint text for the spelling rule |
| `rule` | string | No | The spelling rule being practiced |

**Example Excel Row:**
```
template_type: missing-letters
question_text: Choose the missing letters!
word: believe
blank_positions: [3, 4]
options: ["ie", "ei"]
correct_option: ie
meaning: to think something is true
hint: There's no 'c' before the blank!
rule: i before e, except after c
```

**Common Spelling Rules to Practice:**
- "i before e, except after c" - believe/receive, thief/ceiling
- Silent letters - kn_ght (knight), wr_te (write)
- Double letters - happ_ness (happiness), runn_ng (running)
- Vowel patterns - b_at (boat/beat), r_in (rain/ruin)

---

### 11. Spelling Rules (`spelling-rules`)

Comprehensive spelling rules practice with multiple rule categories. Students switch between rules.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"spelling-rules"` |
| `rule_id` | string | Yes | Rule category identifier |
| `rule_name` | string | Yes | Display name for the rule |
| `rule_hint` | string | Yes | Short hint for the rule |
| `rule_help` | string | Yes | Detailed explanation (HTML allowed) |
| `questions` | JSON array | Yes | Array of question objects |

**Rule Categories (20 rules, 120 questions total):**

*Australian Spelling:*
- `aus-our` - Australian -our spelling (colour, favour, neighbour)
- `aus-ise` - Australian -ise spelling (organise, realise)
- `aus-re` - Australian -re spelling (centre, metre, theatre)

*Classic Rules:*
- `ie-ei` - i before e, except after c (believe, receive)
- `magic-e` - Magic E makes vowel long (hat→hate, bit→bite)
- `silent` - Silent letters (knight, write, gnome, thumb)
- `soft-c` - Soft c and g before e/i/y (city, giant)

*Consonant Rules:*
- `ck-k` - ck vs k (back vs bake)
- `tch` - -tch after short vowels (catch, witch)
- `dge` - -dge after short vowels (badge, fudge)
- `floss` - FLOSS rule ff/ll/ss/zz (stuff, bell, miss, buzz)
- `double` - Double consonants before -ing (running, hopping)

*Suffix Rules:*
- `drop-e` - Drop the E before -ing (make→making)
- `change-y` - Change Y to I (happy→happier, cry→cried)
- `ful` - -ful has one L (beautiful, careful)

*Plural Rules:*
- `plural-es` - Add -es for s/x/z/ch/sh (boxes, buses)
- `plural-ies` - Change y to -ies (baby→babies)

*Sound Patterns:*
- `ph-f` - ph makes /f/ sound (phone, elephant)
- `qu` - Q always with U (queen, quiet)
- `tion-sion` - -tion vs -sion endings (station, television)

*Homophones:*
- `homophones` - their/there/they're, your/you're, to/too/two

**Question Structure:**
```json
{
  "word": "colour",
  "blank": [3, 4, 5],
  "options": ["our", "or"],
  "correct": "our",
  "meaning": "red, blue, green...",
  "context": "\"What colour is the sky?\""
}
```

**Example Excel Row:**
```
template_type: spelling-rules
rule_id: aus-our
rule_name: Australian -our spelling
rule_hint: In Australia, we use -our not -or! 🇦🇺
questions: [{"word":"colour","blank":[3,4,5],"options":["our","or"],"correct":"our","meaning":"red, blue, green","context":"What colour?"}]
```

---

### 12. Picture Equations (`picture-equations`)

Visual maths with pictures showing addition/subtraction. Some pictures are crossed out to show subtraction.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"picture-equations"` |
| `operation` | string | Yes | `"addition"`, `"subtraction"`, or `"mixed"` |
| `emoji` | string | Yes | The emoji/picture to use (e.g., "🍎") |
| `equations` | JSON array | Yes | Array of equation objects |

**Subtraction Equation Structure:**
```json
{
  "type": "subtraction",
  "total": 8,
  "subtract": 3,
  "result": 5,
  "given": ["total"],
  "blanks": ["subtract", "result"]
}
```

**Addition Equation Structure:**
```json
{
  "type": "addition",
  "num1": 4,
  "num2": 3,
  "result": 7,
  "given": ["num1", "num2"],
  "blanks": ["result"]
}
```

**given/blanks options:**
- Subtraction: `total`, `subtract`, `result`
- Addition: `num1`, `num2`, `result`

**Example Excel Row:**
```
template_type: picture-equations
operation: subtraction
emoji: 🍐
equations: [{"type":"subtraction","total":8,"subtract":3,"result":5,"given":["total"],"blanks":["subtract","result"]}]
```

**Features:**
- Pictures with red line through crossed-out items
- Number pad for touch input
- Subtraction, Addition, or Mixed modes
- Random equation generation

---

### 13. Fractions (`fractions`)

Click to shade parts of shapes to represent fractions. Supports circles (pizza) and rectangles (chocolate bar). Supports difficulty-based random generation.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"fractions"` |
| `difficulty` | string | Yes | `"halves"`, `"quarters"`, `"mixed"`, `"eighths"` |

**Difficulty Options:**
- `halves` - 1/2 only
- `quarters` - 1/4, 2/4, 3/4
- `mixed` - Halves + quarters combined
- `eighths` - Include 1/8 through 7/8 (plus halves and quarters)

**Example Excel Row:**
```
template_type: fractions
difficulty: quarters
```

**Standalone Mode:**
The template generates 8 random fraction questions based on the selected difficulty. Each question randomly uses either a circle (pizza) or rectangle (chocolate bar) shape. Students complete all 8 questions, then can play again with new fractions.

**Features:**
- Click parts to shade/unshade them
- Counter shows "You shaded X out of Y parts"
- Progress dots track completion of all 8 questions
- Shapes automatically adjust grid for denominator (e.g., 8ths use 4x2 grid)

---

### 14. Skip Counting (`skip-counting`)

Fill in missing numbers in a counting sequence. Supports difficulty-based random generation.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"skip-counting"` |
| `difficulty` | string | Yes | `"easy"`, `"medium"`, `"hard"`, `"expert"` |

**Difficulty Options:**
- `easy` - Count by 1s or 2s (randomly selected per question)
- `medium` - Count by 3s, 5s, or 10s
- `hard` - Count by 4s or 6s
- `expert` - Count by 7s, 8s, or 9s

**Example Excel Row:**
```
template_type: skip-counting
difficulty: medium
```

**Standalone Mode:**
The template generates 6 random skip counting questions based on the selected difficulty. Each question randomly selects a skip value from the difficulty's options and generates a sequence with 2-3 blanks.

**Features:**
- Difficulty selector with colored buttons (cyan/purple/coral/charcoal)
- Randomly generated sequences with random blank positions
- 7 numbers per sequence with 2-3 blanks
- 6 questions per round

---

### 15. Base 10 Blocks (`base10-blocks`)

Count base-10 blocks (hundreds, tens, ones) to identify the number shown. Uses isometric 3D SVG blocks.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"base10-blocks"` |
| `difficulty` | string | Yes | `"easy"`, `"medium"`, `"hard"` |

**Difficulty Options:**
- `easy` - Numbers 1-20 (ones and some tens)
- `medium` - Numbers 1-100 (tens and ones only)
- `hard` - Numbers 100-999 (hundreds, tens, and ones)

**Example Excel Row:**
```
template_type: base10-blocks
difficulty: medium
```

**Standalone Mode:**
The template generates a random number within the selected difficulty range and displays the corresponding blocks:
- **Ones**: Small orange cubes
- **Tens**: Red vertical rods (stacks of 10)
- **Hundreds**: Blue flat squares (10x10 grids, stacked isometrically)

Students count the blocks and type the total number. Different numbers are generated each time the activity is played.

**Features:**
- Isometric 3D SVG blocks generated programmatically
- Hundreds stack on top of each other with visual offset
- Tens wrap to multiple rows when needed
- Responsive layout: blocks on left, answer input on right
- Read aloud, help, and hint functionality

**Block Colours:**
- Ones: Orange `#FF8C00`
- Tens: Red `#B22222`
- Hundreds: Blue `#4169E1`

---

### 16. 3D Sphere (`sphere-3d`)

**Standalone Visual Effect** - Interactive 3D rotating sphere for showcasing topics!

A Three.js powered 3D sphere that can display images/content wrapped around it. Great for visual presentations of topics like "Animal Lifecycles", "World Geography", etc.

| Setting | Value | Description |
|---------|-------|-------------|
| Library | Three.js r128 | 3D rendering |
| Interaction | Drag to rotate | Touch and mouse support |
| Auto-rotate | Toggleable | Continuous slow rotation |

**Features:**
- Interactive drag-to-rotate with touch support
- Auto-rotate toggle button
- Reset view button
- Smooth rotation with inertia
- Decorative cloud elements
- Gradient sky background (peach → pink → lavender)
- Title card overlay with topic name

**Controls:**
- **Drag**: Rotate sphere manually
- **Auto-Rotate button**: Toggle continuous rotation
- **Reset View button**: Return to default position

**Customisation:**
```javascript
// Change auto-rotate speed (line ~177)
this.autoRotateSpeed = 1.0; // Higher = faster

// Change sphere texture - replace the image URL in the texture loader
```

**Use Cases:**
- Topic introduction screens
- Visual exploration of concepts
- Interactive world/globe displays
- Engaging visual transitions between activities

**Note:** This is a **visual effect** rather than a quiz question type. Use it for engagement and topic exploration.

---

### 17. Dice Addition (`dice-addition`)

**Standalone Speed Challenge** - Roll dice and add them up as fast as possible!

This template is **ready to use as-is** - no Excel import needed. Students select the number of dice (2-5) and complete 10 rounds as fast as they can.

| Setting | Value | Description |
|---------|-------|-------------|
| Dice count | 2-5 | Selected by student before starting |
| Rounds | 10 | Fixed challenge length |
| Wrong answer penalty | +5 seconds | Added to final time |
| Answer options | 4 | Multiple choice, randomised |

**Features:**
- 3D animated dice with realistic rolling physics
- Timer tracks total time including penalties
- Visual round progress dots
- Answer buttons appear on right side (desktop) or below (mobile)
- Final score shows time, correct count, and penalty count

**Customisation Options (in code):**

To change number of rounds:
```javascript
// Line ~950 - change 10 to desired number
if (currentRound >= 10) {
  endGame();
}
```

To change penalty time:
```javascript
// Line ~930 - change 5000 to desired ms
totalPenalty += 5000; // 5 seconds
```

To change available dice options:
```html
<!-- Line ~559 - modify dice-selector buttons -->
<div class="dice-selector">
  <button class="dice-option" data-count="2">2</button>
  <button class="dice-option selected" data-count="3">3</button>
  <button class="dice-option" data-count="4">4</button>
  <button class="dice-option" data-count="5">5</button>
</div>
```

**Note:** Unlike other templates, this is a **complete activity** rather than a data-driven question type. Use it directly for maths fluency practice.

---

### 18. Balloon Pop (`balloon-pop`)

Pop balloons to reveal letters and complete words. Great for phonics and digraph practice (sh, ch, th, wh, ph).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"balloon-pop"` |
| `word` | string | Yes | The complete word (e.g., "fish") |
| `blank_position` | string | Yes | `"start"`, `"middle"`, or `"end"` |
| `blank_letters` | string | Yes | The missing letters (e.g., "sh", "ch") |
| `display_word` | JSON array | Yes | Word split around blank: `["fi", "_"]` or `["_", "eep"]` |
| `options` | JSON array | Yes | Balloon choices: `["ch", "sh", "th"]` |
| `correct` | string | Yes | The correct option |
| `lottie` | string | No | Lottie animation filename for picture hint |
| `scale` | number | No | Lottie animation scale (default 1.0) |
| `sound_name` | string | No | The phonetic sound being practiced |
| `sound_description` | string | No | Description of the sound |
| `sound_examples` | string | No | Example words with this sound |
| `hint` | string | No | Hint text for the question |

**Example Excel Row:**
```
template_type: balloon-pop
word: ship
blank_position: start
blank_letters: sh
display_word: ["_", "ip"]
options: ["sh", "ch", "th", "wh"]
correct: sh
lottie: ship.json
sound_name: sh
sound_description: Shhh! Like a quiet whisper!
sound_examples: ship, shoe, shell
hint: This sound is like telling someone to be quiet: Shhh!
```

**Features:**
- Animated floating balloons with pop effect and confetti
- Phonics/digraph sound hints with Lottie picture support
- Audio read-aloud support (ElevenLabs Vonnie Voice)
- 6 questions per round
- Compass progress bar

**Current Questions (hardcoded):**
The demo includes 6 questions covering sh, ch, th, wh sounds:
- fish (sh at end)
- sheep (sh at start)
- chicken (ch at start)
- whale (wh at start)
- dolphin (ph in middle)
- birthday (th in middle)

---

## Recent Features (March 2025)

### Lottie Animations
Many templates use animated Lottie images for visual engagement.
- **Location:** `/lottie-assets/` (65+ JSON animation files)
- **Library:** `lottie-player` loaded from CDN
- **Templates using Lottie:** Word Match, Sound Select, Balloon Pop, Spelling, Drag & Drop

**Blazor Integration:**
```csharp
// Option 1: Use lottie-player web component via JS interop
// Option 2: Use a Blazor Lottie library like LottieSharp
```

### ElevenLabs Audio ("Vonnie Voice")
Professional voice audio replaces browser speech synthesis.
- **Location:** `/audio/{template-name}/` directories (17 directories)
- **Files per template:** question.mp3, hint.mp3, help.mp3, feedback-correct.mp3, feedback-incorrect.mp3
- **Total:** 125+ MP3 files across all templates
- **Generation:** `npm run generate-audio` (requires .env with ELEVENLABS_API_KEY)

**Audio File Structure:**
```
/audio/
├── balloon-pop/
│   ├── question.mp3
│   ├── hint-sh.mp3, hint-ch.mp3, hint-th.mp3...
│   ├── feedback-correct.mp3
│   └── feedback-incorrect.mp3
├── clock/
├── color-blocks/
├── ... (17 template directories)
```

### Color Cycling
Background color cycles through 4 colors on each "next question" action.
- **Colors:** Yellow (#FFE280) → Light Green (rgb(209,253,145)) → Pink (rgb(243,178,221)) → Cyan (rgb(178,235,242))
- **Script:** `/js/color-cycle.js`
- **Persistence:** sessionStorage (continues across page navigation)
- **Note:** Dice Addition does NOT use color cycling (excluded by design)

**Usage in templates:**
```javascript
// In <head>
<script src="js/color-cycle.js"></script>

// On page load
initColorCycle();

// In next question function
cycleColor();
```

### Progress Bar with Spinning Compass

**PRIORITY COMPONENT** - All templates include this animated progress bar. See `demo-progress-bar.html` for the complete working implementation.

**Features:**
- Gradient fill bar: Purple (#5E58F9) → Pink (#EFA1D5)
- Spinning compass diamond that follows progress
- Spins **faster** when progressing forward
- Spins **backwards** when going to previous question
- Returns to slow idle spin when stationary

**Colors:**
| Element | Value |
|---------|-------|
| Track | `#3a3a3a` (dark gray) |
| Fill start | `#5E58F9` (purple) |
| Fill end | `#EFA1D5` (pink) |
| Compass border | `#333` |
| Pink kite | `#EFA1D5` |
| Blue kite | `#5E58F9` |

**HTML Structure:**
```html
<div class="progress-container">
  <div class="progress-track">
    <div class="progress-fill" id="progress-fill"></div>
  </div>
  <div class="compass-container" id="compass-container">
    <div class="compass">
      <!-- Cardinal dots -->
      <div class="compass-dot top"></div>
      <div class="compass-dot bottom"></div>
      <div class="compass-dot left"></div>
      <div class="compass-dot right"></div>
      <!-- Spinning bowtie kites -->
      <div class="compass-diamond">
        <svg viewBox="0 0 28 8">
          <polygon points="0,4 10,0 14,4 10,8" fill="#EFA1D5" stroke="#333" stroke-width="0.5"/>
          <polygon points="28,4 18,0 14,4 18,8" fill="#5E58F9" stroke="#333" stroke-width="0.5"/>
        </svg>
      </div>
    </div>
  </div>
</div>
```

**JavaScript Implementation:**
```javascript
let currentQuestion = 1;
const totalQuestions = 8;

// Rotation state
let rotation = 0;
let spinSpeed = 120; // degrees per second (slow idle)
const slowSpeed = 120;
const fastSpeed = 720;
let lastTime = performance.now();
let slowDownTimer = null;

// Continuous spin loop
function spinCompass(currentTime) {
  const delta = (currentTime - lastTime) / 1000;
  lastTime = currentTime;

  rotation += spinSpeed * delta;
  rotation %= 360;

  const compassDiamond = document.querySelector('.compass-diamond');
  if (compassDiamond) {
    compassDiamond.style.transform = `rotate(${rotation}deg)`;
  }

  requestAnimationFrame(spinCompass);
}

// Start spinning on page load
requestAnimationFrame(spinCompass);

function updateProgress(animate = false, backwards = false) {
  const progressFill = document.getElementById('progress-fill');
  const compassContainer = document.getElementById('compass-container');

  // Calculate percentage
  const percentage = (currentQuestion / totalQuestions) * 100;

  // Speed up spin while moving (negative = backwards)
  if (animate) {
    if (slowDownTimer) clearTimeout(slowDownTimer);
    spinSpeed = backwards ? -fastSpeed : fastSpeed;
    slowDownTimer = setTimeout(() => {
      spinSpeed = slowSpeed;
    }, 500);
  }

  // Update fill and compass position
  progressFill.style.width = percentage + '%';
  compassContainer.style.left = percentage + '%';
}

function nextQuestion() {
  if (currentQuestion < totalQuestions) {
    currentQuestion++;
    updateProgress(true, false); // animate forward
  }
}

function prevQuestion() {
  if (currentQuestion > 1) {
    currentQuestion--;
    updateProgress(true, true); // animate backwards
  }
}
```

**CSS (key styles):**
```css
.progress-container {
  position: relative;
  width: 100%;
  height: 24px;
  margin: 40px 0;
}

.progress-track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 16px;
  background: #3a3a3a;
  border-radius: 8px;
  transform: translateY(-50%);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #5E58F9 0%, #EFA1D5 100%);
  border-radius: 8px;
  transition: width 0.5s ease-out;
}

.compass-container {
  position: absolute;
  top: 50%;
  left: 0%;
  transform: translate(-50%, -50%);
  transition: left 0.5s ease-out;
  z-index: 10;
}

.compass {
  width: 44px;
  height: 44px;
  background: white;
  border: 2px solid #333;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
```

**Blazor Integration:**
The spinning animation uses `requestAnimationFrame`. In Blazor, you can either:
1. Keep the JS animation via interop (recommended for smooth 60fps)
2. Use CSS animations with `@keyframes` for simpler implementation

**Full working demo:** `demo-progress-bar.html` - copy CSS/JS directly from this file.

### Difficulty Selection Screens
Templates with auto-generated questions have difficulty selectors on start:
- **Clock:** Hours Only, Half Hours, Quarters, 5 Minutes
- **Color Blocks:** Ones Only (1-9), Easy (10-50), Medium (51-99), Hard (100-999)
- **Base 10 Blocks:** Easy (1-20), Medium (1-100), Hard (100-999)
- **Fractions:** Halves, Quarters, Mixed, Eighths
- **Skip Counting:** Easy (1,2), Medium (3,5,10), Hard (4,6), Expert (7,8,9)

**Button Color Palette (2048-style):**
- Cyan: `#a7f0f5`
- Purple: `#d793fa`
- Coral: `#ee836b`
- Charcoal: `#3c3a32`

---

## Suggested Excel Import Structure

### Option A: Single Table (Simple)

One Excel sheet with all questions. Use `template_type` column to route to correct component.

| id | template_type | question_text | correct_answer | target_number | word | items | ... |
|----|---------------|---------------|----------------|---------------|------|-------|-----|
| 1 | color-blocks | Make 23 | | 23 | | | |
| 2 | spelling | Spell the word | | | dog | | |
| 3 | clock | Set the time | | | | | |

**Pros:** Simple, one file
**Cons:** Many empty columns, JSON in cells is awkward

### Option B: Multiple Sheets (Recommended)

One Excel file with separate sheets per template type:

- Sheet: `Clock` - columns specific to clock
- Sheet: `DragDrop` - columns specific to drag/drop
- Sheet: `ColorBlocks` - columns specific to colour blocks
- etc.

**Pros:** Clean columns per type, no empty cells
**Cons:** Multiple sheets to manage

### Option C: Database Tables (Most Flexible)

```
Questions (base table)
├── id
├── template_type
├── question_text
├── topic_id
├── difficulty
└── created_at

ClockData
├── question_id (FK)
├── target_hour
└── target_minute

DragDropData
├── question_id (FK)
├── items (JSON)
└── categories (JSON)

... etc for each type
```

**Pros:** Proper relational structure, easy to query and extend
**Cons:** More complex import process

---

## Blazor Integration Steps

### 1. Create Base Question Component

```csharp
public abstract class QuestionComponentBase : ComponentBase
{
    [Parameter] public QuestionModel Question { get; set; }
    [Parameter] public EventCallback<bool> OnAnswerSubmitted { get; set; }

    protected async Task SubmitAnswer(bool isCorrect)
    {
        await OnAnswerSubmitted.InvokeAsync(isCorrect);
    }
}
```

### 2. Create Type-Specific Components

```
/Components/Questions/
├── ClockQuestion.razor
├── DragDropQuestion.razor
├── ColorBlocksQuestion.razor
├── SpellingQuestion.razor
├── WordMatchQuestion.razor
├── NumberOrderQuestion.razor
├── SoundSelectQuestion.razor
├── LineMatchQuestion.razor
├── WordSortQuestion.razor
├── MissingLettersQuestion.razor
├── SpellingRulesQuestion.razor
├── PictureEquationsQuestion.razor
├── FractionsQuestion.razor
├── SkipCountingQuestion.razor
├── BalloonPopQuestion.razor
├── Base10BlocksQuestion.razor
└── DiceAdditionChallenge.razor
```

### 3. Dynamic Component Loader

```razor
@* QuestionRenderer.razor *@
@switch (Question.TemplateType)
{
    case "clock":
        <ClockQuestion Question="@Question" OnAnswerSubmitted="@HandleAnswer" />
        break;
    case "drag-drop":
        <DragDropQuestion Question="@Question" OnAnswerSubmitted="@HandleAnswer" />
        break;
    case "base10-blocks":
        <Base10BlocksQuestion Question="@Question" OnAnswerSubmitted="@HandleAnswer" />
        break;
    // ... etc
}
```

### 4. Excel Import Service

```csharp
public class QuestionImportService
{
    public async Task<List<QuestionModel>> ImportFromExcel(Stream excelFile)
    {
        var questions = new List<QuestionModel>();

        // Read Excel using EPPlus or similar
        // For each row:
        //   1. Read template_type
        //   2. Create appropriate QuestionModel subclass
        //   3. Map columns to properties
        //   4. Add to list

        return questions;
    }
}
```

---

## File Reference

### Quiz Templates (17)

| Demo File | Template Type | Data Source | Key Dependencies |
|-----------|---------------|-------------|------------------|
| `demo-clock.html` | `clock` | Auto-generated | `css/clock.css`, `js/clock.js` |
| `demo-drag-drop.html` | `drag-drop` | Hardcoded/Excel | `css/drag-drop.css`, `js/drag-drop.js` |
| `demo-color-blocks.html` | `color-blocks` | Auto-generated | `js/color-cycle.js` |
| `demo-spelling.html` | `spelling` | Hardcoded/Excel | `js/color-cycle.js`, Lottie |
| `demo-word-match.html` | `word-match` | Hardcoded/Excel | `js/color-cycle.js`, Lottie |
| `demo-number-order.html` | `number-order` | Auto-generated | `js/color-cycle.js`, Lottie |
| `demo-sound-select.html` | `sound-select` | Hardcoded/Excel | `js/color-cycle.js`, Lottie |
| `demo-line-match.html` | `line-match` | Hardcoded/Excel | `js/color-cycle.js` |
| `demo-word-sort.html` | `word-sort` | Hardcoded/Excel | `js/color-cycle.js` |
| `demo-missing-letters.html` | `missing-letters` | Hardcoded/Excel | `js/color-cycle.js` |
| `demo-spelling-rules.html` | `spelling-rules` | Hardcoded/Excel | `js/color-cycle.js` |
| `demo-picture-equations.html` | `picture-equations` | Hardcoded/Excel | `js/color-cycle.js` |
| `demo-fractions.html` | `fractions` | Auto-generated | `js/color-cycle.js` |
| `demo-skip-counting.html` | `skip-counting` | Auto-generated | `js/color-cycle.js` |
| `demo-balloon-pop.html` | `balloon-pop` | Hardcoded/Excel | `js/color-cycle.js`, Lottie |
| `demo-base10-blocks.html` | `base10-blocks` | Auto-generated | `js/color-cycle.js` |
| `demo-dice-addition.html` | `dice-addition` | Auto-generated | Standalone (no color cycle) |

### Visual Demos (5)

| Demo File | Purpose |
|-----------|---------|
| `demo-progress-bar.html` | Compass progress bar component demo |
| `demo-sphere-3d.html` | 3D rotating sphere (Three.js) |
| `demo-spinning-sphere.html` | Alternative sphere effect |
| `demo-dice-animation.html` | 3D dice animation demo |
| `demo-dice-embed.html` | Embeddable dice component |

### Shared Resources

| Directory | Contents |
|-----------|----------|
| `/css/` | base.css, clock.css, drag-drop.css |
| `/js/` | clock.js, drag-drop.js, color-cycle.js |
| `/audio/` | 17 subdirectories with 125+ MP3 files (ElevenLabs) |
| `/lottie-assets/` | 65+ JSON animation files |
| `/images/` | Static images and icons |

---

## Design System

All templates use consistent styling:

### Background Colors (4-Color Cycle)
| Color | Value | Used By |
|-------|-------|---------|
| Yellow | `#FFE280` | Default starting color |
| Light Green | `rgb(209, 253, 145)` | Cycle color 2 |
| Pink | `rgb(243, 178, 221)` | Cycle color 3 |
| Cyan | `rgb(178, 235, 242)` | Cycle color 4 |

### UI Elements
| Element | Value |
|---------|-------|
| Card background | `#FFFFFF` (or transparent for modern look) |
| Correct feedback | `#C8E6C9` (light green) |
| Incorrect feedback | `#FFCDD2` (light red/pink) |
| Primary button | `#333333` |
| Next button | `#4CAF50` (green, circular) |
| Try Again button | `#FF9800` (orange) |
| Border radius | `12px` (cards), `8px` (buttons) |
| Font | System fonts |

### Progress Bar
| Element | Value |
|---------|-------|
| Track | `#3a3a3a` (dark gray) |
| Fill gradient | `#5E58F9` → `#EFA1D5` (purple to pink) |
| Compass border | `#333333` |

---

## Standard Template Structure

Every template should include these elements for consistency:

### HTML Structure
```
├── Header
│   ├── Back button (onclick → index.html)
│   ├── User profile (avatar + progress bar)
│   └── Help button (id="header-help", wired to modal)
├── Question Meta
│   ├── Badge (class="badge badge-math" or "badge badge-english")
│   └── Progress text ("Question X of Y")
├── Question Title
│   ├── Read-aloud button
│   └── H1 with question text
├── Help Bar
│   ├── Read Aloud (id="btn-read-aloud")
│   ├── Get Help (id="btn-get-help")
│   └── Get Hint (id="btn-get-hint")
├── Help Modal (id="help-modal")
├── Hint Modal (id="hint-modal")
├── Main Content Area (template-specific)
├── Check Answer Button (class="btn-check-answer")
└── Feedback Section
    ├── Feedback badge (class="feedback-badge correct/incorrect")
    ├── Try Again button (class="btn-try-again", orange #FF9800)
    └── Next button (class="btn-next", green #4CAF50, circular)
```

### Button Colors
- **Check Answer**: Black `#333`
- **Try Again**: Orange `#FF9800`, hover `#F57C00`
- **Next**: Green `#4CAF50`, circular 48px, hover `#43A047`

### Badge Classes (in base.css)
- `.badge-math` - Blue #2196F3
- `.badge-english` - Pink #E91E63
- `.badge-science` - Green #4CAF50
- `.badge-art` - Orange #FF9800

### Background Colors by Subject
- Default (Math): Yellow `#FAE38E`
- English/Phonics: Pink `#F2ADE2`
- Some templates: Sky Blue `#87CEEB`

---

## Questions?

These templates demonstrate the **interaction patterns** and **visual design**. Victor will translate these into Blazor components that:

1. Accept question data as parameters
2. Handle user interactions
3. Report correct/incorrect back to the parent quiz system
4. Save results to the database

The HTML/CSS/JS in these demos can be adapted directly into Blazor's Razor syntax.
