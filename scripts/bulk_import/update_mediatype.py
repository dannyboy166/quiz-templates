#!/usr/bin/env python3
"""
Update existing questions with MediaType from spreadsheet.

This adds [MediaType: VO/VONWQ/P] prefix to TeacherNotes and sets
PlayAudioOnRenderFlag = 1 for voice-over questions.

Usage:
    source venv/bin/activate
    python -m scripts.bulk_import.update_mediatype --dry-run
    python -m scripts.bulk_import.update_mediatype
"""

import argparse
from pathlib import Path

import pandas as pd

from .db_connect import get_connection

DEFAULT_FILE = Path("data/questions/standardized/ALL_QUESTIONS_STANDARDIZED.xlsx")


def main():
    parser = argparse.ArgumentParser(
        description="Update existing questions with MediaType"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview without making changes"
    )
    args = parser.parse_args()

    print("Reading spreadsheet...")
    df = pd.read_excel(DEFAULT_FILE)
    print(f"Found {len(df)} rows")

    # Build lookup: ItemID -> MediaType
    media_lookup = {}
    for _, row in df.iterrows():
        item_id = row.get('ItemID')
        media_type = row.get('MediaType')
        if pd.notna(item_id) and pd.notna(media_type):
            mt = str(media_type).strip().upper()
            if mt in ['VO', 'VONWQ', 'P']:
                media_lookup[str(item_id)] = mt

    print(f"Questions with MediaType: {len(media_lookup)}")
    print(f"  - VO: {sum(1 for v in media_lookup.values() if v == 'VO')}")
    print(f"  - VONWQ: {sum(1 for v in media_lookup.values() if v == 'VONWQ')}")
    print(f"  - P: {sum(1 for v in media_lookup.values() if v == 'P')}")

    if args.dry_run:
        print("\n[DRY RUN - No changes made]")
        return

    print("\nConnecting to database...")
    conn = get_connection()
    cursor = conn.cursor()
    print("Connected!")

    # Get all questions
    cursor.execute("""
        SELECT QuestionID, Title, TeacherNotes, PlayAudioOnRenderFlag
        FROM DanTest.Question
    """)
    questions = cursor.fetchall()
    print(f"\nUpdating {len(questions)} questions...")

    updated = 0
    for q_id, title, notes, play_audio in questions:
        if title not in media_lookup:
            continue

        mt = media_lookup[title]
        new_play_audio = 1 if mt in ['VO', 'VONWQ'] else 0

        # Add MediaType prefix to notes if not already there
        prefix = f"[MediaType: {mt}]"
        if notes and prefix not in notes:
            new_notes = f"{prefix} {notes}"
        elif not notes:
            new_notes = prefix
        else:
            new_notes = notes  # Already has prefix

        # Only update if something changed
        if new_notes != notes or new_play_audio != play_audio:
            cursor.execute("""
                UPDATE DanTest.Question
                SET TeacherNotes = ?, PlayAudioOnRenderFlag = ?
                WHERE QuestionID = ?
            """, (new_notes[:4000], new_play_audio, q_id))
            updated += 1

            if updated % 500 == 0:
                conn.commit()
                print(f"  Updated {updated} questions...")

    conn.commit()
    conn.close()

    print(f"\nDone! Updated {updated} questions with MediaType")


if __name__ == "__main__":
    main()
