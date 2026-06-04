# Conceptual Math: Teaching the "Why"

## The Problem

Australian students are declining in mathematics. PISA rankings have dropped consistently over 20+ years. But the issue isn't that students can't follow procedures - it's that they don't understand *why* those procedures work.

### What We're Seeing

1. **Calculator dependence** - Students can't do basic arithmetic without a calculator because they never understood the underlying logic
2. **BODMAS confusion** - Order of operations is memorised as arbitrary rules, not understood as logical necessity
3. **Formula memorisation** - Students memorise formulas without understanding what they represent, then can't apply them to real problems
4. **No transfer** - Knowledge doesn't transfer to new contexts because it was never truly understood

### The Root Cause

Students are taught **procedural knowledge** (how to do it) without **conceptual knowledge** (why it works).

| Procedural | Conceptual |
|------------|------------|
| "Cross multiply to solve proportions" | "Proportions are equivalent ratios - we're finding what keeps the relationship balanced" |
| "BODMAS: Brackets, Order, Division, Multiplication, Addition, Subtraction" | "We need an agreed order because 2 + 3 × 4 could mean two different things" |
| "Area = length × width" | "We're counting how many unit squares fit inside" |
| "To add fractions, find a common denominator" | "We can only add parts that are the same size" |

The student who memorises procedures might pass tests. But when they encounter a new problem that requires applying the concept, they're lost - because they never had the concept in the first place.

---

## The Theory

**Math is logical. It's not arbitrary rules to memorise - it's patterns that make sense.**

For some students, this is intuitive. They see the pattern, understand why it works, and everything clicks. They don't need to study because they're not memorising - they're understanding.

The question: **Can this intuitive understanding be taught?**

Research says yes. Countries that emphasise conceptual understanding (Japan, Singapore, Finland) consistently outperform countries that drill procedures (USA, UK, Australia). The difference isn't intelligence - it's pedagogy.

### The Goal

Build interactive experiences that create "aha" moments - where students *discover* why math works, rather than being told what to do.

---

## The Approach: Discovery Learning

Instead of:
> "Here's the rule. Now practice it."

We do:
> "Here's a puzzle. Figure out what makes sense."

### Key Principles

1. **Start with the problem, not the solution**
   - Present a scenario that requires the concept
   - Let students struggle (productively) before revealing patterns
   - The answer should feel obvious in hindsight

2. **Make the invisible visible**
   - Use visual manipulatives to show what numbers represent
   - Animate processes so students see what's happening
   - Connect abstract symbols to concrete meaning

3. **Ask "why" constantly**
   - "Why do you think that worked?"
   - "What would happen if...?"
   - "Can you find another way?"

4. **Build from intuition**
   - Start with what students already understand
   - Connect new concepts to existing knowledge
   - Make the logic explicit

5. **Fail forward**
   - Wrong answers are data, not failures
   - Show why the wrong answer doesn't work
   - Let students see the consequences of different approaches

---

## Implemented Templates

### 1. ✅ "Why BODMAS?" Discovery

**Status:** IMPLEMENTED - `demo-why-bodmas.html`

**The Problem:** Students memorise BODMAS but don't know why it exists.

**The Experience (6 phases):**
1. **The Problem** - Show `2 + 3 × 4`, let students argue between 14 and 20
2. **Without Rules** - Show that different orders give chaos - same expression, different answers
3. **Why Multiplication First** - Visual: 3 groups of 4 apples plus 2 more. Groups must be counted first!
4. **Practice** - Solve expressions step-by-step with visual feedback
5. **More Practice** - Division/subtraction examples
6. **The Insight** - BODMAS isn't arbitrary - it's a logical agreement based on how grouping works

**Key Insight:** Multiplication represents "groups of" - you need to know what's IN the groups before you can add them to other things.

**Outcome:** Students understand BODMAS as a sensible agreement, not an arbitrary rule.

---

## Template Ideas (Not Yet Implemented)

### "What IS a Fraction?" Discovery

**The Problem:** Students manipulate fractions without understanding what they represent.

**The Experience:**
- Start with a pizza. Show 1/2 and 2/4 visually.
- Ask: "Are these the same?" (Obviously yes - same amount of pizza)
- But the numbers look different (1/2 vs 2/4). Why are they equal?
- Lead to discovery: fractions represent a *relationship* between parts and wholes
- 2/4 means "2 parts out of 4" - which is the same proportion as "1 part out of 2"
- Show this with different shapes, different numbers of pieces
- Let them discover equivalent fractions by seeing the pattern

