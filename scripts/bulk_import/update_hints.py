"""
Add hints to existing questions in the database that don't have them yet.

Reads hints from the clean spreadsheets (master source of truth) and INSERTs
QuestionHint + HintReplacement records for questions that are already in the DB
but missing hints.

SAFETY:
- Dry-run by default (must pass --commit to write)
- Never overwrites existing hints
- Idempotent via SpreadsheetXRef duplicate detection
- SystemEvent audit trail
- Test on DanTest before DevTest

Usage:
    source venv/bin/activate
    az login

    # Preview what would be inserted (default = dry run)
    python -m scripts.bulk_import.update_hints --schema DanTest

    # Actually write to DanTest (sandbox)
    python -m scripts.bulk_import.update_hints --schema DanTest --commit

    # DevTest (only after Victor approves)
    python -m scripts.bulk_import.update_hints --schema DevTest --commit
"""

import argparse
import json
import os
import sys

import openpyxl
import pyodbc

from scripts.bulk_import.db_connect import get_connection

# === Configuration ===

SCHEMA_CONFIG = {
    "DanTest": 2,    # Dan's sandbox (UserID)
    "DevTest": 8,    # DevTest live portal (UserID)
}

TEMPLATE_NAMES = {
    1: "Select One",
    2: "Select All",
    3: "True/False",
    4: "Written",
    5: "Sort",
    6: "Link",
}

CLEAN_DIR = "data/questions/clean"

SHEET_TO_FILE = {
    "Phonological Awareness": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Phonics": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Spelling": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Punctuation": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Grammar": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Vocabulary": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Reading Comprehension": "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Number and Algebra": "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "Measurement & Space": "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "Statistics & Probability": "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "HSIE": "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
    "Science & technology": "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
    "Creative Arts": "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
    "PD H PE": "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
}


def load_item_question_map(cursor, schema):
    """Load ItemID → QuestionID mapping from SpreadsheetXRef."""
    cursor.execute(f"""
        SELECT SpreadsheetRecordID, QuestionID
        FROM {schema}.SpreadsheetXRef
        WHERE TableName = 'Question'
    """)
    mapping = {}
    for row in cursor.fetchall():
        mapping[str(row[0]).strip()] = row[1]
    return mapping


def load_questions_with_hints(cursor, schema):
    """Get set of QuestionIDs that already have hints."""
    cursor.execute(f"""
        SELECT DISTINCT QuestionID FROM {schema}.QuestionHint
    """)
    return {row[0] for row in cursor.fetchall()}


