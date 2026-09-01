# WorldWise Upload Options — Complete Reference

**Every choice we can make when bulk-uploading a question**, pulled straight from Victor's
DevTest DB + student templates (verified 31 Aug 2026). This is the "what are ALL the options"
map so we never reverse-engineer it again.

Source of truth: `DevTest.QuestionTemplate`, `DevTest.TemplateElement`, `DevTest.ReferenceData`,
and `WW/WWAppStudent/.../Templates/*.razor` + `BaseQuestionTemplate.cs` +
`WWDbConfig/SQLScripts/StoredProcs/GetQuestionHint.sql`.

---

## 1. Question Types (`QuestionTemplate.QuestionTemplateID`)

| ID | Name | Component | Behaviour |
|----|------|-----------|-----------|
| 1 | **Select One** | QTG_AS1_O4T_01 | Single choice from multiple options. **Renders the question image.** |
| 2 | **Select All** | QTG_AS_CHK_01 | Select all that apply. ⚠️ **Does NOT render the question image** — it's an image-grid of the *options*. |
| 3 | **True/False** | QTG_ATF_01 | No options — True/False buttons. Don't load SelectionOptions. |
| 4 | **Written** | QTG_AKN_01 | Free-text answer; multiple accepted/partial answers possible. |
| 5 | **Sort** | QTG_SORT_01 | Options are boxes the student re-arranges. |
| 6 | **Link** | QTG_LINK_01 | Two sets of boxes; student connects them. |

Spreadsheet friendly names → ID map (in `import_questions.py` QUESTION_TYPE_MAP):
Select One→1, Select All→2, True/False→3, Written→4, Sort→5, Link→6.

---

## 2. Status Codes (`ReferenceData` CodeTypeCD=2) — the "StatusCD" on every table

| CD | Name | Meaning |
|----|------|---------|
| 3 | **Pending** | Waiting for approval before use. **Victor's default for bulk loads.** |
| 4 | **Active** | Live and good to use. (Blobs must be 4 to serve.) |
| 5 | Cancelled | Never approved. |
| 6 | Deactivated | No longer used for new events. |
| 7 | Deleted | Logically deleted; hidden from reports. |

---

## 3. Blob Types (`ReferenceData` CodeTypeCD=109) — `Blob.BlobTypeCD`

| CD | Name | Use |
|----|------|-----|
| 110 | Image | SVG/PNG question + option images |
| 111 | Audio | MP3 voice-overs (question + hint) |
| 112 | Video | MP4/WebM |

---

## 4. Template Elements — the FULL menu a hint can target

Element types (`ReferenceData` CodeTypeCD=117, = `TemplateElement.ElementTypeCD`):
- **118 = TEXT** (htmltxt) — HTML text field
- **119 = AUDIO** (Audele) — playable sound
- **120 = VISUAL** (VisEle) — image/video

Every element has `IsHintReplaceable` (can a hint target it?) and `TemplateSectionName`
(Question / Option / Hint). **All the elements below are hint-replaceable.**

### Elements present on ALL templates (the 6 core)
| Element (`HTMLElementID`) | Type | Section | What it is / what happens if a hint targets it |
|---|---|---|---|
| `question-text-content` | TEXT | Question | The main question text. **Hint text here REPLACES the question text.** |
| `question-image` | VISUAL | Question | Main question image. Hint can swap it for a hint image. |
| `question-audio` | AUDIO | Question | Audio played alongside the question (image-hover speaker = `AudioBlobID`). |
| `question-reader` | AUDIO | Question | Human voice reading the question (text speaker = `ReaderBlobID`). |
| `hint-graphic` | VISUAL | Hint | "A small graphic shown as a hint **beside** the question text." Empty until a hint fills it. |
| `hint-graphic-audio` | AUDIO | Hint | **"An audio clip played from the hint graphic speaker."** The hint VOICE-OVER. Companion to `hint-graphic`. |

