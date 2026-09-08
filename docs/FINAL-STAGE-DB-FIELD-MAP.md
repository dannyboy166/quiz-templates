# Final Stage — Complete DB Field/Column Map (verified from Victor's codebase)

Authoritative map of **everything** that makes up one WorldWise question, so our "Final Stage"
dev-app tab can cover every setting/option Victor's DB expects and our bulk upload goes in with
no wrong columns/lines.

Sources (audited 8 Sep 2026, read-only, from `/Users/danielsamus/WW/`):
- `WWApp/Components/Pages/Question/QuestionStudio.razor` (+ `.razor.cs`) — the authoring UI + save.
- `WWApp/Components/Shared/BlobPicker.razor`, `BlobUploader.razor` — blob select/create.
- `WWApp/Components/Pages/Question/QuestionPreviewContent.razor` — preview renderer.
- `WWDbConfig/SQLScripts/SeedData.sql`, `AddQuestionMediaTemplateElements.sql`,
  `AddHintGraphicTemplateElements.sql` — QuestionTemplate + TemplateElement seed rows.

Related: `docs/QUESTION-STUDIO-FULL-SPEC.md`, `docs/FINAL-REVIEW-TAB-PROPOSAL.md`, CLAUDE.md.

---

## 1. Question type ↔ TemplateID ↔ TemplateTypeCD (VERIFIED)

`QuestionTemplate` seed rows (SeedData.sql) — **TemplateID matches our CLAUDE.md exactly**:

| TemplateID | TemplateName | ComponentName | QuestionType CD (studio dropdown, `ReferenceData.CD`) |
|---|---|---|---|
| 1 | Select One | QTG_AS1_O4T_01 | 31 |
| 2 | Select All | QTG_AS_CHK_01 | 33 |
| 3 | True/False | QTG_ATF_01 | 34 |
| 4 | Written | QTG_AKN_01 | 32 |
| 5 | Sort | QTG_SORT_01 | 115 |
| 6 | Link | QTG_LINK_01 | 116 |

**CRITICAL:** the studio dropdown value is the **QuestionType CD** (31/32/33/34/115/116), which is
NOT the TemplateID (1–6). Template is auto-narrowed from the type via `TemplateTypeCD`. Keep BOTH
mappings straight. Our content uses only 4 types (Select One, Select All, True/False, Written);
Sort & Link are 0 in our content.

---

## 2. TemplateElement seed rows — the media model (VERIFIED)

"Media" is not a card; it's the **Template Elements table**. Each element is a row in
`TemplateElement` keyed by `(TemplateName, HTMLElementID)`, and `MapElementToQuestionField` maps it
to a Question column. Every one of the 6 templates has this ladder:

| HTMLElementID | Maps to (Question column) | Notes |
|---|---|---|
| `question-text-content` | `Question.TextHTML` | the question text |
| `question-image` | `Question.ImageBlobID` | "Question Graphic" — image or video |
| `question-audio` | `Question.AudioBlobID` | audio clip alongside question (hover-to-play on image) |
| `question-reader` | `Question.ReaderBlobID` | **human voice reading the question** (our ElevenLabs VO) |
| `hint-graphic` | (populated by HintReplacement.BlobID) | small graphic shown as a hint |
| `hint-graphic-audio` | (populated by HintReplacement.BlobID) | **audio-only hint** — our hint VO target |

- `question-*` elements ARE question fields. `hint-*` elements are NOT — they're populated only by
  `HintReplacement` rows targeting that element.
- **This is exactly our current recipe:** question VO → `ReaderBlobID` (via `question-reader`);
  hint VO → `HintReplacement.BlobID` on the `hint-graphic-audio` row (audio-only, no text replace).

---

## 3. Per-OPTION media — per-option VO IS fully supported (VERIFIED)

The option editor exposes THREE blob pickers per selection option, each select+clear+inline preview:

| SelectionOption column | Studio picker | BLOBTYP |
|---|---|---|
| `SelectionOption.ImageBlobID` | "Select Image" (`OpenBlobPickerForOption(n,"Image",IMAGE)`) | 110 Image |
| `SelectionOption.AudioBlobID` | "Select Audio" (`...,"Audio",AUDIO)`) | 111 Audio |
| `SelectionOption.ReaderBlobID` | "Reader (Audio)" (`...,"Reader",AUDIO)`) | 111 Audio |

**=> Per-option voice-over is a first-class field in Victor's schema (`SelectionOption.ReaderBlobID`).**
Building "generate a VO per option" is legitimate; the target column already exists. (Distinction:
`AudioBlobID` = a sound played with the option; `ReaderBlobID` = a voice reading the option text.
For "read each option aloud", **`ReaderBlobID`** is the right target — same role as question-reader.)

Per-option descriptor is **Text OR Image (mutually exclusive)**; Audio/Reader always optional. Each
option can also have its own `HintHTML` (hidden for Link). No per-option `ScorePct`/`TeacherNotes`
input in the UI — correctness comes from the Correct-Answer control.

---

## 4. Full save path — tables written, in order (from `.razor.cs` audit + our scripts)

