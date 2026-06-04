# Help Lessons - Conceptual Teaching for Year 1-2 Maths

This document maps out the "Help" button content for WorldWise. Each Help lesson teaches the **underlying concept** (the "why"), not just how to solve a specific question.

## How Help Lessons Work

- **Hint** = helps with the specific question they're stuck on
- **Help** = teaches the whole concept (applies to many questions)

Each Help lesson:
- 60-90 seconds max
- Teacher character voiceover (ElevenLabs)
- Animated visuals that show the concept
- Ends with a simple summary

## Technical Implementation

### File Structure
```
audio/
  help-addition.mp3          # Voiceover audio
  help-subtraction.mp3
  transcripts/
    help-addition.json       # ElevenLabs word-level timestamps
    help-subtraction.json
scripts/
  help-addition.md           # Script for recording
  help-subtraction.md
  help-place-value.md
demo-help-test.html          # Addition prototype (working)
demo-help-subtraction.html   # Subtraction prototype (in progress)
```

### How It Works
1. Write script with visual cues (`scripts/help-*.md`)
2. Record voiceover with ElevenLabs
3. Export JSON transcript with word-level timestamps
4. Build HTML page with synced animations using timestamps
5. Animation timeline triggers visuals at exact moments in audio

### Animation Pattern
- **Intro title** appears (e.g., "What is Adding?")
- **Concrete objects** appear and animate (apples, cookies)
- **Objects combine/transform** to show the concept
- **Equation appears** showing numbers + objects side by side
- **Highlights sync** with voiceover explanations
- **Summary** reinforces the key idea

---

## Help Topic 1: Counting & Number Sense

**Applies to:** Number ordering, sequences, skip counting, what comes next

**The Concept:** Numbers represent quantities. Each number is one more than before.

**The "Why":** Numbers aren't just symbols - they represent *how many* of something.

**Question types this covers:**
- Count the objects
- What comes next?
- Skip counting (2s, 5s, 10s)
- Order numbers smallest to biggest
- Fill in the missing number

---

## Help Topic 2: Place Value

**Applies to:** Tens and ones, hundreds tens ones, base-10 blocks, expanded form

**The Concept:** Our number system groups by 10. The position of a digit tells us its value.

**The "Why":** We bundle into tens because it's easier to count. The 4 in 45 means 4 tens, not 4 ones.

**Question types this covers:**
- How many tens and ones?
- Base-10 block counting
- What is the value of the 5 in 52?
- Partition numbers (45 = 40 + 5)
- Expanded form

---

## Help Topic 3: Addition

**Applies to:** All addition questions

**The Concept:** Combining two groups to find the total.

**The "Why":** Addition is putting things together and counting how many altogether.

**Question types this covers:**
- 3 + 5 = ?
- Picture addition
- Word problems (Sam has 3, gets 2 more)
- Missing addend (3 + ? = 7)
- Dice/dot addition

---

## Help Topic 4: Subtraction

**Applies to:** All subtraction questions

**The Concept:** Finding what's left when we take away, OR finding the difference.

**The "Why":** Subtraction is the opposite of addition. It can mean "take away" OR "how many more?"

**Question types this covers:**
- 8 - 3 = ?
- Picture subtraction
- Word problems (had 7, ate 2)
- Comparison (how many more?)
- Missing number (10 - ? = 6)

---

## Help Topic 5: Multiplication (Groups Of)

**Applies to:** Groups of, arrays, repeated addition

**The Concept:** Multiplication is counting equal groups.

**The "Why":** 3 × 4 means "3 groups of 4" - it's faster than adding 4 + 4 + 4.

**Question types this covers:**
- How many altogether? (groups)
- 3 groups of 2 = ?
- Arrays (rows and columns)
- Skip counting patterns

---

## Help Topic 6: Division (Sharing)

**Applies to:** Equal sharing, grouping

**The Concept:** Splitting into equal groups OR finding how many groups.

