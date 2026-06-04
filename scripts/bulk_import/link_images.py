#!/usr/bin/env python3
"""
Link uploaded images to questions based on filename convention.

Filename format: {questionID}-{type}.svg
  - 00110001-question.svg → Question.ImageBlobID
  - 00110001-answer1.svg → SelectionOption.ImageBlobID (OptionNum=1)
  - 00110001-answer2.svg → SelectionOption.ImageBlobID (OptionNum=2)
  - etc.

Usage:
    source venv/bin/activate
    python -m scripts.bulk_import.link_images
    python -m scripts.bulk_import.link_images --dry-run
"""

import argparse
import re
from collections import defaultdict

from .db_connect import get_connection


def get_blob_lookup(conn) -> dict:
    """Get mapping of filename → (BlobID, question_id, image_type) from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT BlobID, Filename
        FROM DanTest.Blob
        WHERE BlobTypeCD = 110  -- Images only
    """)

    lookup = {}
    for row in cursor.fetchall():
        blob_id, filename = row

        # Parse filename: 00110001-question.svg or 00110001-answer1.svg
        match = re.match(r'^(\d+)-(question|answer(\d+))\.', filename)
        if match:
            question_id = match.group(1)
            image_type = match.group(2)  # "question" or "answer1", "answer2", etc.
            answer_num = int(match.group(3)) if match.group(3) else None

            lookup[filename] = {
                'blob_id': blob_id,
                'question_id': question_id,
                'image_type': image_type,
                'answer_num': answer_num
            }

    return lookup


def get_question_lookup(conn) -> dict:
    """Get mapping of ItemID (Title) → QuestionID from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT QuestionID, Title
        FROM DanTest.Question
    """)

    lookup = {}
    for row in cursor.fetchall():
        question_id, title = row
        if title:
            # Store both with and without leading zeros
            title_str = str(title).strip()
            lookup[title_str] = question_id
            # Also try without leading zeros
            lookup[title_str.lstrip('0')] = question_id

    return lookup


def get_option_lookup(conn) -> dict:
    """Get mapping of (QuestionID, OptionNum) → SelectionOptionID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT QuestionID, OptionNum, ImageBlobID
        FROM DanTest.SelectionOption
    """)

    lookup = {}
    for row in cursor.fetchall():
        q_id, opt_num, current_blob = row
        lookup[(q_id, opt_num)] = {
            'has_image': current_blob is not None
        }

    return lookup


def update_question_image(conn, question_id: int, blob_id: int, dry_run: bool = False):
    """Link a question to an image."""
    if dry_run:
        return
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE DanTest.Question
        SET ImageBlobID = ?
        WHERE QuestionID = ?
    """, (blob_id, question_id))
    conn.commit()


def update_option_image(conn, question_id: int, option_num: int, blob_id: int, dry_run: bool = False):
    """Link a selection option to an image."""
    if dry_run:
        return
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE DanTest.SelectionOption
        SET ImageBlobID = ?
        WHERE QuestionID = ? AND OptionNum = ?
    """, (blob_id, question_id, option_num))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Link uploaded images to questions"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be linked without making changes"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("LINK IMAGES TO QUESTIONS")
    print("=" * 60)

    # Connect to database
    print("\nConnecting to Azure...")
    conn = get_connection()
    print("Connected!")

    # Load lookups
    print("\nLoading data...")
    blob_lookup = get_blob_lookup(conn)
    question_lookup = get_question_lookup(conn)

    print(f"  Images with valid naming: {len(blob_lookup)}")
    print(f"  Questions in database: {len(question_lookup) // 2}")  # Divided by 2 due to duplicate keys

    if args.dry_run:
        print("\n[DRY RUN - No changes will be made]")

    # Process links
    print("\n" + "-" * 60)
    print("Linking images to questions...")

    stats = {
        'question_linked': 0,
        'answer_linked': 0,
        'question_not_found': [],
        'option_not_found': [],
    }

    for filename, info in blob_lookup.items():
        blob_id = info['blob_id']
        q_id_str = info['question_id']
        image_type = info['image_type']
        answer_num = info['answer_num']

        # Find question
        db_question_id = question_lookup.get(q_id_str)
        if not db_question_id:
            # Try without leading zeros
            db_question_id = question_lookup.get(q_id_str.lstrip('0'))

        if not db_question_id:
            stats['question_not_found'].append(q_id_str)
            continue

        if image_type == 'question':
            # Link to Question.ImageBlobID
            update_question_image(conn, db_question_id, blob_id, args.dry_run)
            stats['question_linked'] += 1
            print(f"  {filename} → Question {q_id_str}")
        else:
            # Link to SelectionOption.ImageBlobID
            update_option_image(conn, db_question_id, answer_num, blob_id, args.dry_run)
            stats['answer_linked'] += 1
            print(f"  {filename} → Question {q_id_str} Option {answer_num}")

    # Summary
    print("\n" + "=" * 60)
    print("LINKING RESULTS")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN]")

    print(f"\nQuestion images linked: {stats['question_linked']}")
    print(f"Answer images linked: {stats['answer_linked']}")
    print(f"Total: {stats['question_linked'] + stats['answer_linked']}")

    # Show questions not found
    unique_not_found = list(set(stats['question_not_found']))
    if unique_not_found:
        print(f"\nQuestions not found in database: {len(unique_not_found)}")
        print("(These images have no matching question)")
        for qid in sorted(unique_not_found)[:10]:
            print(f"  - {qid}")
        if len(unique_not_found) > 10:
            print(f"  ... and {len(unique_not_found) - 10} more")

    conn.close()


if __name__ == "__main__":
    main()
