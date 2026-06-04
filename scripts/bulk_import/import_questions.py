#!/usr/bin/env python3
"""
Bulk import questions from standardized Excel to Azure SQL database.

This script:
1. Reads from standardized spreadsheet format (ALL_QUESTIONS_STANDARDIZED.xlsx)
2. Creates Subject/SubjectArea/Topic/AcademicLevel if they don't exist
3. Imports questions with their options and hints
4. Is idempotent - can run multiple times without duplicates

Usage:
    source venv/bin/activate
    az login
    python -m scripts.bulk_import.import_questions --help
    python -m scripts.bulk_import.import_questions  # uses default standardized file
    python -m scripts.bulk_import.import_questions --dry-run
    python -m scripts.bulk_import.import_questions --schema DevTest
    python -m scripts.bulk_import.import_questions "path/to/custom.xlsx"
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from .db_connect import get_connection

# Default file path
DEFAULT_FILE = Path("data/questions/standardized/ALL_QUESTIONS_STANDARDIZED.xlsx")

# Schema configs: schema name -> user ID
SCHEMA_CONFIG = {
    "DanTest": 2,    # Dan's sandbox
    "DevTest": 8,    # DevTest (live portal)
}

# Subject mapping: spreadsheet name -> database name
SUBJECT_MAP = {
    'English GR': 'English',
    'English PA': 'English',
    'English PH': 'English',
    'English PU': 'English',
    'English RC': 'English',
    'English SP': 'English',
    'English VO': 'English',
    'HSIE': 'Human Society and its Environment',
    'Maths M&S': 'Maths Measurement & Space',
    'Maths N&A': 'Maths Number & Algebra',
    'Maths S&P': 'Maths Statistics & Probability',
    'PDHPE': 'Personal Development Health and Physical Education',
    'Sci & Tech': 'Science & Technology',
    'Creative Arts': 'Creative Arts',
    # Kristie sometimes puts difficulty labels in the Subject column
    'easy': 'English',
    'easier': 'English',
    'harder': 'English',
    'hard': 'English',
}

# Messy category mapping: spreadsheet category -> correct parent category
CATEGORY_CLEANUP = {
    # English Grammar subcategories
    'action verbs': 'Grammar',
    'colour adjectives': 'Grammar',
    'feeling adjectives': 'Grammar',
    'feeling verbs': 'Grammar',
    'number adjectives': 'Grammar',
    'opinion adjectives': 'Grammar',
    'saying verbs': 'Grammar',
    'shape adjectives': 'Grammar',
    'size adjectives': 'Grammar',
    'thinking verbs': 'Grammar',
    # English Phonics subcategories
    '_ce': 'Phonics',
    '_ss': 'Phonics',
    'air': 'Phonics',
    'ch': 'Phonics',
    'consonant + le': 'Phonics',
    'consonant digraphs': 'Phonics',
    'difficult': 'Phonics',
    'double letters': 'Phonics',
    'ear': 'Phonics',
    'extension diff': 'Phonics',
    'igh': 'Phonics',
    'kn': 'Phonics',
    'mb': 'Phonics',
    'sh': 'Phonics',
    'tch': 'Phonics',
    # English Reading Comprehension subcategories
    'inferential': 'Reading Comprehension',
    'literal': 'Reading Comprehension',
    'vocab': 'Vocabulary',
    # English Spelling/Vocabulary difficulty subcategories
    'harder': 'Spelling',
    'hard': 'Vocabulary',
}

# QuestionTemplate IDs
TEMPLATE_SELECT_ONE = 1  # Standard multiple choice (Mandatory one option)
TEMPLATE_SELECT_ALL = 2  # Choose all that apply (At least one)
TEMPLATE_TRUE_FALSE = 3  # True/False
TEMPLATE_WRITTEN = 4     # Written answer (also used for word-list questions to skip)
TEMPLATE_SORT = 5        # Interactive Sorting
TEMPLATE_LINK = 6        # Interactive Linking

# Template names for HintReplacement FK
TEMPLATE_NAMES = {
    1: "Select One",
    2: "Select All",
    3: "True/False",
    4: "Written",
    5: "Sort",
    6: "Link",
}

# Reverse mapping: friendly name -> template ID (for new template format)
QUESTION_TYPE_MAP = {
    "Select One": TEMPLATE_SELECT_ONE,
    "Select All": TEMPLATE_SELECT_ALL,
    "True/False": TEMPLATE_TRUE_FALSE,
    "Written": TEMPLATE_WRITTEN,
    "Sort": TEMPLATE_SORT,
    "Link": TEMPLATE_LINK,
}

# Grade -> Stage mapping
GRADE_TO_STAGE = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}


class QuestionImporter:
    """Handles importing questions from standardized Excel to database."""

    def __init__(self, conn, schema, user_id, dry_run=False):
        self.conn = conn
        self.cursor = conn.cursor()
        self.dry_run = dry_run
        self.schema = schema
        self.user_id = user_id

        # Cache for IDs we create/lookup
        self.subject_cache = {}         # name -> SubjectID
        self.subject_area_cache = {}    # (subject_id, name) -> SubjectAreaID
        self.topic_cache = {}           # (subject_area_id, name) -> TopicID
        self.level_cache = {}           # name -> AcademicLevelID
        self.question_cache = set()     # set of external IDs we've imported

        # Load existing mappings from SpreadsheetXRef table
        self.item_question_map = {}     # ItemID -> QuestionID
        self._load_mapping()

        # Counters for ordering
        self.subject_order = 0
        self.subject_area_order = 0
        self.topic_order = 0

        # Stats
        self.stats = {
            'subjects_created': 0,
            'subject_areas_created': 0,
            'topics_created': 0,
            'levels_created': 0,
            'questions_created': 0,
            'questions_skipped': 0,
            'questions_skipped_wordlist': 0,
            'options_created': 0,
            'hints_created': 0,
            'errors': [],
        }

    def _load_mapping(self):
        """Load existing mappings from SpreadsheetXRef table."""
        # ItemID -> QuestionID for duplicate detection
        self.cursor.execute(f"""
            SELECT SpreadsheetRecordID, QuestionID
            FROM {self.schema}.SpreadsheetXRef
            WHERE TableName = 'Question'
        """)
        for row in self.cursor.fetchall():
            self.item_question_map[row[0]] = row[1]
        print(f"  Loaded {len(self.item_question_map)} mappings from SpreadsheetXRef")

    def _xref_exists(self, item_id: str, question_id: int, table_name: str,
                     key_json: str = None) -> bool:
        """Check if a specific record already exists in SpreadsheetXRef."""
        if key_json:
            self.cursor.execute(f"""
                SELECT 1 FROM {self.schema}.SpreadsheetXRef
                WHERE SpreadsheetRecordID = ? AND QuestionID = ?
                AND TableName = ? AND TableRecordKeyJson = ?
            """, (item_id, question_id, table_name, key_json))
        else:
            self.cursor.execute(f"""
                SELECT 1 FROM {self.schema}.SpreadsheetXRef
                WHERE SpreadsheetRecordID = ? AND QuestionID = ?
                AND TableName = ? AND TableRecordKeyJson IS NULL
            """, (item_id, question_id, table_name))
        return self.cursor.fetchone() is not None

    def _save_xref(self, item_id: str, question_id: int, table_name: str,
                   key_json: str = None):
        """Save a mapping to SpreadsheetXRef table. Idempotent - skips if exists."""
        if self.dry_run:
            return
        if not self._xref_exists(item_id, question_id, table_name, key_json):
            self.cursor.execute(f"""
                INSERT INTO {self.schema}.SpreadsheetXRef
                    (SpreadsheetRecordID, QuestionID, TableName, TableRecordKeyJson,
                     CreatedUserID, LastModUserID)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, question_id, table_name, key_json,
                  self.user_id, self.user_id))
            self.conn.commit()

    def get_or_create_subject(self, name: str) -> int:
        """Get existing SubjectID or create new one."""
        if name in self.subject_cache:
            return self.subject_cache[name]

        # Check if exists
        self.cursor.execute(
            f"SELECT SubjectID FROM {self.schema}.Subject WHERE Name = ?",
            (name,)
        )
        row = self.cursor.fetchone()
        if row:
            self.subject_cache[name] = row[0]
            return row[0]

        if self.dry_run:
            fake_id = len(self.subject_cache) + 1000
            self.subject_cache[name] = fake_id
            self.stats['subjects_created'] += 1
            return fake_id

        # Create new
        self.subject_order += 1
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.Subject
                (Name, Title, Description, RelativePositionOrd, StatusCD, LastModUserID)
            OUTPUT INSERTED.SubjectID
            VALUES (?, ?, ?, ?, 4, ?)
        """, (
            name[:50],           # Name
            name[:100],          # Title
            name,                # Description
            self.subject_order,  # RelativePositionOrd
            self.user_id
        ))

        subject_id = self.cursor.fetchone()[0]
        self.conn.commit()
        self.subject_cache[name] = subject_id
        self.stats['subjects_created'] += 1
        return subject_id

    def get_or_create_subject_area(self, subject_id: int, name: str) -> int:
        """Get existing SubjectAreaID or create new one."""
        cache_key = (subject_id, name)
        if cache_key in self.subject_area_cache:
            return self.subject_area_cache[cache_key]

        # Check if exists
        self.cursor.execute(
            f"SELECT SubjectAreaID FROM {self.schema}.SubjectArea WHERE SubjectID = ? AND Name = ?",
            (subject_id, name)
        )
        row = self.cursor.fetchone()
        if row:
            self.subject_area_cache[cache_key] = row[0]
            return row[0]

        if self.dry_run:
            fake_id = len(self.subject_area_cache) + 2000
            self.subject_area_cache[cache_key] = fake_id
            self.stats['subject_areas_created'] += 1
            return fake_id

        # Create new
        self.subject_area_order += 1
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.SubjectArea
                (SubjectID, Name, Title, Description, RelativePositionOrd, StatusCD, LastModUserID)
            OUTPUT INSERTED.SubjectAreaID
            VALUES (?, ?, ?, ?, ?, 4, ?)
        """, (
            subject_id,
            name[:50],               # Name
            name[:100],              # Title
            name,                    # Description
            self.subject_area_order, # RelativePositionOrd
            self.user_id
        ))

        subject_area_id = self.cursor.fetchone()[0]
        self.conn.commit()
        self.subject_area_cache[cache_key] = subject_area_id
        self.stats['subject_areas_created'] += 1
        return subject_area_id

    def get_or_create_topic(self, subject_area_id: int, name: str) -> int:
        """Get existing TopicID or create new one."""
        cache_key = (subject_area_id, name)
        if cache_key in self.topic_cache:
            return self.topic_cache[cache_key]

        # Check if exists
        self.cursor.execute(
            f"SELECT TopicID FROM {self.schema}.Topic WHERE SubjectAreaID = ? AND Name = ?",
            (subject_area_id, name)
        )
        row = self.cursor.fetchone()
        if row:
            self.topic_cache[cache_key] = row[0]
            return row[0]

        if self.dry_run:
            fake_id = len(self.topic_cache) + 3000
            self.topic_cache[cache_key] = fake_id
            self.stats['topics_created'] += 1
            return fake_id

        # Create new
        self.topic_order += 1
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.Topic
                (SubjectAreaID, Name, Title, Description, RelativePositionOrd, StatusCD, LastModUserID)
            OUTPUT INSERTED.TopicID
            VALUES (?, ?, ?, ?, ?, 4, ?)
        """, (
            subject_area_id,
            name[:50],           # Name
            name[:100],          # Title
            name,                # Description
            self.topic_order,    # RelativePositionOrd
            self.user_id
        ))

        topic_id = self.cursor.fetchone()[0]
        self.conn.commit()
        self.topic_cache[cache_key] = topic_id
        self.stats['topics_created'] += 1
        return topic_id

    def get_or_create_academic_level(self, name: str) -> int:
        """Get existing AcademicLevelID or create new one."""
        if name in self.level_cache:
            return self.level_cache[name]

        # Check if exists
        self.cursor.execute(
            f"SELECT AcademicLevelID FROM {self.schema}.AcademicLevel WHERE Name = ?",
            (name,)
        )
        row = self.cursor.fetchone()
        if row:
            self.level_cache[name] = row[0]
            return row[0]

        if self.dry_run:
            fake_id = len(self.level_cache) + 4000
            self.level_cache[name] = fake_id
            self.stats['levels_created'] += 1
            return fake_id

        # Create new
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.AcademicLevel
                (Name, Title, StatusCD, LastModUserID)
            OUTPUT INSERTED.AcademicLevelID
            VALUES (?, ?, 4, ?)
        """, (name[:50], name[:100], self.user_id))

        level_id = self.cursor.fetchone()[0]
        self.conn.commit()
        self.level_cache[name] = level_id
        self.stats['levels_created'] += 1
        return level_id

    def question_exists(self, external_id: str) -> bool:
        """Check if question with this external ID already imported."""
        if external_id in self.question_cache:
            return True

        # Check mapping file (ItemID -> QuestionID)
        if external_id in self.item_question_map:
            self.question_cache.add(external_id)
            return True
        return False

    def create_question(self, text_html: str, template_id: int,
                        media_type: str = None,
                        external_id: str = None) -> int:
        """Create a question record. Returns QuestionID.

        Args:
            media_type: P (prompt), VO (voice over), VONWQ (voice over no written question)
            external_id: ItemID for looking up associated image blob
        """
        if self.dry_run:
            self.stats['questions_created'] += 1
            return len(self.question_cache) + 5000

        # Truncate fields to fit database constraints
        text_html_safe = str(text_html)[:4000] if text_html else ""
        # Title = truncated question text (not ItemID)
        title_safe = text_html_safe[:80]

        # Don't populate TeacherNotes - Kristie's spreadsheet notes are
        # internal production notes, not useful for teachers in the portal
        notes_safe = None

        # PlayAudioOnRenderFlag = 1 for voice-over questions (VO/VONWQ)
        play_audio = 0
        if media_type and not pd.isna(media_type):
            mt = str(media_type).strip().upper()
            if mt in ['VO', 'VONWQ']:
                play_audio = 1

        # Look up existing image blob for this question (by ItemID-question pattern)
        image_blob_id = None
        if external_id:
            self.cursor.execute(f"""
                SELECT BlobID FROM {self.schema}.Blob
                WHERE Name = ? AND BlobTypeCD = 110
            """, (f"{external_id}-question",))
            row = self.cursor.fetchone()
            if row:
                image_blob_id = row[0]

        self.cursor.execute(f"""
            INSERT INTO {self.schema}.Question
                (TextHTML, Title, TemplateID, TeacherNotes, StatusCD,
                 CreatedUserID, LastModUserID, IsNumericOnlyAnswer, PlayAudioOnRenderFlag,
                 ImageBlobID, CreatedTime, LastModTime)
            OUTPUT INSERTED.QuestionID
            VALUES (?, ?, ?, ?, 3, ?, ?, 0, ?, ?, GETDATE(), GETDATE())
        """, (text_html_safe, title_safe, template_id, notes_safe,
              self.user_id, self.user_id, play_audio, image_blob_id))

        question_id = self.cursor.fetchone()[0]
        self.conn.commit()
        self.stats['questions_created'] += 1
        return question_id

    def create_selection_option(self, question_id: int, option_num: int,
                                 text_html: str, is_correct: bool) -> None:
        """Create a selection option for a question."""
        if self.dry_run:
            self.stats['options_created'] += 1
            return

        # ScorePct is decimal(7,6) - so 1.0 = 100%, 0.0 = 0%
        score_pct = 1.0 if is_correct else 0.0

        # Handle boolean values (True/False questions)
        if isinstance(text_html, bool):
            text_html = "True" if text_html else "False"

        # Handle 0 correctly (it's falsy but valid text)
        if text_html is None or (isinstance(text_html, float) and pd.isna(text_html)):
            text_safe = ""
        else:
            text_safe = str(text_html)[:1000]

        self.cursor.execute(f"""
            INSERT INTO {self.schema}.SelectionOption
                (QuestionID, OptionNum, TextHTML, ScorePct, StatusCD, LastModUserID)
            VALUES (?, ?, ?, ?, 4, ?)
        """, (question_id, option_num, text_safe, score_pct, self.user_id))

        self.conn.commit()
        self.stats['options_created'] += 1

    def create_question_classification(self, question_id: int, topic_id: int,
                                        level_id: int, difficulty: int = 1) -> int:
        """Link question to topic and academic level. Returns QuestionClassificationID."""
        if self.dry_run:
            return 0

        # Ensure difficulty is valid (1-3)
        if pd.isna(difficulty) or not isinstance(difficulty, (int, float)):
            difficulty = 1
        difficulty = max(1, min(3, int(difficulty)))

        self.cursor.execute(f"""
            INSERT INTO {self.schema}.QuestionClassification
                (QuestionID, TopicID, AcademicLevelID, DifficultyLevelNum)
            OUTPUT INSERTED.QuestionClassificationID
            VALUES (?, ?, ?, ?)
        """, (question_id, topic_id, level_id, difficulty))

        classif_id = self.cursor.fetchone()[0]
        self.conn.commit()
        return classif_id

    def create_hint(self, question_id: int, hint_level: int, hint_html: str,
                    template_name: str) -> None:
        """Create a hint for a question.

        Args:
            question_id: The question ID
            hint_level: 1, 2, or 3
            hint_html: The hint text
            template_name: "Select One", "True/False", etc.
        """
        if not hint_html or pd.isna(hint_html):
            return

        hint_text = str(hint_html).strip()
        if not hint_text:
            return

        if self.dry_run:
            self.stats['hints_created'] += 1
            return

        # First create QuestionHint record
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.QuestionHint
                (QuestionID, HintLevelNum, StatusCD, CreatedUserID, LastModUserID)
            VALUES (?, ?, 4, ?, ?)
        """, (question_id, hint_level, self.user_id, self.user_id))

        # Then create HintReplacement with correct TemplateName and HTMLElementID
        # These must match valid entries in TemplateElement table
        self.cursor.execute(f"""
            INSERT INTO {self.schema}.HintReplacement
                (QuestionID, HintLevelNum, TemplateName, HTMLElementID, HintHTML,
                 CreatedUserID, LastModUserID)
            VALUES (?, ?, ?, 'question-text-content', ?, ?, ?)
        """, (question_id, hint_level, template_name, hint_text[:1000],
              self.user_id, self.user_id))

        self.conn.commit()
        self.stats['hints_created'] += 1

    def import_row(self, row: pd.Series) -> bool:
        """Import a single question row from standardized format. Returns True if imported."""
        # Get data using column names
        # Support both old format (TemplateID as number) and new format (QuestionType as text)
        item_id = row.get('ItemID')
        template_id = row.get('TemplateID')
        question_type = row.get('QuestionType')
        subject = row.get('Subject')
        category = row.get('Category')
        grade = row.get('Grade')
        topic = row.get('Topic')
        question_text = row.get('QuestionText')
        option1 = row.get('Option1')
        option2 = row.get('Option2')
        option3 = row.get('Option3')
        option4 = row.get('Option4')
        answer = row.get('Answer')
        level = row.get('Level')
        hint1 = row.get('Hint1')
        hint2 = row.get('Hint2')
        hint3 = row.get('Hint3')
        media_type = row.get('MediaType')  # P/VO/VONWQ

        # Skip if no item ID
        if pd.isna(item_id):
            return False

        external_id = str(item_id)

        # Resolve template ID from either format
        # New format: QuestionType = "Select One" / "Select All" / "True/False"
        # Old format: TemplateID = 1 / 2 / 3
        if question_type and not pd.isna(question_type):
            template_id = QUESTION_TYPE_MAP.get(str(question_type).strip(), None)
        elif template_id and not pd.isna(template_id):
            try:
                template_id = int(template_id)
            except (ValueError, TypeError):
                template_id = None

        # Skip word-list questions (TemplateID = 4)
        if template_id == 4 or template_id == TEMPLATE_WRITTEN:
            self.stats['questions_skipped_wordlist'] += 1
            return False

        # Skip if no question text
        if pd.isna(question_text) or not str(question_text).strip():
            return False

        # Check for duplicate
        if self.question_exists(external_id):
            self.stats['questions_skipped'] += 1
            return False

        try:
            # Map subject name using SUBJECT_MAP
            subject_raw = str(subject) if not pd.isna(subject) else "Unknown"
            subject_name = SUBJECT_MAP.get(subject_raw, subject_raw)

            # Map category using CATEGORY_CLEANUP (merge messy subcategories)
            category_name = str(category) if not pd.isna(category) else subject_name
            category_name = CATEGORY_CLEANUP.get(category_name, category_name)

            # Topic name as-is from spreadsheet
            topic_name = str(topic) if not pd.isna(topic) else category_name

            # Get or create hierarchy: Subject -> SubjectArea -> Topic
            subject_id = self.get_or_create_subject(subject_name)
            subject_area_id = self.get_or_create_subject_area(subject_id, category_name)
            topic_id = self.get_or_create_topic(subject_area_id, topic_name)

            # Academic level - derive stage from grade
            # Year 1-2 = Stage 1, Year 3-4 = Stage 2, Year 5-6 = Stage 3
            if pd.isna(grade) or str(grade).strip() == '':
                level_name = "Stage 1 - Year 1"
            else:
                try:
                    grade_int = int(float(grade))
                    stage = GRADE_TO_STAGE.get(grade_int, 1)
                    level_name = f"Stage {stage} - Year {grade_int}"
                except (ValueError, TypeError):
                    level_name = "Stage 1 - Year 1"
            level_id = self.get_or_create_academic_level(level_name)

            # Default to Select One if template wasn't resolved
            if template_id is None or (isinstance(template_id, float) and pd.isna(template_id)):
                template_id = TEMPLATE_SELECT_ONE

            # Parse correct answer(s) - handle various formats
            import re
            correct_answers = []
            if pd.isna(answer):
                correct_answers = [1]
            else:
                answer_str = str(answer).strip()

                # Handle T/F format (T→1, F→2 for True/False questions)
                if answer_str in ['T', 'True']:
                    correct_answers = [1]
                elif answer_str in ['F', 'False']:
                    correct_answers = [2]
                # Handle Excel date bug (2025-01-02 → answers [1, 2])
                elif '2025-' in answer_str:
                    match = re.search(r'2025-(\d+)-(\d+)', answer_str)
                    if match:
                        correct_answers = [int(match.group(1)), int(match.group(2))]
                        template_id = TEMPLATE_SELECT_ALL
                    else:
                        correct_answers = [1]
                # Check for multiple answers (e.g., "1 and 2", "1,2,3")
                elif re.search(r'\d\s*and\s*\d|\d\s*,\s*\d', answer_str, re.IGNORECASE):
                    # Multiple answers - extract all numbers
                    correct_answers = [int(x) for x in re.findall(r'\d+', answer_str)]
                    # Change template to Select All for multi-answer questions
                    template_id = TEMPLATE_SELECT_ALL
                else:
                    # Single numeric answer
                    try:
                        correct_answers = [int(float(answer_str))]
                    except (ValueError, TypeError):
                        correct_answers = [1]

            # Create question
            question_id = self.create_question(
                text_html=str(question_text),
                template_id=template_id,
                media_type=media_type,
                external_id=external_id
            )

            self.question_cache.add(external_id)
            self.item_question_map[external_id] = question_id

            # Save to SpreadsheetXRef
            self._save_xref(external_id, question_id, 'Question')

            # Create options - skip for True/False (template shows buttons automatically)
            options = [option1, option2, option3, option4]

            if template_id != TEMPLATE_TRUE_FALSE:
                for i, opt_text in enumerate(options, start=1):
                    # Skip empty options
                    if opt_text is None or pd.isna(opt_text):
                        continue
                    opt_str = str(opt_text).strip() if not isinstance(opt_text, bool) else ("True" if opt_text else "False")
                    if opt_str == '':
                        continue
                    self.create_selection_option(
                        question_id=question_id,
                        option_num=i,
                        text_html=opt_text,
                        is_correct=(i in correct_answers)
                    )
                    self._save_xref(external_id, question_id, 'SelectionOption',
                                    json.dumps({'OptionNum': i}))

            # Update CorrectAnswerText
            if not self.dry_run:
                if template_id == TEMPLATE_TRUE_FALSE:
                    # True/False: store "True" or "False"
                    if 1 in correct_answers:
                        correct_answer_text = "True"
                    else:
                        correct_answer_text = "False"
                elif template_id == TEMPLATE_SELECT_ALL:
                    # Select All: store option numbers ("1, 3")
                    correct_answer_text = ", ".join(str(n) for n in sorted(correct_answers))
                else:
                    # Select One: store the correct option text
                    correct_texts = []
                    for i, opt_text in enumerate(options, start=1):
                        if i in correct_answers and opt_text is not None and not pd.isna(opt_text):
                            if isinstance(opt_text, bool):
                                correct_texts.append("True" if opt_text else "False")
                            else:
                                correct_texts.append(str(opt_text))
                    correct_answer_text = ", ".join(correct_texts)[:200] if correct_texts else None

                if correct_answer_text:
                    self.cursor.execute(f"""
                        UPDATE {self.schema}.Question
                        SET CorrectAnswerText = ?
                        WHERE QuestionID = ?
                    """, (correct_answer_text, question_id))
                    self.conn.commit()

            # Create classification
            difficulty = level if not pd.isna(level) else 1
            try:
                difficulty = int(difficulty)
            except (ValueError, TypeError):
                difficulty = 1

            classif_id = self.create_question_classification(
                question_id=question_id,
                topic_id=topic_id,
                level_id=level_id,
                difficulty=difficulty
            )
            self._save_xref(external_id, question_id, 'QuestionClassification',
                            json.dumps({'QuestionClassificationID': classif_id}))

            # Create hints with correct template name
            template_name = TEMPLATE_NAMES.get(template_id, "Select One")

            for hint_num, hint_text in [(1, hint1), (2, hint2), (3, hint3)]:
                if hint_text and not pd.isna(hint_text):
                    self.create_hint(question_id, hint_num, hint_text, template_name)
                    self._save_xref(external_id, question_id, 'QuestionHint',
                                    json.dumps({'HintLevelNum': hint_num}))
                    self._save_xref(external_id, question_id, 'HintReplacement',
                                    json.dumps({'HintLevelNum': hint_num,
                                                'TemplateName': template_name,
                                                'HTMLElementID': 'question-text-content'}))

            return True

        except Exception as e:
            self.stats['errors'].append(f"Row {external_id}: {str(e)}")
            return False

    def reconnect(self):
        """Reconnect to database if connection dropped."""
        try:
            self.conn.close()
        except:
            pass
        print("    Reconnecting to database...")
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        time.sleep(1)

    def import_file(self, filepath: Path) -> dict:
        """Import all questions from standardized Excel file. Returns stats."""
        print(f"  Reading: {filepath}")
        # keep_default_na=False preserves 'None' text as string (not NaN)
        df = pd.read_excel(filepath, keep_default_na=False, na_values=[])
        print(f"  Found {len(df)} rows")

        count = 0
        batch_count = 0

        for idx, row in df.iterrows():
            try:
                if self.import_row(row):
                    count += 1
                    batch_count += 1

                    # Progress indicator
                    if count % 100 == 0:
                        print(f"    Imported {count} questions...")

                    # Small delay every 50 questions to avoid throttling
                    if batch_count >= 50:
                        time.sleep(0.3)
                        batch_count = 0

            except Exception as e:
                # Try to reconnect on connection errors
                if "Communication link failure" in str(e) or "connection" in str(e).lower():
                    print(f"    Connection error at row {idx}, reconnecting...")
                    self.reconnect()
                    # Retry this row
                    try:
                        if self.import_row(row):
                            count += 1
                    except Exception as e2:
                        self.stats['errors'].append(f"Row {idx}: {str(e2)}")
                else:
                    self.stats['errors'].append(f"Row {idx}: {str(e)}")

        print(f"  Completed: {count} questions imported")
        return self.stats


def print_stats(stats: dict, dry_run: bool = False):
    """Print import statistics."""
    prefix = "[DRY RUN] Would create" if dry_run else "Created"

    print("\n" + "=" * 60)
    print("IMPORT RESULTS")
    print("=" * 60)

    print(f"\n{prefix}:")
    print(f"  Subjects: {stats['subjects_created']}")
    print(f"  Subject Areas: {stats['subject_areas_created']}")
    print(f"  Topics: {stats['topics_created']}")
    print(f"  Academic Levels: {stats['levels_created']}")
    print(f"  Questions: {stats['questions_created']}")
    print(f"  Selection Options: {stats['options_created']}")
    print(f"  Hints: {stats['hints_created']}")

    if stats['questions_skipped']:
        print(f"\nSkipped (already exist): {stats['questions_skipped']}")

    if stats['questions_skipped_wordlist']:
        print(f"Skipped (word-list questions): {stats['questions_skipped_wordlist']}")

    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:  # Show first 10
            print(f"  ! {err}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk import questions from standardized Excel to database"
    )
    parser.add_argument(
        "filepath",
        type=Path,
        nargs='?',
        default=DEFAULT_FILE,
        help=f"Path to Excel file (default: {DEFAULT_FILE})"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be imported without actually doing it"
    )
    parser.add_argument(
        "--schema", "-s",
        default="DanTest",
        choices=SCHEMA_CONFIG.keys(),
        help="Database schema to import into (default: DanTest)"
    )

    args = parser.parse_args()

    if not args.filepath.exists():
        print(f"Error: {args.filepath} does not exist")
        print(f"Run standardize_spreadsheets.py first to create the standardized file.")
        return 1

    schema = args.schema
    user_id = SCHEMA_CONFIG[schema]

    print("Connecting to Azure...")
    conn = get_connection()
    print("Connected!")
    print(f"Schema: {schema}, UserID: {user_id}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    print(f"\nImporting from: {args.filepath}")

    # Log batch start to SystemEvent
    cursor = conn.cursor()
    if not args.dry_run:
        cursor.execute(f"""
            INSERT INTO {schema}.SystemEvent
                (EventTypeCD, MessageTypeCD, IsActive, MessageTxt,
                 RaisedByModuleName, RaisedByUserID, CreatedUTC)
            VALUES (121, 121, 1, ?, 'import_questions.py', ?, GETUTCDATE())
        """, (f"Batch load started: {args.filepath.name}", user_id))
        conn.commit()
        print("  SystemEvent: batch start logged")

    importer = QuestionImporter(conn, schema=schema, user_id=user_id,
                                dry_run=args.dry_run)
    stats = importer.import_file(args.filepath)

    print_stats(stats, args.dry_run)

    # Log batch end to SystemEvent
    if not args.dry_run:
        summary = (f"Batch load completed: {stats['questions_created']} created, "
                   f"{stats['questions_skipped']} skipped, "
                   f"{len(stats['errors'])} errors")
        cursor = importer.conn.cursor()
        cursor.execute(f"""
            INSERT INTO {schema}.SystemEvent
                (EventTypeCD, MessageTypeCD, IsActive, MessageTxt,
                 RaisedByModuleName, RaisedByUserID, CreatedUTC)
            VALUES (121, 121, 0, ?, 'import_questions.py', ?, GETUTCDATE())
        """, (summary, user_id))
        importer.conn.commit()
        print("  SystemEvent: batch end logged")

    # Close the importer's connection (may have reconnected during import)
    try:
        importer.conn.close()
    except Exception:
        pass  # Already closed or invalid
    return 0


if __name__ == "__main__":
    exit(main())
