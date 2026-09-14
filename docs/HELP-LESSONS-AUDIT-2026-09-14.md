# Help Lessons Audit — Portal Readiness (14 Sep 2026)

Rendered all 7 built lessons in a headless browser at 4 screen sizes (desktop 1440, tablet 768, phone portrait 390, phone landscape 844×390), stepped through scenes, checked console + network + source.

## Verdict: all 7 are FUNCTIONALLY GOOD but NONE are ship-ready yet
Same engine across all 7, so the same handful of issues repeat. All are correctness-clean and security-clean. The blockers are a debug artifact and small-screen (landscape/portrait) layout breakage. All fixable.

## Per-lesson scorecard

| Lesson | Debug panel | Desktop | Tablet | Phone portrait | Phone landscape | Verdict |
|---|---|---|---|---|---|---|
| Partitioning | ❌ present | ✅ | ✅ | ✅ (controls wrap) | 🔴 controls below fold | NEEDS-FIXES |
| Addition | ❌ present | ✅ (Your Turn tab clipped, scrolls) | ✅ | ✅ (controls wrap) | 🔴 controls below fold | NEEDS-FIXES |
| Subtraction | ❌ present | ✅ | ✅ | 🔴 Prev/Got-it clipped L/R | 🔴 controls below fold | NEEDS-FIXES |
| Counting | ❌ present | ✅ | ✅ | 🔴 Prev/Got-it clipped L/R | 🔴 controls below fold | NEEDS-FIXES |
| Ordinal Numbers | ❌ present | ✅ | ✅ | ⚠️ tab row overflows ~15px | 🔴 (same engine) | NEEDS-FIXES |
| Telling Time | ❌ present | ✅ | ✅ | ⚠️ tab row tight | 🔴 (same engine) | NEEDS-FIXES |
| Homophones | ✅ ABSENT | ✅ | ✅ | 🔴 word-pair card clipped (0 @media) | 🔴 fixed 380px stage cramped | NEEDS-FIXES |

## The issues, grouped

### 1. Debug panel — 🔴 SHIP BLOCKER (6 of 7 lessons)
A green "Scene: N | Time: Ns" readout is pinned bottom-right on the landing page AND inside the overlay, updating live. Present on all except Homophones. **Must be removed before Victor sees it.** Easy fix (delete `.debug-panel` element + CSS).

### 2. Phone landscape (844×390) broken — 🔴 ALL 7
The overlay is taller than the viewport. On most lessons there's no internal scroll, so the whole control bar (Prev / Pause / Replay / Next / Got it!) falls below the fold and is unreachable — a student in landscape can't navigate scenes or dismiss the lesson. Classroom tablets flip to landscape constantly, so this matters. Fix: give the modal `max-height` + internal scroll, and/or a compact landscape layout so controls stay on-screen.

### 3. Phone portrait control-bar clipping — 🔴 Subtraction, Counting
Their control bar overflows horizontally: "← Prev" cut off the left edge, "Got it!" cut off the right. (Addition/Partitioning wrap to two rows and survive.) Fix: `flex-wrap` the controls + shrink/wrap so they fit narrow widths.

### 4. Homophones small-screen — 🔴 (worst; 0 breakpoints)
- `.word-pair` (intro "blue vs blew") is `flex` with NO `flex-wrap` → the 2nd word card clips off inside an `overflow:hidden` stage on phone portrait.
- `.stage { height: 380px }` fixed → cramped/overflows in landscape.
- `.controls` (6 buttons, no wrap) overflow on ~360px devices (iPhone SE).
- Fix: add flex-wrap, make stage height responsive, add a mobile breakpoint.

### 5. Assets not inlined — 🟡 portal-deploy item (all 7, expected)
Each lesson loads over the network (same-origin only, no third-party/trackers): 3 woff2 fonts, `assets/videos/teacher-transparent.webm`, and the scene MP3s. On GitHub Pages this resolves fine. For Victor's portal these relative `../../` paths must be rewritten to CDN/blob URLs (or inlined). Victor's integration doc already anticipates this.

### 6. Cosmetic
- `favicon.ico` 404 on every lesson (harmless).
- Occasional tab/debug-counter desync during autoplay (goes away once debug panel removed).

## Security: ✅ CLEAN (go for portal)
- Fully self-authored, inline CSS/JS, **zero third-party references** (no CDN, analytics, trackers).
- No user input → no XSS/injection surface.
- Victor's doc: "No CSP or iframe restrictions exist that would block this." His constraint was "no external dependencies," not "no JavaScript" — these meet it.

## Correctness: ✅ WORKING
Audio loads (all scene MP3s HTTP 206), scene tabs switch scenes, completed tabs turn green, no JS errors. No broken scenes observed.

## Fix list before handing to Victor
1. Remove `.debug-panel` from all 6 lessons that have it.
2. Fix phone-landscape overlay (max-height + internal scroll / compact controls) — all 7.
3. Fix phone-portrait control-bar wrap — Subtraction, Counting (+ verify others).
4. Homophones mobile pass — flex-wrap word-pair, responsive stage height, wrap controls.
5. (At upload) rewrite relative asset paths to Victor's CDN/blob URLs, or inline.
6. (Optional) add a favicon to kill the 404.

Then re-render all 7 at the 4 sizes to confirm green before shipping.
