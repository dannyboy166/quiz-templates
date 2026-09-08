# QuestionStudio — Full Question Spec (every setting, field & parameter)

**Purpose:** the authoritative, no-gaps map of everything that makes up a question in
Victor's WorldWise DB. Built by reading Victor's actual source (7 Sep 2026), cross-checked
from three angles:
1. **UI** — `WWApp/Components/Pages/Question/QuestionStudio.razor` (+ `.razor.cs`) — what a reviewer sets.
2. **DB** — `WWDbConfig/Models/*.cs` + `Migrations/WWDBContextModelSnapshot.cs` — what the DB requires.
3. **Runtime** — `WWAppStudent/.../Templates/Template1-6.razor` + stored procs — what the portal reads to render & score.

Use this as the spec for the future "one screen → straight into DB" app. If a field isn't here, it doesn't exist.

---

## 0. The 6 question types (three numbering systems — keep them straight!)

| Template<br>(razor) | TemplateID<br>(Question.TemplateID) | QuestionType CD<br>(TemplateTypeCD) | Portal name | ComponentName |
|---|---|---|---|---|
| Template1 | **1** | **31** ChooseOnly1 | Select One | QTG_AS1_O4T_01 |
| Template2 | **2** | **33** ChooseAtLeast1 | Select All | QTG_AS_CHK_01 |
| Template3 | **3** | **34** TrueFalse | True/False | QTG_ATF_01 |
| Template4 | **4** | **32** WrittenAnswer | Written | QTG_AKN_01 |
| Template5 | **5** | **115** Sortquest | Sort | QTG_SORT_01 |
| Template6 | **6** | **116** Linkquest | Link | QTG_LINK_01 |

⚠️ **Written is type 32 but TemplateID 4 / Template4** — the number order is NOT 1-2-3-4-5-6 = the CD order.
`Question` has **no question-type column**; type is derived via `TemplateID → QuestionTemplate.TemplateTypeCD`.

---

## 1. Reference codes (all live in ReferenceData, seeded in SeedData.sql)

**StatusCD:** 3=Pending · 4=Active · 5=Cancelled · 6=Deactivated · 7=Deleted (also 113=Finished, 114=Waiting, 158=Complete — used elsewhere).
**BlobTypeCD:** 110=Image · 111=Audio · 112=Video · 122=Multi-Scene Animation (help/EdContent).
**ElementTypeCD (family 117):** 118=HTML Text · 119=Audio · 120=Image/Video.
**ColorSchemeID:** 1=Yellow(default) · 2=Green · 3=Blue · 4=Pink.
**DifficultyLevelNum:** raw 0–9 (0 trivial, 1–3 easy, 4–6 medium, 7–9 hard). UI offers 1–9.

---

## 2. MUST-SET-ON-INSERT (non-nullable, no DB default) — the fields that make an INSERT fail if missing

### Question
- `TextHTML` (varchar max, **Required**)
- `Title` (varchar 1000, **Required**) ← we historically set this to truncated question text
- `TemplateID` (required FK)
- **`PlayAudioOnRenderFlag`** (bit, **NO default** — must pass true/false explicitly)
- **`IsNumericOnlyAnswer`** (bit, **NO default** — must pass true/false explicitly)
- `CreatedUserID`, `LastModUserID` (required FKs → SystemUser; DevTest = 8)
- ⚠️ `CreatedTime`/`LastModTime` default to **NULL** (NOT getdate()) on Question — set them ourselves.
- `StatusCD` defaults 4 (Active) if omitted — we deliberately set 3 (Pending) for review.

### SelectionOption (PK = QuestionID + OptionNum)
- `QuestionID`, `OptionNum` (tinyint)
- **`ScorePct`** (decimal 7,6, **NO default**) — 0–1 normalized; supports part marks & negatives.
- `LastModUserID` (required FK)
- `StatusCD` defaults 4 (must be 4 to be visible/scored). `TextHTML` nullable. `CreatedTime`/`LastModTime` default getdate().

### QuestionHint (PK = QuestionID + HintLevelNum)
- `QuestionID`, `HintLevelNum`, `CreatedUserID`, `LastModUserID`.

### HintReplacement (PK = QuestionID + HintLevelNum + TemplateName + HTMLElementID)
- All 4 PK cols. `TemplateName`+`HTMLElementID` **must match an existing TemplateElement row**.
- `CreatedUserID`, `LastModUserID`.
- ⚠️ **Business rule: exactly ONE of `HintHTML` / `BlobID` is non-null.** (Not DB-enforced — WE enforce it.)

### QuestionClassification
- `QuestionID`, `TopicID` (required FKs), `DifficultyLevelNum` (byte, **NO default**).

