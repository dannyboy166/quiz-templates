# Quiz Question Templates - Documentation

## Overview

This project contains reusable HTML/CSS/JavaScript templates for interactive quiz questions. These templates are designed to be handed off to a developer for integration into a Blazor WebAssembly education platform.

---

## The Problem

Our developer is building a quiz/education portal using Blazor WebAssembly (.NET). He has limited time and bandwidth to work on both the backend logic AND the frontend design/animations for every question type.

**Challenge:** The quiz system needs multiple interactive question formats:
- Written answers
- Draggable clock hands (set the time)
- Drag-and-drop sorting (shapes into categories)
- Line matching (connect related items)

Building all of these from scratch in Blazor takes significant time.

---

## The Solution

**Split the work:**

1. **This project** = Frontend templates (HTML, CSS, JavaScript)
   - All the visual design
   - Animations and interactions
   - Look and feel matching the existing design system

2. **Developer's work** = Integration into Blazor
   - Convert HTML to Razor components
   - Wire up database queries
   - Handle scoring/progress logic

The developer can take these templates and translate them 1:1 into Blazor components. The CSS works identically, and the JavaScript logic shows exactly how interactions should work.

---

## Design System

All templates match the existing developer design. Key colors:

| Element | Color Code | Usage |
|---------|------------|-------|
| `#FAE38E` | Golden yellow | Page background |
| `#FFFFFF` | White | Content cards |
| `#000000` | Black | Primary buttons, text |
| `#C8E6C9` | Light green | Correct answer background |
| `#66BB6A` | Green | Correct answer border |
| `#FFCDD2` | Light red/pink | Incorrect answer background |
| `#E57373` | Coral red | Incorrect answer border |
| `#2196F3` | Blue | Next button, selections |

---

## File Structure

```
quiz-templates/
├── index.html              # Demo hub - links to all templates
├── DOCUMENTATION.md        # This file
│
├── css/
│   ├── base.css           # Core styles, layout, buttons, feedback
│   ├── clock.css          # Draggable clock component styles
│   └── drag-drop.css      # Drag & drop component styles
│
├── js/
│   ├── clock.js           # DraggableClock class
│   └── drag-drop.js       # DragDropZone class
│
├── demo-written-answer.html   # Text input question demo
├── demo-clock.html            # Draggable clock demo
├── demo-drag-drop.html        # Shapes into jars demo
├── demo-matching.html         # Line matching demo
│
├── images/                 # Reference screenshots (add here)
│   └── (add developer screenshots for reference)
│
└── components/             # (reserved for future components)
```

---

## Question Types Included

### 1. Written Answer (`demo-written-answer.html`)
- Student types answer in text box
- Shows correct (green) or incorrect (red) feedback
- Displays the correct answer if wrong

**Key elements:**
- `.answer-input` - The text input field
- `.answer-input.correct` / `.answer-input.incorrect` - Feedback states
- `.feedback-badge` - Shows result message

---

### 2. Draggable Clock (`demo-clock.html`)
- SVG clock with draggable hour hand (minute hand optional)
- Student rotates hands to set the time
- Supports snapping to hours or 5-minute intervals

**JavaScript class:** `DraggableClock`

```javascript
const clock = new DraggableClock('#container', {
  size: 200,
  interactive: true,
  showMinuteHand: false,
  snapToHour: true,
  initialHour: 12,
  onChange: (time) => console.log(time)
});

// Check answer
clock.checkAnswer(3, 0); // Returns true if set to 3 o'clock
```

---

### 3. Drag & Drop Sorting (`demo-drag-drop.html`)
- Draggable items (shapes, numbers, images, text)
- Drop zones (jars, boxes, categories)
- Works on desktop and mobile/touch

**JavaScript class:** `DragDropZone`

```javascript
const sorter = new DragDropZone('#container', {
  correctAnswers: {
    'triangle': '3',    // triangle goes in 3-sides zone
    'square': '4',      // square goes in 4-sides zone
  },
  onDrop: (itemId, zoneId) => console.log(`Dropped ${itemId} in ${zoneId}`)
});

// Check answers
const result = sorter.checkAnswers();
// Returns { results: {...}, allCorrect: true/false }
```

---

### 4. Line Matching (`demo-matching.html`)
- Two columns of items
- Click dots to draw connecting lines
- Validates correct matches

**Implementation:** Uses click-to-match (click left dot, then right dot to connect). Lines drawn with SVG.

---

## How to Preview

1. Open `index.html` in any browser
2. Click on any demo to see it in action
3. Try the interactions (drag, click, type)
4. Click "Check Answer" to see feedback states

---

## For the Developer - Integration Guide

### Step 1: Review the demos
Open each HTML file and understand the structure.

### Step 2: Copy the CSS
The CSS files can be used almost directly. Import into your Blazor project:
- `base.css` - Required for all question types
- `clock.css` - Only if using clock questions
- `drag-drop.css` - Only if using drag/drop questions

### Step 3: Convert HTML to Razor
The HTML structure maps directly to Razor components. Example:

**HTML:**
```html
<div class="question-title">
  <h1>How many blocks are there?</h1>
</div>
```

**Razor:**
```razor
<div class="question-title">
  <h1>@Question.Text</h1>
</div>
```

### Step 4: Implement JavaScript logic in C#/Blazor
The JavaScript classes show the logic needed:
- Clock rotation math
- Drag/drop state management
- Answer validation

These can be implemented as:
- Blazor C# code-behind
- JavaScript interop if needed for complex interactions

---

## Adding New Question Types

To add a new question type:

1. Create a new CSS file in `/css/` if needed
2. Create a new demo HTML file
3. Add JavaScript class in `/js/` if interactive
4. Update this documentation
5. Add link in `index.html`

---

## Reference Images

Add screenshots from the existing portal to `/images/` folder for reference:
- `images/developer-design.png` - Current design from developer
- `images/clock-question.png` - Clock matching example
- `images/drag-drop-example.png` - Shapes sorting example

---

## Questions / Contact

If the developer has questions about any component, they can:
1. Review the demo HTML for structure
2. Check the CSS for styling details
3. Read the JavaScript for interaction logic

The JavaScript comments explain the key methods and their purpose.

---

## Version History

| Date | Changes |
|------|---------|
| Feb 2025 | Initial creation - 4 question types |

