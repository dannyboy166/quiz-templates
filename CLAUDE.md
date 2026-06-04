# Claude Context

Project context for AI assistance.

## Safety Rules

**CRITICAL - READ FIRST:**
- **NEVER delete data** from database - only INSERT
- **NEVER modify** Victor's existing records
- **Victor is the boss** - we're helping him, not overriding
- Only INSERT into `DanTest` or `DevTest` schemas
- Only INSERT into blob containers when Victor approves
- Victor reviews all bulk imports before production

## Project Overview

**WorldWise** - An educational learning platform for K-12 students, approved by the Department of Education. Features teacher and student portals with adaptive learning, curriculum alignment, and comprehensive question templates.

## Team Structure

| Person | Role |
|--------|------|
| **Victor** | Backend lead, database architect. Builds .NET backend, Azure infrastructure. **THE BOSS** |
| **Dan** | Frontend developer. HTML/CSS/JS quiz templates, animations. Helping with bulk data import |
| **Julie/Tanya** | Project owners. Curriculum content, question creation, design direction |
| **Dat** | Developer. Working on Student Portal (Blazor). Checking audio issues. |
| **Aidan** | Developer. Building car racing game (Unity) for the portal. Uses Azure DevOps. |

## Current Status (22 May 2026)

### DanTest Sandbox - Complete, Victor Approved

**DanTest Results (after 23 Apr 2026 fixes):**
| Table | Count | Status |
|-------|-------|--------|
| Questions | 7,585 | ✅ All fields populated |
| SelectionOptions | 23,039 | ✅ Cleaned (was 30,337 - removed T/F + empty options) |
| QuestionClassifications | 7,583 | ✅ All linked (2 questions missing - check spreadsheet) |
| QuestionHints | 2,165 | ✅ Working |
| HintReplacements | 2,165 | ✅ Working |
| ImageBlobID linked | 413 | ✅ Questions with images auto-linked |
| SpreadsheetXRef | 42,542 | ✅ All mappings populated |