### Blob
- `BlobTypeCD` (NO default), `HasVttFile` (bit, NO default), `CreatedUserID`, `LastModUserID`. StatusCD defaults 4.

---

## 3. What EACH question type needs to SCORE correctly (from stored procs — FormAnswerResponse.sql)

The scoring key is almost always **`Question.CorrectAnswerText`** (nvarchar 200), encoded differently per type:

| Type | CorrectAnswerText encoding | Also needs | Wrong-answer hint source |
|---|---|---|---|
| **Select One** (31) | the winning `OptionNum` (e.g. `"2"`) — OR set the correct option's `ScorePct ≥ ~1.0` | ≥1 SelectionOption (StatusCD=4) | `SelectionOption.HintHTML` |
| **Select All** (33) | comma list of correct OptionNums (`"1,3"`) — OR correct options' `ScorePct` sum ≈ 1.0 | ≥1 SelectionOption (StatusCD=4) | per-option `HintHTML` |
| **True/False** (34) | **exactly `"True"` or `"False"`** — the ONLY key | SelectionOptions optional (UI synthesizes buttons) | **`Question.IncorrectTFHintHTML`** |
| **Written** (32) | (returned = top CompareText) | **≥1 `WrittenAnswerOption` (StatusCD=4)** with `CompareText` (LIKE pattern), `ScorePct`. **Case-sensitive** match. No WAO → always scores 0 | `WrittenAnswerOption.HintHTML` |
| **Sort** (115) | comma OptionNums in correct order (`"3,1,2,4"`) — exact string match | ≥1 SelectionOption (StatusCD=4) | — |
| **Link** (116) | correct `"source-target"` pairs (`"1-3,2-4"`) — set comparison | SelectionOptions with **`OptionGroup` GroupName = "SOURCE"/"TARGET"** | — |

⚠️ **SelectionOption / WrittenAnswerOption with StatusCD ≠ 4 are INVISIBLE and UNCOUNTED.** Always 4.

---

## 4. What each template RENDERS (from Template1-6.razor)

| Template | Renders question image? | Renders option images? | Notes |
|---|---|---|---|
| T1 Select One | **YES** | YES | full media |
| T2 Select All | **NO** | YES | ⚠️ no question-image block — a Q-picture won't show; put it on options |
| T3 True/False | **YES** | YES | |
| T4 Written | **YES** | n/a (no options) | reads AnswerMin/MaxLengthNum, IsNumericOnlyAnswer |
| T5 Sort | **NO** | YES | renders sortable items only |
| T6 Link | **NO** | YES | renders SOURCE/TARGET items; needs OptionGroups |

**All templates** read the stem from `TextHTML`, read-aloud audio from `ReaderBlobID` (ReaderJson),
question hover/on-render audio from `AudioBlobID` (AudioJson), per-option audio from `SelectionOption.AudioBlobID`.
Audio helpers require `BlobID > 0` AND a non-empty resolved URL. Lottie = any image blob with `FileTypeExtn == "json"`.

---

## 5. Hints — how replacement vs audio-only works (the thing Zoe cares about)

- A hint = one `QuestionHint` row (per level) + one or more `HintReplacement` rows (per target element).
- Each `HintReplacement` targets a `HTMLElementID` and carries **either** `HintHTML` (text) **or** `BlobID` (media), never both.
- **Stem is replaced ONLY if** a replacement on `question-text-content` has **non-empty HintHTML** (`GetHintHtmlForElement` returns null when empty). → **Audio-only hint = leave HintHTML empty/blank on the text element, put the audio on a `hint-graphic-audio` element.** ✅ This is Zoe's "just a voiceover, don't replace text."
- Target element IDs the templates recognize: `question-text-content` (text), `question-image`, `question-audio`, `question-reader`/`question-reader-audio`, `option-{N}-image`, `option-{N}-text`, `hint-graphic`, `hint-graphic-audio`. Plus per-option virtual elements (created on save).
- ⚠️ `GetQuestionHint.sql` does **not** filter hint rows by StatusCD (but availability count in GetNextQuestion uses StatusCD=4 and caps at session HintsAllowedNum).

---

## 6. Full UI field inventory (QuestionStudio) — grouped, with DB mapping

