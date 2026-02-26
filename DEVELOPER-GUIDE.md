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

Student drags clock hands to show a time.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"clock"` |
| `question_text` | string | Yes | e.g., "Show half past 2" |
| `target_hour` | integer | Yes | Hour (1-12) |
| `target_minute` | integer | Yes | Minute (0, 15, 30, 45 for young kids) |

**Example Excel Row:**
```
template_type: clock
question_text: Show half past 3
target_hour: 3
target_minute: 30
```

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

Click blocks to colour tens and ones to make a number.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `template_type` | string | Yes | `"color-blocks"` |
| `question_text` | string | Yes | e.g., "Make the number 23" |
| `target_number` | integer | Yes | Number to make (1-99) |
| `tens_color` | string | No | Hex color for tens (default: #FF6B6B) |
| `ones_color` | string | No | Hex color for ones (default: #4ECDC4) |

**Example Excel Row:**
```
template_type: color-blocks
question_text: Colour the blocks to make 45
target_number: 45
```

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
└── SoundSelectQuestion.razor
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

## Questions?

These templates demonstrate the **interaction patterns** and **visual design**. Victor will translate these into Blazor components that:

1. Accept question data as parameters
2. Handle user interactions
3. Report correct/incorrect back to the parent quiz system
4. Save results to the database

The HTML/CSS/JS in these demos can be adapted directly into Blazor's Razor syntax.
