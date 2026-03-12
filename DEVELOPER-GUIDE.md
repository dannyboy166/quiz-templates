# Quiz Templates - Developer Integration Guide

## Overview

These templates are **UI/UX prototypes** demonstrating interactive question types for the education portal. Victor will need to:

1. Recreate these as **Blazor components**
2. Set up **Excel import** with a `template_type` column
3. Map Excel columns to each template's required data fields

---

## Template Types & Required Data Fields

### 1. Written Answer (`written-answer`)

Simple text input where student types an answer.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"written-answer"` |
| `question_text` | string | Yes | The question to display |
| `correct_answer` | string | Yes | Expected answer (case-insensitive match) |
| `hint` | string | No | Optional hint text |
| `image_url` | string | No | Optional image to show with question |

**Example Excel Row:**
```
template_type: written-answer
question_text: What is 5 + 3?
correct_answer: 8
hint: Count on your fingers!
```

---

### 2. Draggable Clock (`clock`)

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

### 3. Drag & Drop Sorting (`drag-drop`)

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

### 4. Colour the Blocks (`color-blocks`)

Click blocks to colour tens and ones to make a number. Supports difficulty-based random generation.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"color-blocks"` |
| `question_text` | string | No | Auto-generated: "Colour the blocks to make [number]" |
| `difficulty` | string | Yes | `"ones-only"`, `"easy"`, `"medium"`, `"hard"` |
| `tens_color` | string | No | Hex color for tens (default: #5C6BC0) |
| `ones_color` | string | No | Hex color for ones (default: #90CAF9) |

**Difficulty Options:**
- `ones-only` - Numbers 1-9 (single digits, no tens columns)
- `easy` - Numbers 10-30
- `medium` - Numbers 31-60
- `hard` - Numbers 61-99

**Example Excel Row:**
```
template_type: color-blocks
difficulty: easy
```

**Standalone Mode:**
The template generates a random target number within the selected difficulty range. The block grid automatically adjusts to provide enough tens columns and ones blocks for the target number. Different numbers are generated each time the activity is played.

---

### 5. Spelling Letters (`spelling`)

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

### 6. Word Match (`word-match`)

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

### 7. Number Order (`number-order`)

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

### 8. Sound Select (`sound-select`)

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

### 9. Line Match (`line-match`)

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

### 10. Word Sort (`word-sort`)

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

### 11. Missing Letters (`missing-letters`)

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

### 12. Spelling Rules (`spelling-rules`)

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

### 13. Picture Equations (`picture-equations`)

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

### 14. Fractions (`fractions`)

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

### 15. Skip Counting (`skip-counting`)

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

### 16. Base 10 Blocks (`base10-blocks`)

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

## Suggested Excel Import Structure

### Option A: Single Table (Simple)

One Excel sheet with all questions. Use `template_type` column to route to correct component.

| id | template_type | question_text | correct_answer | target_number | word | items | ... |
|----|---------------|---------------|----------------|---------------|------|-------|-----|
| 1 | written-answer | What is 2+2? | 4 | | | | |
| 2 | color-blocks | Make 23 | | 23 | | | |
| 3 | spelling | Spell the word | | | dog | | |

**Pros:** Simple, one file
**Cons:** Many empty columns, JSON in cells is awkward

### Option B: Multiple Sheets (Recommended)

One Excel file with separate sheets per template type:

- Sheet: `WrittenAnswer` - columns specific to written answer
- Sheet: `Clock` - columns specific to clock
- Sheet: `DragDrop` - columns specific to drag/drop
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

WrittenAnswerData
├── question_id (FK)
├── correct_answer
└── hint

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
├── WrittenAnswerQuestion.razor
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
    case "written-answer":
        <WrittenAnswerQuestion Question="@Question" OnAnswerSubmitted="@HandleAnswer" />
        break;
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

| Demo File | Template Type | Key CSS/JS |
|-----------|---------------|------------|
| `demo-written-answer.html` | `written-answer` | `css/base.css` |
| `demo-clock.html` | `clock` | `css/clock.css`, `js/clock.js` |
| `demo-drag-drop.html` | `drag-drop` | `css/drag-drop.css`, `js/drag-drop.js` |
| `demo-color-blocks.html` | `color-blocks` | Inline styles |
| `demo-spelling.html` | `spelling` | Inline styles |
| `demo-word-match.html` | `word-match` | Inline styles |
| `demo-number-order.html` | `number-order` | Inline styles |
| `demo-sound-select.html` | `sound-select` | Inline styles |
| `demo-line-match.html` | `line-match` | Inline styles |
| `demo-word-sort.html` | `word-sort` | Inline styles |
| `demo-missing-letters.html` | `missing-letters` | Inline styles |
| `demo-spelling-rules.html` | `spelling-rules` | Inline styles |
| `demo-picture-equations.html` | `picture-equations` | Inline styles |
| `demo-fractions.html` | `fractions` | Inline styles |
| `demo-skip-counting.html` | `skip-counting` | Inline styles |
| `demo-balloon-pop.html` | `balloon-pop` | Inline styles |
| `demo-base10-blocks.html` | `base10-blocks` | Inline styles |
| `demo-dice-addition.html` | `dice-addition` | Inline styles (standalone) |

---

## Design System

All templates use consistent styling:

| Element | Value |
|---------|-------|
| Background (default) | `#FAE38E` (yellow) |
| Background (spelling) | `#F2ADE2` (pink) |
| Background (word-match) | `#87CEEB` (sky blue) |
| Card background | `#FFFFFF` |
| Correct feedback | `#C8E6C9` (green) |
| Incorrect feedback | `#FFCDD2` (red/pink) |
| Primary button | `#000000` |
| Border radius | `12px` (cards), `8px` (buttons) |
| Font | System fonts |

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
