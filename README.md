# Quiz Templates

Frontend templates for interactive quiz questions - ready for developer integration into Blazor.

## Quick Start

```bash
open index.html
```

## What's Here

| Demo | Description |
|------|-------------|
| Balloon Pop | Pop balloons with correct answers |
| Base 10 Blocks | Place value with hundreds, tens, ones |
| Clock | Rotate hands to set time |
| Color Blocks | Color in blocks to represent numbers |
| Dice Addition | Speed challenge adding dice totals |
| Drag & Drop | Sort items into categories |
| Fractions | Interactive fraction questions |
| Line Matching | Connect items between columns |
| Missing Letters | Fill in missing letters in words |
| Number Order | Arrange numbers in order |
| Picture Equations | Solve equations with images |
| Progress Bar | Animated progress bar with spinning compass |
| Skip Counting | Count by 2s, 5s, 10s etc |
| Sound Select | Listen and select correct answer |
| Spelling | Join letters to spell words |
| Spelling Rules | Apply spelling rules |
| Word Match | Match words to definitions/images |
| Word Sort | Sort words into categories |
| Written Answer | Text input with correct/incorrect feedback |

## Auto-Generated Templates (No Excel Import Needed!)

These templates generate random questions automatically - just select difficulty and play:

| Template | Questions | Difficulty Options |
|----------|-----------|-------------------|
| Base 10 Blocks | 5 per round | Easy (1-20), Medium (1-100), Hard (100-999) |
| Clock | 4 per round | Hours Only, Half Hours, Quarters, 5 Minutes |
| Color Blocks | 10 per round | Ones Only (1-9), Easy (10-50), Medium (51-99), Hard (100-999) |
| Dice Addition | 10 per round | 2-5 dice (speed challenge) |
| Fractions | 8 per round | Halves, Quarters, Mixed, Eighths |
| Skip Counting | 6 per round | Easy (1,2), Medium (3,5,10), Hard (4,6), Expert (7,8,9) |

## For Developer

See `DOCUMENTATION.md` for full integration guide.

**TL;DR:**
1. CSS files work directly in Blazor
2. HTML structure maps 1:1 to Razor components
3. JavaScript shows the interaction logic to implement

## Recent Updates

**March 2025 (Latest):**
- **Lottie Animations** - Word Match and Sound Select now use animated Lottie images
- **Professional Voice Audio** - ElevenLabs "Vonnie Voice" replaces browser speech synthesis
- **New Hint System** - Word Match highlights the specific image needing help (no blocking overlay)
- **Improved Mobile UX** - Larger touch targets on clock hands for easier grabbing
- **Cleaner UI** - Removed white containers from picture-equations template

**Word Match Template Features:**
- 24 animated animal/object images across 4 pages
- Drag words to match images
- Pre-generated MP3 audio for all hints, feedback, and instructions
- Inline hint highlighting: shows exactly which image needs help
- Full Lottie animation support with configurable scaling

**Audio Generation:**
```bash
npm install
npm run generate-audio  # Requires .env with ElevenLabs API key
```

**Earlier March 2025:**
- Added spinning compass progress bar to ALL templates
- Added difficulty start screens to: Clock, Skip Counting, Color Blocks, Base 10 Blocks, Fractions
- Colored difficulty buttons (cyan/purple/coral/charcoal) for consistent UX
- Skip Counting: Easy (1,2), Medium (3,5,10), Hard (4,6), Expert (7,8,9)
- Color Blocks: Ones Only (1-9), Easy (10-30), Medium (31-60), Hard (61-99)
- Removed white containers from game areas for cleaner look
- 3D isometric SVG blocks in Base 10 Blocks AND Color Blocks
- Color Blocks now auto-generates 10 questions per round (no Excel needed!)

**February 2025:**
- Updated yellow background color to #FFE280 across templates
- Removed transparent white bars from headers
- Added progress bar component with spinning compass
- Added 2048 game color palette to clock difficulty buttons