### Basic Information
| UI field | DB column | Required | Notes |
|---|---|---|---|
| Question Type | → TemplateID via TemplateTypeCD | Yes | **locked after creation** (can't change type on edit) |
| Title | Question.Title | **Yes** | short teacher/admin description |
| Color Scheme | Question.ColorSchemeID | **Yes (UI-enforced)** | 1–4 |
| Teacher Notes | Question.TeacherNotes | No | |
| Help content | Question.HelpBlobID (+ HelpSceneName) | No | blob ref, not a URL. Topic EdContent or any asset. .zip upload supported |
| Hint for Incorrect (T/F) | Question.IncorrectTFHintHTML | No | **True/False only** |

### Question Configuration
| UI field | DB column | Notes |
|---|---|---|
| Template | Question.TemplateID | filtered to the chosen type; auto-picks if only one |
| Status | Question.StatusCD | **ACTIVE only settable by admins**; non-admin save forced to PENDING; new defaults PENDING |
| Template Elements table | TextHTML / ImageBlobID / AudioBlobID / ReaderBlobID | this is how question text/image/audio/reader are set (no separate Media card) |

### Options (Select One / All / Sort / Link)
Per option (`SelectionOption`): descriptor mode **Text XOR Image** (the other is nulled), TextHTML, ImageBlobID,
AudioBlobID, ReaderBlobID, HintHTML (hidden for Link), GroupName (Link only: SOURCE/TARGET).
`ScorePct` set to 0 on add and **derived from the correct-answer marking** (radio/checkbox/reorder/link-builder) → written into `CorrectAnswerText`.
Option image filename doubles as WCAG alt-text.

### Written Answer Options (Written only)
Table of `WrittenAnswerOption`: CompareText (wildcard, max 50), Score% (0–100 → stored 0–1), HintHTML. Highest score = correct.

### Classification
Topic (→ QuestionClassification.TopicID; display = "SubjectArea - Topic"), Difficulty (1–9 → DifficultyLevelNum).
**No separate Subject/Area dropdown** (implied by Topic). **Academic Level not collected** (derived from Topic).

### Connection Rules (Link only)
Per group (SOURCE/TARGET): ItemsMustHaveMatch (OptionGroup.ItemsMustHaveMatch), ItemsCanHaveMultipleMatches.

### Preview Settings (NOT persisted — session simulation only)
Session name, Hints allowed (0–3, default 3), Help allowed, Show-correct-if-wrong, Show-if-correct, Show-hint-if-wrong.
**Preview embeds the real student renderer** at:
`/Question/PreviewContent/{questionID}?hintsAllowedNum=…&isHelpAllowed=…&showCorrectAnswerIfWrongOption=…&showIfCorrectOption=…&showHintIfWrongOption=…&isPreviewMode=true&hideShell=true&sessionName=…`
→ **the future app should embed this iframe rather than rebuild the renderer.**

---

## 7. Fields that EXIST but the UI does NOT expose (decide if the app should)
- `Question.PlayAudioOnRenderFlag` — checkbox is commented out in the razor; keeps default/existing value. (We set it on import.)
- `Question.AnswerMinLengthNum`, `AnswerMaxLengthNum`, `IsNumericOnlyAnswer` — Written constraints, not in UI.
- `Question.ParentQuestionID` (multi-part), `LocalizedQuestionID` (localization) — not in UI.
- No **alt-text** field (option image filename is used as alt). No **VTT** field anywhere in QuestionStudio.

---

## 8. Related tables a full writer must handle
- **OptionGroup** (PK QuestionID+GroupName) — required parent for any SelectionOption with a GroupName (Sort/Link). ItemsMustHaveMatch, ItemsCanHaveMultipleMatches, Title.
- **WrittenAnswerOption** — Written scoring/hints (CompareText LIKE pattern, ScorePct, HintHTML). StatusCD=4.
- **TemplateElement** (PK TemplateName+HTMLElementID) — HintReplacement FK target. Only IsHintReplaceable=true elements should get hints. Per-option virtual elements are created on save.
- **QuestionTemplate** — Question.TemplateID target (TemplateName, TemplateTypeCD, ComponentName).
- **Topic → SubjectArea → Subject** — classification hierarchy (Topic.EdContentBlobID = help animation).

---

## 9. Our current import scripts vs this spec — gaps to close before "straight to DB"
(what `scripts/bulk_import/import_questions.py` + `ingest_voiceovers.py` do today)
- ✅ Handle: Question core, SelectionOption, QuestionClassification, QuestionHint, HintReplacement (text + hint-graphic-audio), ReaderBlobID/AudioBlobID, ImageBlobID, CorrectAnswerText, Title, StatusCD=3, PlayAudioOnRenderFlag, timestamps.
- ⚠️ **Not yet handled / to confirm:**
  - **Option (answer) voiceovers** → `SelectionOption.AudioBlobID` (+ ReaderBlobID). *(Dan's next build.)*
  - **Written** questions → `WrittenAnswerOption` rows (we skip Written today).
  - **Sort/Link** → `OptionGroup` rows + pair/order `CorrectAnswerText`. (0 in content currently.)
  - **ColorSchemeID** — set via SQL post-import, not by importer. UI treats it as required.
  - **IsNumericOnlyAnswer** — must be set (non-null bit); confirm importer passes it.
  - Alt text lives in `Blob.Description` (accessibility) — separate from QuestionStudio.