Studio save is plain EF Core (`SaveQuestionAsync`, no stored proc). Insert order:
1. **Question** — TemplateID, TextHTML, Title, ImageBlobID, AudioBlobID, ReaderBlobID, ColorSchemeID,
   CorrectAnswerText, TeacherNotes, HelpBlobID/HelpSceneName, IncorrectTFHintHTML (T/F),
   PlayAudioOnRenderFlag, StatusCD (**default Pending=3; Active forced to Pending unless permitted**).
2. **QuestionClassification** — TopicID, AcademicLevelID, DifficultyLevelNum.
3. **SelectionOption** (StatusCD Active=4) — OptionNum, TextHTML/ImageBlobID, AudioBlobID, ReaderBlobID,
   HintHTML, ScorePct, SortOrderNum. Skipped for True/False.
4. **OptionGroup** (Link only) — SOURCE/TARGET groups + rules.
5. **WrittenAnswerOption** (Written only) — CompareText, ScorePct, HintHTML.
6. **QuestionHint** + **HintReplacement** — per level; replacement targets an element via
   TemplateName/HTMLElementID + either HintHTML (text) or BlobID (media), mutually exclusive.

StatusCD reference (verified): 3=Pending, 4=Active, 5=Cancelled, 6=Deactivated, 7=Deleted.

---

## 5. Blob model + BlobPicker/BlobUploader (VERIFIED — corrects a prior assumption)

- A blob is referenced everywhere by integer **`BlobID`** (FK). No URL stored — URL is computed from
  `Path` + `Filename` + `FileTypeExtn` via `ICdnUrlService.GetAssetUrl(relativePath)`.
- **BlobPicker both selects AND creates.** Default = select an existing ACTIVE blob (filtered by
  `BlobTypeCD`). "Add New" → **BlobUploader** creates a new Blob row.
- **BlobUploader** sets: BlobTypeCD (SVG/JSON forced to 110 Image), Name (≤30), Title (≤1000),
  Description (≤1000, our alt text), Filename (≤50), FileTypeExtn (≤10), Path (per-type folder
  `images`/`audio`/`video`/`misc`), **StatusCD PENDING(3) → ACTIVE(4) only after a Microsoft
  Defender malware scan returns Clean** (malicious files deleted). SVG/Lottie sanitized. Size limits:
  image 10 MB, audio 50 MB, video 200 MB. Stored filename = `{BlobID:D8}-{sanitized-basename}`.
- **Blob types:** 110 Image, 111 Audio, 112 Video, 122 Help/Animation parent.

**Implication for us:** our scripts already INSERT Blob rows directly (bypassing the UI uploader), so
we skip Defender. That's fine for our controlled pipeline, but any blob we insert must set the same
columns the UI would (esp. correct BlobTypeCD, Path, FileTypeExtn, StatusCD=4).

---

## 6. Preview renderer

- Route: `/Question/PreviewContent/{questionID:int}` — renders the REAL student template components.
- Unsaved edits reach it out-of-band via in-memory `QuestionPreviewCacheService` (per-session
  `cacheKey`), with display options as query params + a `refresh` counter.
- To embed a faithful preview we'd iframe this (needs WWApp URL + auth — a Victor ask). Otherwise we
  render our own approximation from the demo-*.html templates.

---

## 7. Validation gates (studio's own "ready")

- **Save enabled** when: `hasUnsavedChanges` AND `GetSaveValidationErrors()` empty. Requires Topic +
  Difficulty + Color Scheme + a specified Correct Answer + field validation.
- **Preview enabled** when all **mandatory template elements configured** (`AllMandatoryElementsConfigured`).
- Our Final Stage "100% complete" = UNION of this gate + our media gate (§3 of the proposal:
  every question needs an image; VO present + links to audio blob; every hint level voiced; hints
  audio-only; Select All needs an image on every option).

---

## 8. Columns Victor's OWN studio does NOT expose (so we must decide policy)

Rendered nowhere in the current QuestionStudio UI (but exist as Question columns):
- `AnswerMinLengthNum`, `AnswerMaxLengthNum`, `IsNumericOnlyAnswer` (Written) — set via script if needed.
- `PlayAudioOnRenderFlag` — commented out in UI; our `ingest_voiceovers.py` sets it =1. Keep doing so.
- Per-option `ScorePct` / `TeacherNotes` — no UI; ScorePct derived from correct-answer selection.

---

## 9. Bottom line for the build
- Every part of your "generate everything in one place" ask maps to a real DB column. Nothing is
  missing on Victor's side — including **per-option voice-over** (`SelectionOption.ReaderBlobID`).
- Our existing scripts already write the question/hint/image/VO columns correctly. The NEW gaps are:
  (a) a per-option VO **engine + state + UI + ingest link to `SelectionOption.ReaderBlobID`**, and
  (b) a per-question assembly view + "Generate Complete Question" orchestration.
- DB writes stay terminal-only (deployed app has no azure/pyodbc) → Final Stage "Approve" is a
  staging/approved-state action; the bulk upload remains Dan's verified terminal step.