**Outcome:** Students understand fractions as relationships, not just numbers.

---

### "Why Does Multiplication Work?" Discovery

**The Problem:** Students can multiply but don't understand what multiplication IS.

**The Experience:**
- Show 3 groups of 4 objects
- Ask: "How many total? How did you count?"
- Some will add: 4 + 4 + 4 = 12
- Show that 3 × 4 is just a faster way to write this
- Multiplication is REPEATED ADDITION - a shortcut
- This is why 3 × 4 = 4 × 3 (commutative property) - show visually with arrays
- This is why multiplication comes before addition in BODMAS - you're resolving the groups first

**Outcome:** Students understand multiplication as a concept, not just a procedure.

---

### "Why Does Area Work?" Discovery

**The Problem:** Students use A = L × W without understanding why.

**The Experience:**
- Show a 3 × 4 rectangle
- Fill it with unit squares (grid)
- Ask: "How many squares?"
- They count: 12
- Show them: 3 rows of 4 squares each
- That's 3 × 4 = 12
- Area = Length × Width because we're counting the unit squares
- Extend to irregular shapes - how would you find this area?

**Outcome:** Area formula is logical, not memorised.

---

### "Number Sense" - Mental Math Discovery

**The Problem:** Students can't do mental math because they don't see number relationships.

**The Experience:**
- "What's 47 + 38?"
- Don't teach a method - let them explore
- Show multiple strategies visually:
  - 47 + 38 = 47 + 40 - 2 = 87 - 2 = 85 (round up, adjust)
  - 47 + 38 = 50 + 35 = 85 (shift between numbers)
  - 47 + 38 = 40 + 30 + 7 + 8 = 70 + 15 = 85 (place value split)
- All valid. All logical. Pick what makes sense to you.
- Numbers are flexible - you can break them apart and recombine

**Outcome:** Students develop number sense and mental strategies.

---

## How This Differs From Current Templates

| Current Templates | Conceptual Templates |
|-------------------|---------------------|
| Practice a skill | Discover a concept |
| One right answer | Multiple valid approaches |
| Immediate feedback | Guided exploration |
| Speed/fluency focus | Understanding focus |
| "Do this procedure" | "Why does this work?" |

**Current templates are still valuable** - students need practice and fluency. But they assume the concept is already understood. The conceptual templates come FIRST - they build the foundation.

---

## Implementation Notes

### Technical Approach

These templates need different mechanics than drill templates:

1. **Branching narratives** - Different paths based on student responses
2. **Visual manipulatives** - Drag, combine, split numbers/objects
3. **Guided discovery** - Socratic questioning with hints
4. **Multiple representations** - Show the same concept different ways
5. **Reflection prompts** - "Why do you think that worked?"

### Difficulty Progression

1. **Concrete** - Physical manipulatives (visual objects)
2. **Pictorial** - Drawings and diagrams
3. **Abstract** - Symbols and numbers only

Students should progress through all three stages for each concept.

### Assessment

Don't just check if the answer is right. Check if the understanding is there:
- "Explain in your own words..."
- "Show another way to solve this..."
- "What would happen if...?"

---

## Research Backing

- **Stigler & Hiebert (1999)** - "The Teaching Gap" - Japanese math teaching emphasises problem-solving and discovery
- **Boaler, J. (2015)** - "Mathematical Mindsets" - Growth mindset and visual mathematics
- **CPA Approach** (Singapore Math) - Concrete-Pictorial-Abstract progression
- **Inquiry-Based Learning** - Students construct knowledge through exploration
- **Productive Struggle** - Difficulty before explanation leads to deeper learning

---

## Next Steps

1. ✅ Build "Balance the Equation" - DONE
2. ✅ Build "Why BODMAS?" - DONE
3. Test with real students
4. Iterate based on what creates genuine understanding
5. Build remaining templates (Fractions, Multiplication, Area, Number Sense)
6. Add Vonnie voice audio files

---

## The Vision

A student who goes through these templates doesn't just know HOW to do math. They know WHY it works. When they encounter a new problem:

- They don't panic looking for a formula
- They think: "What makes sense here?"
- They can reason through it logically
- They can explain their thinking

This is what mathematical fluency actually looks like. Not speed at procedures - but genuine understanding that transfers to any context.

---

*Last updated: April 2026*