### Extra elements on **Select One** only (has 10 total)
`option-1-text`, `option-3-text`, `option-4-text` (TEXT, section Option), `option-1-image` (VISUAL).
(Note: option-2 text isn't a listed element for Select One in DevTest — quirk of the seed data.)

### Per-template element counts
- **Select One:** 10 (the 6 core + option-1/3/4-text + option-1-image)
- **Select All, True/False, Written, Sort, Link:** 6 (the core set) each

---

## 5. HINTS — how each behaviour is chosen at upload (THE KEY SECTION)

A hint **Level** (1/2/3) is a set of **Block Replacements**. Each replacement is one
`HintReplacement` row: `QuestionID + HintLevelNum + TemplateName + HTMLElementID` + either
`HintHTML` (text) **or** `BlobID` (media). **We pick the behaviour by choosing which
`HTMLElementID` the row targets.** Text and media are mutually exclusive per row.

### How the student app resolves a hint (verified in code)
- Stored proc `GetQuestionHint` returns **ALL** HintReplacement rows for that Q+level.
  **It does NOT filter by StatusCD** — so deactivating a row does NOT hide it. ⚠️
- The gate is the parent **`QuestionHint`** row (INNER JOIN): no QuestionHint row for a level → no replacements returned for that level.
- Client (`BaseQuestionTemplate.cs`) keys replacements by `HTMLElementID`. For a given element:
  - Text: `GetHintHtmlForElement(el)` returns the hint text **only if `HintHTML` is non-empty**, else falls through to the original.
  - Blob: `GetHintBlobForElement(el)` returns the hint blob if present.

### The behaviours we can choose (per hint level)

| Desired behaviour | Target element | Set | Result |
|---|---|---|---|
| **Replace question text with a hint** | `question-text-content` | `HintHTML`=text, `BlobID`=NULL | Question text is swapped for the hint wording. |
| **Audio-only hint (Zoe's choice)** ✅ | `hint-graphic-audio` | `BlobID`=audio, `HintHTML`='' | Question text STAYS; hint voice-over plays. |
| **Show a hint picture beside the question** | `hint-graphic` | `BlobID`=image | A small graphic appears beside the question. |
| **Swap the read-aloud voice for a hint reader** | `question-reader` | `BlobID`=audio | Question reader audio becomes a hint reader. |
| **Replace an option's text/image** | `option-N-text` / `option-N-image` | text or blob | That option is swapped (rarely what you want for a general hint). |

⚠️ **There is NO "hint text shown ALONGSIDE the question" element.** Text hints only
*replace* their target. To show readable hint text without hiding the question, Victor would
need to add a new element. So "audio-only" is the way to keep the question visible with a hint today.

### To turn an existing text-replace hint into audio-only (Zoe's request)
- **Do NOT delete** (CLAUDE.md). Instead **blank `HintHTML`=''** on the `question-text-content`
  row. The client then shows the original question text (falls through the IsNullOrEmpty check).
- Keep the `hint-graphic-audio` row as-is (that's the voice-over).
- Fully reversible: snapshot the original `HintHTML` first; restore to undo.
- Script: `scripts/bulk_import/set_hints_audio_only.py` (revert-capable).

---

## 6. What `import_questions.py` / `ingest_voiceovers.py` set (quick recap)

- **Question:** TextHTML, Title (≤80 chars), TemplateID, StatusCD=3, PlayAudioOnRenderFlag,
  ImageBlobID (auto-linked by `{ItemID}-question` blob), IsNumericOnlyAnswer=0.
- **Voice-over (ingest):** Blob (111/'audio'/StatusCD4), then Question.ReaderBlobID + AudioBlobID, PlayAudioOnRenderFlag=1.
- **Hint audio (ingest):** new HintReplacement row on `hint-graphic-audio`, HintHTML='', BlobID set. Never touches the text-hint row.
- **SelectionOption:** skipped entirely for True/False.

See `docs/BULK-UPLOAD-FINDINGS-2026-08.md` for the gotchas (leading-zero CDN filenames, Select All hidden image, etc.).

---

## 7. Where to look next time
- **Question types:** `SELECT * FROM DevTest.QuestionTemplate`
- **Hint targets / element menu:** `SELECT * FROM DevTest.TemplateElement WHERE TemplateName='<type>'`
- **Any code meaning (status/blob/element type):** `SELECT * FROM DevTest.ReferenceData WHERE CodeTypeCD IN (2,109,117)`
- **How a hint renders to students:** `WW/WWAppStudent/.../Templates/Template{1..6}.razor` + `BaseQuestionTemplate.cs` (`GetHintHtmlForElement`/`GetHintBlobForElement`/`ApplyHintReplacements`)
- **How hints are fetched:** `WWDbConfig/SQLScripts/StoredProcs/GetQuestionHint.sql` (no StatusCD filter!)