**Template Distribution:**
- Select One: 5,818 questions
- Select All: 584 questions
- True/False: 1,183 questions
- Written (skipped): 327 word-list questions (awaiting Julie's template decision)

### Victor's Feedback Fixes (23 Apr 2026)
All applied to DanTest via SQL:
1. **Title** was ItemID ("20012001") → Now truncated question text
2. **TeacherNotes** had Kristie's internal notes (2,526) → Cleared (notes preserved in spreadsheet)
3. **Select All CorrectAnswerText** was "duck, dog" → Now option numbers "1, 3"
4. **T/F CorrectAnswerText** 7 had "0"/"1" → Fixed to "True"/"False"
5. **T/F SelectionOptions** (4,732) → Deleted (template shows buttons automatically)
6. **Empty SelectionOptions** (2,566) → Deleted

**SpreadsheetXRef table:**
- Victor created `DanTest.SpreadsheetXRef` table (23 Apr 2026)
- Recreated with surrogate key `SpreadsheetXRefID` (identity) - can't use JSON in index
- One row per individual record with `TableRecordKeyJson` storing the record's key
- Tracks: Question (7,585), SelectionOption (23,042), QuestionClassification (7,585), QuestionHint (2,165), HintReplacement (2,165)
- Import script reads/writes this table for duplicate detection
- Old CSV mapping file (`data/questions/item_question_mapping.csv`) kept as backup

**SystemEvent logging added:**
- Writes EventTypeCD=121 (Batch Load) at start and end of each import
- Start: IsActive=1, End: IsActive=0 with summary of created/skipped/errors

**Minor issues found (not yet fixed):**
- 3 Select One questions with <2 options (QIDs: 32062, 32466, 34267)
- 2 questions with NULL CorrectAnswerText (QIDs: 29401, 32062)
- 2 questions without classification
- 375 duplicate question texts (normal - same question with different answer options, e.g., drill questions)

### DevTest - Loaded, Awaiting Victor's Review

**Status:** 7,585 questions loaded to DevTest (30 Apr 2026). Awaiting Victor's review.

**DevTest Results (verified from DB 22 May 2026):**
| Table | Count | Status |
|-------|-------|--------|
| Questions | 7,625 | ✅ 7,585 ours + 38 pre-existing + 2 test |
| SelectionOptions | 23,158 | ✅ Clean (365 with images from Airtable) |
| QuestionClassifications | 7,616 | ✅ Linked |
| QuestionHints | 2,169 | ✅ Working |
| HintReplacements | 2,170 | ✅ Working |
| SpreadsheetXRef | 42,540 | ✅ All mappings populated |
| Blobs | 1,918 | 1,814 images + 104 audio (1,850 ours + 68 pre-existing) |

**Subject restructure (Victor approved via email, applied 30 Apr 2026):**
- 7 English subjects (Grammar, Phonics, Punctuation, Reading Comprehension, Spelling, Vocabulary, Phonological Awareness) merged into single "English" subject - these become SubjectAreas instead
- Maths stays as 3 separate subjects: Number & Algebra, Measurement & Space, Statistics & Probability
- Creative Arts created as new subject
- Other subjects unchanged (HSIE, PDHPE, Science & Technology)

**AcademicLevel entries created (30 Apr 2026):**
- Stage 1 - Year 1 (ID=2)
- Stage 1 - Year 2 (ID=3)
- Stage 2 - Year 3 (ID=4)
- Stage 2 - Year 4 (ID=5)
- Stage 3 - Year 5 (ID=6)
- Stage 3 - Year 6 (ID=7)
- All imported questions set to "Stage 1 - Year 1"

**Images (uploaded 1 May 2026):**
- 1,814 image blobs in DevTest (682 originally uploaded + Airtable imports + pre-existing)
- 1,150 questions linked to images via ImageBlobID
- 365 selection options linked to images (from Airtable import)
- CDN cache purged 4 May 2026 - images now displaying correctly
- ColorSchemeID set to 3 (Blue) for 7,593 questions
- Blob container: `devtestblobs` (Victor moved files from `devtest` to `devtestblobs` on 15 May 2026)
- Content type fix applied: SVGs now served as `image/svg+xml`
- **Accessibility:** `tag_images.py` running on DevTest (22 May 2026) to generate contextual alt text for all images using Claude Vision. Browser TTS will read descriptions aloud for visually impaired students (setting toggle, decided with Julie 22 May).
- Blob paths in DB are relative (`images`, `audio`) — Victor's app prepends CDN URL + container

**Voice overs (confirmed working 13 May 2026):**
- Container: `devtestblobs` under `audio/` path (Victor moved from `devtest` on 15 May 2026)
- CDN URL: `https://wwblobserver-gdchhdg2bdhgf7cc.z01.azurefd.net/devtestblobs/audio/{Filename}.mp3`
- **ReaderBlobID** = speaker icon on question text, click to play (confirmed working). ElevenLabs generated.
- **AudioBlobID** = speaker icon on question image, hover to play (Victor explained 14 May 2026, Dat checking operation). Currently points to same audio as ReaderBlobID.
- **Image descriptions** will use browser built-in text-to-speech reading Blob.Description (Julie decision 22 May 2026). No need to generate separate ElevenLabs audio for image hover — browser TTS handles it via student settings toggle.
- 103 questions with ReaderBlobID, 102 with AudioBlobID, 102 with both (verified 22 May 2026)
- 104 audio blobs total (101 ours + 3 pre-existing)
- Naming convention: `{ItemID}-question.mp3` (Victor confirmed 14 May 2026)
- VTT caption files (if needed): `{ItemID}-question.vtt` — `Blob.HasVttFile` tracks this (0 populated so far)
- VONWQ handling: just delete the question text (Victor confirmed 14 May 2026)
- Generation script: `scripts/bulk_import/generate_voiceovers.py`
- 89 questions with image-based options: don't read option text aloud
- 6 number pattern questions (QIDs 6306-6311): sequence only, no question text — data issue

**DevTest database state:**
- Schema: `DevTest`, UserID: 8
- All questions StatusCD=3 (Pending) - need admin approval to go live
- Existing 38 questions untouched

**Minor issues (same as DanTest):**
- 2 Kristie questions with incomplete data (ItemIDs: 00141224, 01021805)
- 1 NULL CorrectAnswerText (QID 2456)
- 3 questions without classification (QIDs: 2023, 2456, 6039)
- 2 questions with <2 options (QIDs: 5109, 6910)

**Still to discuss with Victor (Tuesday 8am meeting):**
- SubjectArea naming convention (_Stage One suffix on existing ones vs clean names on new ones)
- Topic naming convention (_Year 1/_Year 2 suffix on existing ones vs clean names on new ones)

**Other tasks from Victor:**
- Talk to Aidan about Journey game integration (how questions will work in-game) — spoke to Aidan 20 May 2026, sent email explaining CDN/blob setup
- Victor wants to integrate Dan's question templates into student portal AFTER portal is close to where they want it
- Dat + Dan to discuss JS objects for portal UI (bouncy dice, door opening, turning pencil) — Victor wants to set up meeting
- Selection options can have audio (hover to play) - relevant for voice overs
- Victor will check math game security report when he has time

### Deployment Workflow (from Victor)
1. **DanTest (sandbox)** ← Complete ✅ Victor approved
2. **Dev** ← Skipped (Victor went straight to DevTest)
3. **DevTest** ← Loaded ✅ Awaiting Victor's review

### Duplicate Detection & Mapping Strategy (decided 23 Apr 2026)
**Problem:** Title field was used for duplicate detection (stored ItemID). Victor wants Title to be descriptive.
**Solution (agreed with Victor):** Victor created `SpreadsheetXRef` mapping table with:
- SpreadsheetRecordID (Kristie's ItemID)
- TableName (e.g., "Question", "SelectionOption")
- QuestionID (the database ID)
- TableRecordKeyJson (composite key for child records)

**Import rules (from Julie):**
- Kristie keeps using Google Sheets (her team prefers it)
- Import always reads full spreadsheet, only INSERTs new questions
- NEVER override existing questions (Julie may fix them in QuestionStudio)
- Manual overrides only when specifically requested
- After initial upload, Kristie's sheet gets "locked off"
- Future changes: separate "Updated" sheet or done in QuestionStudio

## What We Built

### Import Pipeline

**New workflow (from 19 May 2026):**
```
Master Template (Google Sheet, 21 columns with dropdowns)
        ↓  download as .xlsx
import_questions.py --schema DevTest
        ↓
Azure SQL Database
```

**Old workflow (Stage 1 import, before template):**
```
Original Spreadsheets (messy, different layouts)
        ↓
standardize_spreadsheets.py
        ↓
Standardized Excel (clean, 20 columns)
        ↓
import_questions.py --schema DanTest|DevTest
        ↓
Azure SQL Database
```

**Key Features:**
- **Configurable schema** via `--schema` flag (DanTest uses UserID=2, DevTest uses UserID=8)
- **SUBJECT_MAP** maps 15 spreadsheet subject codes to database subjects (e.g., 'English GR' -> 'English', 'Maths N&A' -> 'Maths Number & Algebra')
- **CATEGORY_CLEANUP** merges ~30 messy Kristie subcategories into proper parent categories (e.g., 'action verbs' -> 'Grammar', '_ce' -> 'Phonics')
- **AcademicLevel** defaults to "Stage 1 - Year 1" for all questions (format: `Stage 1 - Year {grade}`)
- Handles different column layouts (English vs Math spreadsheets)
- Parses hints (H1, H2, H3) into separate columns
- Detects template type (Multiple Choice vs True/False)
- Creates full hierarchy: Subject -> SubjectArea -> Topic
- Links hints with correct TemplateName/HTMLElementID
- Idempotent - uses SpreadsheetXRef table for duplicate detection
- INSERT only by default - never overrides existing questions (Julie's rule)
- Tracks all records in SpreadsheetXRef (Question, SelectionOption, QuestionHint, HintReplacement, QuestionClassification)
- Skips word-list questions (need Julie's input)
- Preserves "None" and "0" text as option values (not converted to null/empty)
- Handles MediaType (VO/VONWQ) with PlayAudioOnRenderFlag
- Populates CorrectAnswerText from correct option(s)
- Auto-links ImageBlobID by matching `{ItemID}-question` blob pattern
- Sets CreatedTime/LastModTime to GETDATE()
- Sets StatusCD=3 (Pending) for review workflow
- SystemEvent logging at start/end of each import batch

## Access Details

| Resource | Details |
|----------|---------|
| Azure Portal | portal.azure.com |
| Account | Dan@eStreet.com.au |
| Storage Account | worldwiseaustg |
| Database Server | wwa.database.windows.net |
| Database | wwa_dev |
| Schemas | DanTest (sandbox, UserID=2), DevTest (live portal, UserID=8) |

### Blob Containers

| Container | Purpose | Access |
|-----------|---------|--------|
| `danassets` | Sandbox for testing uploads | ✅ Have |
| `devtest` | Legacy for DevTest — files moved to `devtestblobs` (15 May 2026) | ✅ Have |
| `devtestblobs` | DevTest images + audio + help videos (app reads from here via CDN) | ✅ Have |
| `devblobs` | Dev environment blobs. `helpcontent` folder created (25 May 2026) for Get Help samples | ✅ Have |
| `wwassets` | Legacy — Victor confirmed being deleted (1 May 2026) | ✅ Have |

### Azure DevOps

| Resource | Details |
|----------|---------|
| Organization | `e-street` at `dev.azure.com/e-street` |
| Project | `WorldWise` |
| MathGame repo | `dev.azure.com/e-street/WorldWise/_git/MathGame` |
| Auth method | Personal Access Token (PAT) embedded in git remote URL |
| Web access | **Granted** 24 May 2026 — Contributor privilege to repo |
| Student Portal | `Dan@TestClass` / `World@Wise0` (Victor created 25 May 2026) |

Local MathGame folder: `/Users/danielsamus/MathGame` (has PAT in remote, still works for git push/pull)
Source code: `/Users/danielsamus/MathCrush2` (GitHub) and `/Users/danielsamus/MathCrush2_Infants` (GitHub)

**Victor's main codebase** cloned to `/Users/danielsamus/WW/` (25 May 2026):
- **WWApp** — Teacher/Admin portal (Blazor Server + WebAssembly). QuestionStudio (~900 lines) for creating questions one at a time.
- **WWAppStudent** — Student portal. Quiz engine, 6 template components, hint system, math game + racing game integration.
- **WWDbConfig** — Database models, 39 EF Core migrations, 9 stored procedures. `GetNextQuestion` SP is 800+ lines.
- **Tech stack:** .NET 10.0, Blazor hybrid, EF Core 10.0.1, Azure Blob Storage, Sass/SCSS
- **~532 source files** across 9 projects, 777 files total
- **No bulk import in the UI** — questions added one at a time via QuestionStudio. Our Python import scripts are the only bulk method.
- **Template system:** 6 templates (Template1-6), each is a Blazor component extending BaseQuestionTemplate. Adding new templates = new Razor component + SCSS + DB records.
- **Key stored procedures:** GetNextQuestion (session/quiz logic), CheckAnswer, PostAnswer, GetQuestionHint
- **Contributors:** Victor and Dat (based on commit history)

### Connection Method

```bash
# 1. Activate Python environment
source venv/bin/activate

# 2. Login to Azure (opens browser)
az login

# 3. Run scripts
python -m scripts.bulk_import.db_connect
```

## Project Structure

```
quiz-templates/
├── demo-*.html              # Frontend templates (20+)
├── css/, js/, assets/       # Frontend assets
├── audio/                   # Generated audio files
│
├── scripts/
│   ├── create_template.py             # Generate QUESTION_TEMPLATE.xlsx (master template)
│   └── bulk_import/                   # Bulk import scripts
│       ├── __init__.py
│       ├── db_connect.py              # Database connection (Azure AD token auth)
│       ├── standardize_spreadsheets.py # Clean old spreadsheet format (legacy)
│       ├── import_questions.py        # Import questions ✅ (handles old + new format)
│       ├── import_blobs.py            # Upload images/audio/video ✅
│       ├── generate_voiceovers.py     # Generate question voice overs ✅
│       ├── import_from_airtable.py    # Download Georgia's images from Airtable ✅
│       ├── tag_images.py              # Auto-tag images using Claude Vision ✅ (DevTest done)
│       ├── review_questions.py       # AI quality review of questions (Pass 1: spelling, answers)
│       ├── search_images.py           # Search images by tags (DanTest only)
│       ├── link_images.py             # [OBSOLETE] Superseded by import_questions.py
│       ├── analyze_images.py          # [OBSOLETE] One-off image audit
│       └── update_mediatype.py        # [OBSOLETE] Approach rejected by Victor
│
├── data/
│   ├── questions/
│   │   ├── QUESTION_TEMPLATE.xlsx  # Master template for Kristie (21 cols, dropdowns)
│   │   ├── clean/           # Converted to new 21-col format (upload these to Google Drive)
│   │   ├── original/        # Original messy spreadsheets (Stage 1, 3 files)
│   │   ├── standardized/    # Clean standardized format (Stage 1)
│   │   ├── drive_stage1/    # Fresh downloads from Google Drive (Stage 1, for comparison)
│   │   ├── drive_stage2/    # Stage 2 files from Google Drive (Maths + English)
│   │   └── reference/       # Topic list, ItemID numbering guide
│   └── voiceovers/          # Generated MP3 voice overs (output of generate_voiceovers.py)
│
├── docs/
│   └── victor-erd.png       # Database ERD diagram
│
├── venv/                    # Python virtual environment
├── CLAUDE.md                # This file
└── README.md                # Template documentation
```

## Usage

### New Workflow (using master template)

```bash
source venv/bin/activate
az login

# Dry run first
python -m scripts.bulk_import.import_questions --schema DevTest --dry-run "path/to/downloaded_sheet.xlsx"

# Import for real
python -m scripts.bulk_import.import_questions --schema DevTest "path/to/downloaded_sheet.xlsx"
```

No standardization step needed — the template is already in the correct format.

### Legacy: Standardize Old Spreadsheets (Stage 1 only)

```bash
source venv/bin/activate
python -m scripts.bulk_import.standardize_spreadsheets
```

This reads from `data/questions/original/` and creates clean files in `data/questions/standardized/`.
Only needed for Kristie's old-format spreadsheets. Not needed with the new template.

### Step 2: Import Questions

```bash
# Preview (dry run) - defaults to DanTest schema
python -m scripts.bulk_import.import_questions --dry-run

# Import to DanTest (default)
python -m scripts.bulk_import.import_questions

# Import to DevTest
python -m scripts.bulk_import.import_questions --schema DevTest

# Dry run for DevTest
python -m scripts.bulk_import.import_questions --schema DevTest --dry-run

# Specify a file
python -m scripts.bulk_import.import_questions --schema DevTest "path/to/file.xlsx"
```

### Step 3: Import Images (when ready)

```bash
# Preview
python -m scripts.bulk_import.import_blobs --dry-run images/

# Upload
python -m scripts.bulk_import.import_blobs images/
```

### Step 4: Import Images from Airtable (Georgia's images)

```bash
# Preview all tables
python -m scripts.bulk_import.import_from_airtable --schema DevTest --dry-run

# Import specific table
python -m scripts.bulk_import.import_from_airtable --schema DevTest --table "Statistics & Probability"

# Import all
python -m scripts.bulk_import.import_from_airtable --schema DevTest
```

### Step 5: Generate Voice Overs

```bash
# Test with random questions
python -m scripts.bulk_import.generate_voiceovers --test 20

# Dry run (show SSML, no API calls)
python -m scripts.bulk_import.generate_voiceovers --test 20 --dry-run

# Specific questions
python -m scripts.bulk_import.generate_voiceovers --qids 7590 124 5212

# Bulk generation in batches of 500 (resumable)
python -m scripts.bulk_import.generate_voiceovers --all --batch 500 --resume
```

## Spreadsheet Column Structure

### Old Format (Kristie's original sheets — legacy)

The original spreadsheets had different column layouts:

| File/Sheet | Columns | Option1 Col | Notes |
|------------|---------|-------------|-------|
| English (all sheets) | 16 | Col 6 | Standard structure |
| Maths/Number & Algebra | 17 | Col 7 | Has extra "New Image No." at col 5 |
| Maths (other sheets) | 16 | Col 6 | Standard structure |
| Other Subjects (all) | 16-19 | Col 6 | Standard structure |

The standardize script auto-detects this and uses the correct mapping.

### Clean Format (converted 19 May 2026)

All spreadsheets have been converted to the new 21-column format and saved in `data/questions/clean/`:

| File | Questions | Verified |
|------|-----------|----------|
| Kristie Stage One Other Subjects Questions WORLD WISE.xlsx | 2,842 | Row-by-row, 0 issues |
| Krisite Stage One English Questions WORLD WISE.xlsx | 3,064 | Row-by-row, 0 issues |
| Kristie Stage One Mathematics Questions WORLD WISE.xlsx | 2,008 | Row-by-row, 0 issues |
| Kristie Stage Two Mathematics Questions WORLD WISE.xlsx | 1,499 | Row-by-row, 0 issues |

**Data quality fixes applied during conversion (208 total):**
- 142 ImageRequired case fixes ("y"/"n" → "Y"/"N")
- 61 Subject mislabels fixed ("easier"/"harder"/"easy" → "English")
- 5 MediaType whitespace trimmed ("VO " → "VO")

**Remaining data gaps (Kristie needs to fill in):**
- 717 questions with empty Category (Science & Technology: 682, PD H PE: 35)
- 194 questions with empty MediaType (scattered)
- 1 duplicate ItemID: `01021401` in Maths N&A (two different questions, same ID)

## New Template Spreadsheet (built 19 May 2026)

Master template for Kristie/Zoe/Georgia: `data/questions/QUESTION_TEMPLATE.xlsx`
Generated by: `scripts/create_template.py`

**21-column format with 6 dropdowns:**

| Col | Name | Dropdown? | Description |
|-----|------|-----------|-------------|
| A | ItemID | | Unique 8-digit question identifier |
| B | QuestionType | Select One, Select All, True/False, Written, Sort, Link | Question type (friendly names, mapped to TemplateID on import) |
| C | Subject | English, Maths Number & Algebra, etc. (8 values) | Database subject name |
| D | Category | | SubjectArea / parent category |
| E | Grade | 1, 2, 3, 4, 5, 6 | Year level (Stage derived automatically: Y1-2=Stage 1, Y3-4=Stage 2, Y5-6=Stage 3) |
| F | Topic | | Topic name |
| G | QuestionText | | The question itself |
| H-K | Option1-4 | | Answer options (blank for True/False) |
| L | Answer | | Correct option: 1-4, "True"/"False", or "1 and 3" for Select All |
| M | Level | 1, 2, 3 | Difficulty level |
| N | MediaType | P, VO, VONWQ | P=Picture, VO=Voice Over, VONWQ=Voice Over No Written Question |
| O | ImageRequired | Y, N | Y=question needs image to make sense, N=nice to have |
| P | ImageDescription | | Image description/brief for Georgia |
| Q-S | Hint1-3 | | Progressive hints (separate columns) |
| T | GetHelp | | What teacher says/shows when student clicks Get Help |
| U | Notes | | Internal notes (NOT imported to database) |

**3 sheets in the template:**
1. **Instructions** — column guide, rules, ItemID numbering system
2. **Template** — the working sheet with headers, dropdowns, and sample rows
3. **Reference Data** — valid values, question types explained, grade/stage mapping, GetHelp guide

**Key changes from Kristie's old format:**
- **QuestionType** dropdown (new) — Kristie picks the type explicitly instead of us guessing
- **Subject** dropdown — exact database names, no more codes like "English GR"
- **GetHelp** column (new) — teacher help content (text or video descriptions)
- **Hints** in 3 separate columns — no more "H1 - text H2 - text" combined format
- **Consistent columns** across ALL subjects and years — no more 16 vs 17 column layouts
- **"New Image No." removed** — the column that caused Maths to have a different layout
- **Grade/Level/MediaType/ImageRequired** all have dropdowns

**Import compatibility:**
- `import_questions.py` updated to handle both old format (TemplateID as number) and new format (QuestionType as text)
- QUESTION_TYPE_MAP maps friendly names to template IDs: "Select One"→1, "Select All"→2, etc.
- Stage is now derived from Grade via GRADE_TO_STAGE: Year 1-2→Stage 1, Year 3-4→Stage 2, Year 5-6→Stage 3

**GetHelp column notes:**
- Victor already has a "Get Help" button in the student portal UI (next to "Get Hint")
- **Victor responded (19 May 2026):** Help content will be stored as blobs in the Storage Account, served via CDN. Will go in their own folder in `devblobs` and `devtestblobs` for hygiene.
- **Victor confirmed (25 May 2026):** Single HTML files (not folder structures) + MP4/WebM. `devblobs->helpcontent` folder created. Software changes for help button expected end of week (30 May 2026).
- Previously the Help button just pointed to an external URL (`Question.HelpURL` field). Victor is now building internal blob support for it.
- `Question.HelpURL` field exists (nvarchar 1000) — currently only 1 record populated (and it's just test data)
- Victor wants Dan to create some sample help content and put it in `devblobs` for development testing
- Media types: HTML (single file, interactive help lessons) + MP4/WebM (video). Dan confirmed 22 May.
- Victor will provide a mechanism for loading help content through the UI
- GetHelp is conceptually different from hints: hints are small nudges, GetHelp is a teacher explaining the concept
- Not imported to DB yet — captured in spreadsheet for when blob loading is ready

## Database Schema

### Full ERD (20 tables)

The ERD at `docs/victor-erd.png` shows these tables:

**Curriculum hierarchy:** Subject → SubjectArea → Topic → QuestionClassification → Question
**Quiz/Collection hierarchy:** CollectionTemplate → QuestionCollection → QuestionCollectionQuestion → Question
**Session/Answer hierarchy:** ActiveSession → ActiveSessionQuestion → Question
**Media:** Blob (referenced by Question via ImageBlobID, AudioBlobID, ReaderBlobID; by SelectionOption via ImageBlobID, AudioBlobID)
**Hints:** Question → QuestionHint → HintReplacement ← TemplateElement
**Tracking:** SpreadsheetXRef, SystemEvent

**Question table (verified from DB 22 May 2026):**
QuestionID, TemplateID (FK), ImageBlobID (FK→Blob), AudioBlobID (FK→Blob), ReaderBlobID (FK→Blob), ColorSchemeID (FK), Title (varchar 1000), TextHTML (varchar max), CorrectAnswerText (nvarchar 200), TeacherNotes (varchar max), HelpURL (nvarchar 1000 — for Get Help button, being replaced with blob-based approach), IncorrectTFHintHTML (varchar 1000 — unused so far), PlayAudioOnRenderFlag (bit), IsNumericOnlyAnswer (bit), StatusCD, ParentQuestionID, LocalizedQuestionID, AnswerMaxLengthNum, AnswerMinLengthNum, + audit columns

**SelectionOption table:**
SelectionOptionID, QuestionID (FK), ImageBlobID (FK→Blob), AudioBlobID (FK→Blob), OptionText, IsCorrectFlag, SortOrderNum, StatusCD, + audit columns

**Blob table (verified from DB 22 May 2026):**
BlobID, BlobTypeCD (110=Image, 111=Audio, 112=Video), Name (varchar 30), Title (varchar 1000), Description (varchar 1000 — alt text for accessibility), Filename (nvarchar 50), Path (nvarchar 200 — relative folder like `images` or `audio`), FileTypeExtn (nvarchar 10), HasVttFile (bit), StatusCD, + audit columns (CreatedTime, CreatedUserID, LastModTime, LastModUserID)

**Common audit columns** (on nearly every table): StatusCD, CreatedByUserID, CreatedTime, LastModByUserID, LastModTime

### QuestionTemplate IDs
| ID | Name | Portal Name |
|----|------|-------------|
| 1 | Select One | Mandatory one option |
| 2 | Select All | At least one |
| 3 | True/False | True or False |
| 4 | Written | Written answer |
| 5 | Sort | Interactive Sorting |
| 6 | Link | Interactive Linking |

### Hierarchy
```
Subject (e.g., "English")
    └── SubjectArea (e.g., "Phonics")
            └── Topic (e.g., "CVC Words")
                    └── Question
                            ├── SelectionOptions (answers)
                            ├── QuestionClassification (links to Topic + Level)
                            └── QuestionHint + HintReplacement
```

### What import_questions.py sets on each table

**Question:** TextHTML, Title (truncated to 80), TemplateID, StatusCD=3, PlayAudioOnRenderFlag, ImageBlobID (auto-linked), IsNumericOnlyAnswer=0, TeacherNotes=NULL, CreatedTime/LastModTime=GETDATE()
**Question NOT set (handled elsewhere):** AudioBlobID, ReaderBlobID (generate_voiceovers.py), ColorSchemeID (set via SQL)

**SelectionOption:** QuestionID, OptionNum, TextHTML, ScorePct (1.0/0.0), StatusCD=4. Skipped entirely for True/False questions.
**SelectionOption NOT set:** ImageBlobID (import_from_airtable.py), AudioBlobID (not yet used)

**QuestionClassification:** QuestionID, TopicID, AcademicLevelID, DifficultyLevelNum (1-3)

**QuestionHint:** QuestionID, HintLevelNum (1-3), StatusCD=4
**HintReplacement:** QuestionID, HintLevelNum, TemplateName, HTMLElementID='question-text-content', HintHTML

### Hints Structure
Hints require valid FK references to TemplateElement:
- `TemplateName`: "Select One", "True/False", etc.
- `HTMLElementID`: "question-text-content"

```sql
-- Example hint insert
INSERT INTO HintReplacement
    (QuestionID, HintLevelNum, TemplateName, HTMLElementID, HintHTML, ...)
VALUES
    (123, 1, 'Select One', 'question-text-content', 'This is hint 1...', ...)
```

## ST4S Compliance (Safer Technologies 4 Schools)

**Documents (Julie provided 22 May 2026):**
- `docs/Safer-Technologies-4-Schools-Supplier-Guide-2025.1-v1.0.pdf` — **Latest** ST4S framework (Release 2025.1, 16 Dec 2025)
- `docs/Responsible-AI-Supplier-Guide-2025-v0.4.pdf` — RAI assessment for AI features (Release 2025.1, 9 Oct 2025). Separate from ST4S. Requires ST4S compliance first.
- `docs/Safer-Technologies-4-Schools-Supplier-Guide-2023.2-v1.1.pdf` — Old version (July 2024, superseded)
**Website:** www.st4s.edu.au

### What is ST4S?
Assessment framework run by Education Services Australia (ESA) via NSIP. Covers security, privacy, interoperability, and safety. Products are tiered (Tier 1 = highest risk, Tier 2 = lower risk). WorldWise is likely **Tier 2** ("Learning activities, assessments and games").

### Key Requirements Relevant to Us

**P14 - WCAG 2.1 Accessibility (MANDATORY):**
- Minimum: **WCAG 2.1 Level A** (Tier 2) or **Level AA** (Tier 1)
- Alt text on all images — `tag_images.py` running on DevTest (22 May 2026), generates contextual descriptions using Claude Vision + question text
- Keyboard navigation on HTML templates
- Colour contrast ratios
- ARIA labels on interactive elements
- Audio captions (VTT files — structure exists but 0 populated)

**Image audio accessibility (decided with Julie 22 May 2026):**
- Image descriptions stored as alt text in `Blob.Description` (populated by `tag_images.py`)
- When student hovers on image, browser's built-in text-to-speech reads the alt text aloud
- This is a student **setting** they toggle on (off by default) — only visually impaired students need it
- **No need to generate ElevenLabs audio for image descriptions** — browser TTS handles it
- Victor's portal needs to: render `Blob.Description` as `alt` attribute on `<img>` tags, and implement the TTS toggle in student settings
- ElevenLabs voice overs are only for **question text** (ReaderBlobID), not image descriptions

**P11 - No Advertising:** Service must not display ads. We're fine.

**PF2 - Role-based Access Control:** Admin accounts must control user access. Victor's portal handles this.

**PF25 - Learning Activities/Games:** Describes our quiz functionality. Need to document:
- Pre-defined response options (Select One, Select All, True/False)
- Written answer fields
- Data analytics/reporting to teachers
- Teacher can create learning activities (QuestionStudio)

**PF51 - OWASP File Upload Security:** Relevant to our blob upload pipeline (`import_blobs.py`).

**SC1/SC1A - Acceptable Use Policy:** Must be in child-friendly language for student portal.

**SC5 - Restrict Non-School Users:** Controls to prevent outsiders interacting with students.

**PR20 - AI/ML Data Use:** User data must NOT be used for AI/ML training. Relevant if we add AI features.

**Section 6.9 - AI Module:** Separate assessment for AI features (piloting since Jul 2024). Covers AI hosting, logging, access, testing, incidents, data retention, privacy, safety.

### What Victor Handles (Infrastructure/Backend)
Most of ST4S is infrastructure that Victor/Azure handles:
- Encryption: TLS 1.2+, AES 256 (Azure default)
- Hosting location: Azure Australia
- Data retention/deletion policies
- Incident response plans
- Privacy policy, Terms of Service (legal/Julie)
- Database security controls (S8)
- Multi-tenancy segregation (S4)
- Intrusion detection (S7)
- Key management (S6)
- IRAP assessment (H6)
- Logging and audit trails (PF39)

### What We Handle (Frontend/Content)
1. **WCAG accessibility** — alt text, keyboard nav, colour contrast, ARIA labels, captions
2. **Content appropriateness** — no offensive material in questions/images
3. **No advertising** in templates
4. **File upload security** — OWASP principles in blob imports
5. **Question template accessibility** — screen reader support in demo-*.html files

### ST4S Action Items
- [ ] Run `tag_images.py` on DevTest to populate Blob.Description (alt text) for all 1,814 images
- [ ] Audit HTML question templates for WCAG 2.1 Level A compliance (keyboard nav, ARIA, contrast)
- [ ] Generate VTT caption files for audio (HasVttFile = 0 for all 1,918 blobs)
- [ ] Discuss with Victor which tier WorldWise falls under and assessment timeline

## Pending Items

### Waiting on Victor (as of 25 May 2026)
- **Get Help UI mechanism** — Victor building software changes for help button to support HTML + MP4/WebM. Expected end of week (~30 May 2026). `devblobs->helpcontent` folder ready for sample content.
- **SubjectArea naming** - existing ones have `_Stage One` suffix, new ones don't
- **Topic naming** - existing ones have `_Year 1`/`_Year 2` suffix, new ones don't
- **Dat looking at audio issues** — Victor mentioned this 14 May 2026
- **MathGame security report** — Victor set up security scanning on MathGame repo. webgl_portal_v5 pushed 30 Apr 2026. Victor will check report when he has time.

### Resolved (since 19 May 2026)
- ✅ **Get Help storage** — Victor confirmed: blobs in Storage Account, served via CDN, own folder in containers (19 May 2026)
- ✅ **Get Help folders created** — `devblobs->helpcontent` folder ready (25 May 2026). Single HTML files + MP4/WebM.
- ✅ **AudioBlobID vs ReaderBlobID** — Victor explained (14 May 2026): ReaderBlobID = speaker on question text (click to play), AudioBlobID = speaker on question image (hover to play). Set both.
- ✅ **Azure DevOps access** — Contributor privilege granted (24 May 2026). Student Portal login: `Dan@TestClass` / `World@Wise0`
- ✅ **Image descriptions** — Victor reviewed and confirmed they look great (25 May 2026). VTT files for video/audio, image descriptions from Blob.Description field.
- ✅ **Alt text populated** — 1,674 images tagged with contextual descriptions (22 May 2026). Victor confirmed approach.

### Stage 1 Corrections Needed (discovered 19 May 2026)
Kristie made changes to her spreadsheets after we imported. Need Julie/Victor approval to apply:
- **3 answer corrections:**
  - ItemID `10011813` (Maths M&S) — answer 3→5
  - ItemID `00241803` (PD H PE) — answer 1→3
  - ItemID `00221229` (Sci & Tech) — answer "1 and 2"→"2 and 3"
- **1,331 new hints** added to Other Subjects (HSIE: 599, Sci&Tech: 599, Creative Arts: 111, PDHPE: 22)
- **~10 question text/typo fixes** (lower priority)

### Stage 2 Status (discovered 19 May 2026)
- **Maths: 1,499 questions ready** (Year 3 + Year 4, updated 17 May 2026)
  - Number & Algebra: 1,047, Measurement & Space: 369, Statistics & Probability: 83
  - Plus 257 empty placeholder slots
  - No hints or difficulty levels yet. All MediaType is "VO"
  - New categories: Decimals, Mixed Equations
  - Uses uniform 16-column layout (no special Maths N&A 17-col issue)
- **English: Structure only, zero content** (5 sheets with headers but no questions)
- **Other Subjects: No file exists yet**
- **Import script ready** — AcademicLevel bug fixed, Stage derived from Grade

### Resolved (since 30 Apr 2026)
- ✅ **Audio container** — `devtestblobs` under `audio/` path (Victor moved from `devtest` on 15 May 2026)
- ✅ **Audio naming** — `{ItemID}-question.mp3` (Victor confirmed 14 May 2026)
- ✅ **VONWQ** — just delete question text (Victor confirmed 14 May 2026)
- ✅ **VTT files** — same name as audio but `.vtt` extension, separate BlobID, `Blob.HasVttFile` flag
- ✅ **Math game pushed** - webgl_portal_v5 pushed to Azure DevOps MathGame repo (30 Apr 2026)
- ✅ **AcademicLevel entries** created via QuestionStudio
- ✅ **Image container migration** — Originally uploaded to `wwassets`, then `devtest`, then Victor moved to `devtestblobs` (15 May 2026). CDN cache purged 4 May 2026.
- ✅ **wwassets container** — Victor confirmed being deleted (1 May 2026), no longer used

### Ask Julie/Kristie (Curriculum)
- **327 word-list questions** (e.g., "cat, bed, sit, dog, sun")
  - No Answer column filled
  - What template should they use? Sort? Link? Custom game?
  - IDs: 20013301, 20013307, etc.
- **2 incomplete questions** (missing options/answers in Kristie's spreadsheet):
  - ItemID **00141224** — "Other Subjects" file → **PD H PE** sheet, ~row 263 (only 1 option, no answer)
  - ItemID **01021805** — "Mathematics" file → **Number and Algebra** sheet, ~row 1277 (only Option 2 filled)
- **717 empty Categories** — Science & Technology (682) and PD H PE (35) have no Category filled in
- **194 empty MediaType** — scattered across English and Maths
- **1 duplicate ItemID** — `01021401` in Maths N&A has two different questions using the same ID

### Access (resolved)
- ✅ DevTest schema access (granted 20 Apr 2026)
- ✅ DevTest blob container access (granted 20 Apr 2026)
- ✅ Import script now supports `--schema DevTest` (no default schema change needed)

### Images & Accessibility
- **Important:** The `ImageDescription` column in spreadsheets is a description/brief for Georgia (e.g., "Image of a cylinder"), NOT actual filenames
- Real images are created separately and named by **ItemID** (e.g., `00110001-question.svg`)
- **1,814 image blobs** in DevTest, **1,150 questions** linked via ImageBlobID
- **365 selection options** linked to images (from Airtable import)
- Thousands more images still need to be created
- Upload using `import_blobs.py` - images link to questions via ItemID matching
- **Alt text DONE (22 May 2026):** 1,674 images tagged with contextual descriptions using Claude Vision + question context. 69 JSON/Lottie skipped (not real images). Victor confirmed they look great (25 May 2026).

## Data Quality Issues Fixed

### 15 Apr 2026 (Standardized Spreadsheet)
All issues fixed in the standardized spreadsheet:

1. **61 questions with wrong Subject** (easy/easier/harder → English SP/VO)
2. **55 questions with () notes** embedded in question text → moved to Notes column
3. **2 questions with wrong Answer** (fixed in original spreadsheets)
4. **11 "None" text values** preserved correctly as option text

### 20 Apr 2026 (Victor's First Review - Import Script)
Victor reviewed DanTest and requested these fixes to `import_questions.py`:

1. **CorrectAnswerText** was not populated → Now populated with correct option text
2. **ImageBlobID** was not linked → Now auto-links by `{ItemID}-question` blob name pattern
3. **CreatedTime/LastModTime** were NULL → Now set to `GETDATE()`
4. **TeacherNotes** had `[MediaType: VO]` prefix → Removed, MediaType handled via PlayAudioOnRenderFlag
5. **StatusCD** was 4 (Active) → Changed to 3 (Pending) for review workflow
6. **36 options with value "0"** were saved as empty string → Fixed (0 is falsy but valid)

### 23 Apr 2026 (Victor's Second Review - Database Fixes)
Victor reviewed again and found more issues. Fixed via SQL UPDATE/DELETE on DanTest:

1. **Title** was ItemID number → Changed to truncated question text (LEFT(TextHTML, 80))
2. **TeacherNotes** had Kristie's internal notes → Cleared to NULL (notes still in spreadsheet)
3. **Select All CorrectAnswerText** was text ("duck, dog") → Changed to option numbers ("1, 3")
4. **T/F CorrectAnswerText** 7 had "0"/"1" → Fixed to "True"/"False"
5. **T/F SelectionOptions** 4,732 records → Deleted (template handles buttons automatically)
6. **Empty SelectionOptions** 2,566 records → Deleted

## Lessons Learned for Future Imports

1. **Always use `keep_default_na=False, na_values=[]`** when reading Excel files with pandas, otherwise text like "None" becomes NaN
2. **Check column structure** - different sheets may have different column layouts
3. **Template detection** - check Option3/Option4 being empty vs actual empty string
4. **Idempotent imports** - use SpreadsheetXRef mapping table for duplicate detection
5. **Handle falsy values carefully** - `0` is valid text but evaluates to False in Python. Use `if x is None` not `if x`
6. **Database defaults vary** - Blob table has GETDATE() defaults, Question table has NULL defaults - check each table
7. **Never override existing questions** - Julie's rule: import only INSERTs new, never UPDATEs unless manually requested
8. **True/False questions** don't need SelectionOptions - template shows buttons automatically
9. **Select All CorrectAnswerText** must be option numbers ("1, 3") not option text ("duck, dog")
10. **Don't store Kristie's internal notes** in TeacherNotes - that field is for actual teachers
11. **Title field** should be descriptive question text, not ItemID
12. **Subject mapping is essential** - Kristie's spreadsheet codes (e.g., 'English GR') don't match database subject names - use SUBJECT_MAP
13. **Category cleanup needed** - Kristie uses inconsistent subcategory names (e.g., 'action verbs', '_ce') - use CATEGORY_CLEANUP to merge into parent categories
14. **Schema differences matter** - DanTest and DevTest have different UserIDs and may have different subject structures

## Reference Data

### Status Codes (StatusCD)
| CD | Meaning |
|----|---------|
| 3 | Pending |
| 4 | Active (default) |
| 5 | Cancelled |
| 6 | Deactivated |
| 7 | Deleted |

### Blob Types (BlobTypeCD)
| CD | Meaning |
|----|---------|
| 110 | Image |
| 111 | Audio |
| 112 | Video |

## Files Reference

### Active Scripts
| File | Purpose |
|------|---------|
| `scripts/create_template.py` | Generate QUESTION_TEMPLATE.xlsx (master template for Kristie) |
| `scripts/bulk_import/db_connect.py` | Database connection (Azure AD token auth, pyodbc) |
| `scripts/bulk_import/standardize_spreadsheets.py` | Clean Kristie's old messy spreadsheets (legacy, not needed with new template) |
| `scripts/bulk_import/import_questions.py` | Bulk import questions (handles both old TemplateID and new QuestionType formats) |
| `scripts/bulk_import/import_blobs.py` | Upload images/audio/video to Azure Blob Storage + create Blob records |
| `scripts/bulk_import/generate_voiceovers.py` | Generate MP3 voice overs via ElevenLabs TTS API |
| `scripts/bulk_import/import_from_airtable.py` | Download Georgia's images from Airtable, upload to blob storage, link to questions |
| `scripts/bulk_import/tag_images.py` | Auto-tag images using Claude Vision API ✅ (DevTest done, 1,674 tagged) |
| `scripts/bulk_import/review_questions.py` | AI quality review — checks spelling, answers, completeness (Pass 1) |
| `scripts/bulk_import/search_images.py` | Search images by tags in Blob.Description (DanTest only) |

### Obsolete Scripts (kept for reference)
| File | Why Obsolete |
|------|-------------|
| `scripts/bulk_import/link_images.py` | Superseded by `import_questions.py` and `import_from_airtable.py` |
| `scripts/bulk_import/analyze_images.py` | One-off audit; ImageFile column was reference images, not filenames |
| `scripts/bulk_import/update_mediatype.py` | Approach rejected by Victor; functionality now in `import_questions.py` |

### Data Files
| File | Purpose |
|------|---------|
| `docs/victor-erd.png` | Database ERD diagram (20 tables, 23 FK relationships) |
| `docs/Safer-Technologies-4-Schools-Supplier-Guide-2025.1-v1.0.pdf` | ST4S compliance framework - LATEST (Dec 2025). Assessment criteria for education platforms. |
| `docs/Responsible-AI-Supplier-Guide-2025-v0.4.pdf` | RAI assessment for AI features (Oct 2025). Separate assessment, requires ST4S first. |
| `docs/Safer-Technologies-4-Schools-Supplier-Guide-2023.2-v1.1.pdf` | ST4S compliance framework - OLD VERSION (July 2024, superseded by 2025.1). |
| `data/questions/QUESTION_TEMPLATE.xlsx` | Master template for Kristie (21 cols, 6 dropdowns, 3 sheets) |
| `data/questions/standardized/ALL_QUESTIONS_STANDARDIZED.xlsx` | Combined clean data from Stage 1 (7,585 questions) |
| `data/questions/item_question_mapping.csv` | ItemID → QuestionID mapping (backup, SpreadsheetXRef is primary) |
| `data/questions/reference/Learning Spheres Topic List.xlsx` | Full topic hierarchy for Other Subjects (K-6) |
| `data/questions/reference/Questions Reference Number Guide.docx` | ItemID numbering system |
| `DataDict.xlsx` | Table/attribute definitions from Victor (sent 10 Apr 2026, may be in email) |