def load_question_templates(cursor, schema):
    """Get QuestionID → TemplateID mapping for all questions."""
    cursor.execute(f"""
        SELECT QuestionID, TemplateID FROM {schema}.Question
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}


def xref_exists(cursor, schema, item_id, question_id, table_name, key_json):
    """Check if a SpreadsheetXRef record already exists."""
    cursor.execute(f"""
        SELECT 1 FROM {schema}.SpreadsheetXRef
        WHERE SpreadsheetRecordID = ? AND QuestionID = ?
        AND TableName = ? AND TableRecordKeyJson = ?
    """, (item_id, question_id, table_name, key_json))
    return cursor.fetchone() is not None


def read_hints_from_spreadsheets():
    """Read all hints from the clean spreadsheets."""
    hints = {}  # ItemID -> {hint1, hint2, hint3}

    for sheet_name, filename in SHEET_TO_FILE.items():
        filepath = os.path.join(CLEAN_DIR, filename)
        wb = openpyxl.load_workbook(filepath, read_only=True)
        ws = wb[sheet_name]

        for row in ws.iter_rows(min_row=2):
            if not row[0].value:
                continue

            item_id = str(row[0].value).strip()
            h1 = str(row[16].value or "").strip() if len(row) > 16 else ""
            h2 = str(row[17].value or "").strip() if len(row) > 17 else ""
            h3 = str(row[18].value or "").strip() if len(row) > 18 else ""

            if h1:  # Only include if at least Hint1 exists
                hints[item_id] = {"hint1": h1, "hint2": h2, "hint3": h3}

        wb.close()

    return hints


def main():
    parser = argparse.ArgumentParser(description="Add hints to existing DB questions")
    parser.add_argument("--schema", default="DanTest", choices=["DanTest", "DevTest"],
                        help="Database schema (default: DanTest)")
    parser.add_argument("--commit", action="store_true",
                        help="Actually write to DB (default is dry-run)")
    args = parser.parse_args()

    schema = args.schema
    user_id = SCHEMA_CONFIG[schema]
    dry_run = not args.commit

    print("=" * 60)
    print("UPDATE HINTS")
    print(f"Schema: {schema} (UserID: {user_id})")
    print(f"Mode: {'DRY RUN — no changes will be made' if dry_run else '⚠️  LIVE — writing to database'}")
    print("=" * 60)

    if not dry_run:
        confirm = input("\n  Are you sure you want to write to the database? (yes/no): ")
        if confirm.lower() != "yes":
            print("  Aborted.")
            return

    # Connect
    print("\nConnecting to database...")
    conn = get_connection()
    cursor = conn.cursor()
    print("  Connected.")

    # Load mappings
    print("\nLoading data from database...")
    item_map = load_item_question_map(cursor, schema)
    print(f"  SpreadsheetXRef mappings: {len(item_map)}")

    existing_hints = load_questions_with_hints(cursor, schema)
    print(f"  Questions with existing hints: {len(existing_hints)}")

    template_map = load_question_templates(cursor, schema)
    print(f"  Questions with template IDs: {len(template_map)}")

    # Read spreadsheets
    print("\nReading hints from spreadsheets...")
    spreadsheet_hints = read_hints_from_spreadsheets()
    print(f"  Questions with hints in spreadsheets: {len(spreadsheet_hints)}")

    # SystemEvent: batch start
    if not dry_run:
        cursor.execute(f"""
            INSERT INTO {schema}.SystemEvent
                (EventTypeCD, MessageTypeCD, IsActive, MessageTxt,
                 RaisedByModuleName, RaisedByUserID, CreatedUTC)
            VALUES (121, 121, 1, ?, 'update_hints.py', ?, GETUTCDATE())
        """, (f"Hint update started for {schema}", user_id))
        conn.commit()

    # Process
    print("\nProcessing...")
    stats = {
        "hints_created": 0,
        "questions_updated": 0,
        "skipped_no_mapping": 0,
        "skipped_has_hints": 0,
        "skipped_empty": 0,
        "skipped_xref_exists": 0,
    }

    for item_id, hints in spreadsheet_hints.items():
        # Look up QuestionID
        question_id = item_map.get(item_id)
        if not question_id:
            stats["skipped_no_mapping"] += 1
            continue

        # Skip if already has hints
        if question_id in existing_hints:
            stats["skipped_has_hints"] += 1
            continue

        # Get template name
        template_id = template_map.get(question_id, 1)
        template_name = TEMPLATE_NAMES.get(template_id, "Select One")

        # Insert hints for each level
        question_got_hints = False
        for hint_num, hint_key in [(1, "hint1"), (2, "hint2"), (3, "hint3")]:
            hint_text = hints.get(hint_key, "").strip()
            if not hint_text:
                continue

            # Check idempotency via XRef
            hint_key_json = json.dumps({"HintLevelNum": hint_num})
            if not dry_run and xref_exists(cursor, schema, item_id, question_id,
                                           "QuestionHint", hint_key_json):
                stats["skipped_xref_exists"] += 1
                continue

            if not dry_run:
                # INSERT QuestionHint
                cursor.execute(f"""
                    INSERT INTO {schema}.QuestionHint
                        (QuestionID, HintLevelNum, StatusCD, CreatedUserID, LastModUserID)
                    VALUES (?, ?, 4, ?, ?)
                """, (question_id, hint_num, user_id, user_id))

                # INSERT HintReplacement
                cursor.execute(f"""
                    INSERT INTO {schema}.HintReplacement
                        (QuestionID, HintLevelNum, TemplateName, HTMLElementID, HintHTML,
                         CreatedUserID, LastModUserID)
                    VALUES (?, ?, ?, 'question-text-content', ?, ?, ?)
                """, (question_id, hint_num, template_name, hint_text[:1000],
                      user_id, user_id))

                # Track in SpreadsheetXRef
                if not xref_exists(cursor, schema, item_id, question_id,
                                   "QuestionHint", hint_key_json):
                    cursor.execute(f"""
                        INSERT INTO {schema}.SpreadsheetXRef
                            (SpreadsheetRecordID, QuestionID, TableName, TableRecordKeyJson,
                             CreatedUserID, LastModUserID)
                        VALUES (?, ?, 'QuestionHint', ?, ?, ?)
                    """, (item_id, question_id, hint_key_json, user_id, user_id))

                replacement_key_json = json.dumps({
                    "HintLevelNum": hint_num,
                    "TemplateName": template_name,
                    "HTMLElementID": "question-text-content",
                })
                if not xref_exists(cursor, schema, item_id, question_id,
                                   "HintReplacement", replacement_key_json):
                    cursor.execute(f"""
                        INSERT INTO {schema}.SpreadsheetXRef
                            (SpreadsheetRecordID, QuestionID, TableName, TableRecordKeyJson,
                             CreatedUserID, LastModUserID)
                        VALUES (?, ?, 'HintReplacement', ?, ?, ?)
                    """, (item_id, question_id, replacement_key_json, user_id, user_id))

                conn.commit()

            stats["hints_created"] += 1
            question_got_hints = True

        if question_got_hints:
            stats["questions_updated"] += 1

    # SystemEvent: batch end
    if not dry_run:
        summary = (f"Hint update completed: {stats['questions_updated']} questions updated, "
                   f"{stats['hints_created']} hints created")
        cursor.execute(f"""
            INSERT INTO {schema}.SystemEvent
                (EventTypeCD, MessageTypeCD, IsActive, MessageTxt,
                 RaisedByModuleName, RaisedByUserID, CreatedUTC)
            VALUES (121, 121, 0, ?, 'update_hints.py', ?, GETUTCDATE())
        """, (summary, user_id))
        conn.commit()

    # Summary
    print(f"\n{'='*60}")
    prefix = "[DRY RUN] Would create" if dry_run else "Created"
    print(f"  {prefix}: {stats['hints_created']} hints across {stats['questions_updated']} questions")
    print(f"  Skipped (already has hints): {stats['skipped_has_hints']}")
    print(f"  Skipped (no DB mapping): {stats['skipped_no_mapping']}")
    print(f"  Skipped (empty hints): {stats['skipped_empty']}")
    print(f"  Skipped (XRef exists): {stats['skipped_xref_exists']}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    main()