**The "Why":** Division is fair sharing. "12 ÷ 3" means share 12 among 3 people equally.

**Question types this covers:**
- Share 12 cookies among 4 kids
- How many groups of 2 in 10?
- Picture sharing problems

---

## Help Topic 7: Fractions

**Applies to:** Halves, quarters, eighths, parts of shapes/groups

**The Concept:** Parts of a whole. EQUAL parts.

**The "Why":** A fraction tells us how many EQUAL parts. If they're not equal, it's not a real fraction.

**Question types this covers:**
- Colour half/quarter of this shape
- What fraction is shaded?
- Share equally between 2/4 people
- Which shows quarters?
- Half of 8 apples

---

## Help Topic 8: Money

**Applies to:** Coin recognition, counting money, making amounts

**The Concept:** Coins have values. We combine them to make amounts.

**The "Why":** The SIZE of a coin doesn't tell you its value. You have to learn what each is worth.

**Question types this covers:**
- Which coin is worth more?
- Count these coins
- Make 50c using different coins
- How much altogether?

---

## Help Topic 9: Time (Clocks)

**Applies to:** Reading analogue clocks, o'clock, half past, quarter past/to

**The Concept:** Two hands show hours and minutes. They move at different speeds.

**The "Why":** Short hand = hours (slow), Long hand = minutes (fast). O'clock = long hand at 12.

**Question types this covers:**
- What time is shown?
- Draw hands for 3 o'clock
- Half past / quarter past
- What time will it be in 1 hour?

---

## Help Topic 10: Time (Calendars)

**Applies to:** Days, weeks, months, seasons

**The Concept:** Days, weeks, months organize time in repeating patterns.

**The "Why":** Time follows patterns. After Sunday comes Monday. The months go in a circle.

**Question types this covers:**
- What day comes after Tuesday?
- How many days until...?
- Which month comes next?
- What season is July?

---

## Help Topic 11: 2D Shapes

**Applies to:** Shape recognition, properties, sorting

**The Concept:** Shapes have features - sides and corners.

**The "Why":** We name shapes by their features. A triangle ALWAYS has 3 sides, no matter its size or rotation.

**Question types this covers:**
- Name this shape
- How many sides?
- Find all the triangles
- Sort by features

---

## Help Topic 12: 3D Objects

**Applies to:** Solid shapes, faces, edges, real-world objects

**The Concept:** 3D objects have faces, edges, and corners. They take up space.

**The "Why":** 2D is flat (paper). 3D is chunky (you can hold it). A cube's faces are squares.

**Question types this covers:**
- Name this object
- How many faces?
- Which will roll?
- Find 3D objects in real life

---

## Help Topic 13: Patterns

**Applies to:** Repeating patterns, growing patterns, number patterns

**The Concept:** Patterns repeat in predictable ways. Find the rule, predict what's next.

**The "Why":** If you understand the rule, you can always figure out what comes next.

**Question types this covers:**
- What comes next?
- Complete the pattern
- Find the mistake
- Growing patterns (1, 3, 5, 7...)

---

## Help Topic 14: Data & Graphs

**Applies to:** Picture graphs, tally marks, collecting data

**The Concept:** We collect information and show it visually to understand it better.

**The "Why":** Graphs make it easy to compare. One picture = one thing.

**Question types this covers:**
- Read the graph
- Which has most/least?
- Make a tally
- Complete the picture graph

---

## Priority Order for Building

Build these first (most questions, biggest impact):

1. **Addition** - DONE (demo-help-test.html)
2. **Subtraction** - IN PROGRESS (audio ready, building demo)
3. **Place Value** - script ready (scripts/help-place-value.md)
4. **Counting** - foundational
5. **Fractions** - conceptually tricky, big payoff

Then:
6. Multiplication
7. Division
8. Money
9. Time (Clocks)
10. Shapes (2D)
11. Patterns
12. Time (Calendars)
13. 3D Objects
14. Data & Graphs
