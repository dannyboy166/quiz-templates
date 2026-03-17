# Vonnie Voice Audio Rollout Plan

## Goal
Add ElevenLabs "Vonnie Voice" audio to ALL quiz templates, replacing browser speechSynthesis.

## Voice Details
- Voice ID: `cupfa8uelkW7cWxLMRa7`
- API Key: stored in `.env` (not committed)

## What Each Template Needs
1. **Question audio** - "Read Aloud" button plays the question
2. **Hint audio** - Each hint has corresponding audio
3. **Feedback audio** - Correct/incorrect/completion messages
4. **Help audio** - Optional help modal audio

## Process Per Template
1. Read template, identify all text needing audio
2. Add entries to `scripts/generate-audio.js`
3. Run `npm run generate-audio` to generate MP3s
4. Update template JS to use `new Audio()` instead of `speechSynthesis`
5. Test and commit

---

## Progress Tracker

### COMPLETED
- [x] **demo-word-match.html** - 29 audio files (question, 24 hints, feedback, help)
- [x] **demo-base10-blocks.html** - 8 audio files (question, 3 place-value hints, feedback, help)
- [x] **demo-balloon-pop.html** - 11 audio files (question, 6 word hints, feedback, help)
- [x] **demo-clock.html** - 12 audio files (question, difficulty intros, hints, feedback, help)
- [x] **demo-color-blocks.html** - 8 audio files (question, place-value hints, feedback, help)
- [x] **demo-dice-addition.html** - 5 audio files (question, feedback, ready)

### IN PROGRESS
- [ ] **demo-fractions.html**

### TODO (Quiz Templates)
- [ ] demo-drag-drop.html
- [ ] demo-fractions.html
- [ ] demo-line-match.html
- [ ] demo-missing-letters.html
- [ ] demo-number-order.html
- [ ] demo-picture-equations.html
- [ ] demo-skip-counting.html
- [ ] demo-sound-select.html
- [ ] demo-spelling-rules.html
- [ ] demo-spelling.html
- [ ] demo-word-sort.html

### NOT APPLICABLE (Visual/Component Demos)
- demo-dice-animation.html (animation demo only)
- demo-dice-embed.html (embed demo only)
- demo-progress-bar.html (UI component only)
- demo-sphere-3d.html (visual effect only)
- demo-spinning-sphere.html (visual effect only)

---

## Audio File Structure
```
audio/
├── word-match/
│   ├── question.mp3
│   ├── hint-dog.mp3
│   ├── hint-cat.mp3
│   └── ...
├── base10-blocks/
│   ├── question.mp3
│   ├── hint-hundreds.mp3
│   └── ...
└── [template-name]/
    └── ...
```

## Notes
- Keep hints as-is if they're already working well
- Focus on audio replacement, not hint redesign
- Test on mobile after each template
