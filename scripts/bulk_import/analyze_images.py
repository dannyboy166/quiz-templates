#!/usr/bin/env python3
"""
Analyze which images are needed for questions and what's missing.

This script:
1. Reads the standardized spreadsheet to find all ImageFile references
2. Checks which images already exist in DanTest.Blob
3. Reports what's missing (need to download from Google Drive)
4. Shows which questions will be linked to which images

Usage:
    source venv/bin/activate
    python -m scripts.bulk_import.analyze_images
"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

from .db_connect import get_connection

SPREADSHEET_PATH = Path("data/questions/standardized/ALL_QUESTIONS_STANDARDIZED.xlsx")
IMAGES_DIR = Path("data/images")  # Where to put downloaded images


def get_existing_blobs(conn) -> dict:
    """Get all existing blob filenames and their IDs from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT BlobID, Filename
        FROM DanTest.Blob
        WHERE BlobTypeCD = 110  -- Images only
    """)
    return {row[1]: row[0] for row in cursor.fetchall()}


def analyze_spreadsheet() -> dict:
    """Analyze the spreadsheet for image requirements."""
    print(f"Reading: {SPREADSHEET_PATH}")
    df = pd.read_excel(SPREADSHEET_PATH)

    # Get all ImageFile values and which questions use them
    image_to_questions = defaultdict(list)

    for _, row in df.iterrows():
        image_file = row.get("ImageFile")
        item_id = row.get("ItemID")

        if pd.notna(image_file) and str(image_file).strip():
            filename = str(image_file).strip()
            image_to_questions[filename].append(item_id)

    return dict(image_to_questions)


def check_local_files(image_filenames: list) -> dict:
    """Check which images exist locally in data/images/."""
    found = {}
    missing = []

    if not IMAGES_DIR.exists():
        return {"found": {}, "missing": image_filenames}

    for filename in image_filenames:
        # Check for exact match and common variations
        possible_paths = [
            IMAGES_DIR / filename,
            IMAGES_DIR / filename.lower(),
            IMAGES_DIR / filename.upper(),
        ]

        found_path = None
        for path in possible_paths:
            if path.exists():
                found_path = path
                break

        if found_path:
            found[filename] = found_path
        else:
            missing.append(filename)

    return {"found": found, "missing": missing}


def main():
    print("=" * 60)
    print("IMAGE ANALYSIS FOR QUESTION IMPORT")
    print("=" * 60)

    # Connect to database
    print("\nConnecting to Azure...")
    conn = get_connection()
    print("Connected!")

    # Get existing blobs from database
    existing_blobs = get_existing_blobs(conn)
    print(f"\nImages already in database: {len(existing_blobs)}")

    # Analyze spreadsheet
    image_to_questions = analyze_spreadsheet()
    total_unique_images = len(image_to_questions)
    total_questions_with_images = sum(len(q) for q in image_to_questions.values())

    print(f"\nSpreadsheet analysis:")
    print(f"  Questions referencing images: {total_questions_with_images}")
    print(f"  Unique image files needed: {total_unique_images}")

    # Categorize images
    already_in_db = []
    need_to_upload = []

    for filename in image_to_questions.keys():
        if filename in existing_blobs:
            already_in_db.append(filename)
        else:
            need_to_upload.append(filename)

    print(f"\n" + "-" * 60)
    print("STATUS:")
    print(f"  Already in database: {len(already_in_db)}")
    print(f"  Need to upload: {len(need_to_upload)}")

    # Check local files
    local_check = check_local_files(need_to_upload)
    found_locally = local_check["found"]
    missing_completely = local_check["missing"]

    print(f"\nOf the {len(need_to_upload)} images to upload:")
    print(f"  Found in data/images/: {len(found_locally)}")
    print(f"  Missing (need from Google Drive): {len(missing_completely)}")

    # Show what's missing
    if missing_completely:
        print(f"\n" + "=" * 60)
        print("IMAGES TO DOWNLOAD FROM GOOGLE DRIVE:")
        print("=" * 60)
        print(f"\nDownload these {len(missing_completely)} files to: {IMAGES_DIR}/")
        print()

        # Group by pattern/prefix for easier finding
        prefixes = defaultdict(list)
        for filename in sorted(missing_completely):
            prefix = filename.split("_")[0] if "_" in filename else "other"
            prefixes[prefix].append(filename)

        for prefix, files in sorted(prefixes.items()):
            print(f"\n  [{prefix}] ({len(files)} files)")
            for f in files[:5]:  # Show first 5 of each group
                question_count = len(image_to_questions[f])
                print(f"    - {f}  (used by {question_count} questions)")
            if len(files) > 5:
                print(f"    ... and {len(files) - 5} more")

    # Save full list to file
    if missing_completely:
        missing_list_path = Path("data/images_needed.txt")
        missing_list_path.parent.mkdir(parents=True, exist_ok=True)
        with open(missing_list_path, "w") as f:
            f.write("# Images needed from Google Drive\n")
            f.write(f"# Download to: {IMAGES_DIR.absolute()}/\n")
            f.write(f"# Total: {len(missing_completely)} files\n\n")
            for filename in sorted(missing_completely):
                f.write(f"{filename}\n")
        print(f"\nFull list saved to: {missing_list_path}")

    # Show next steps
    print(f"\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)

    if found_locally:
        print(f"\n1. Upload {len(found_locally)} local images:")
        print(f"   python -m scripts.bulk_import.import_blobs {IMAGES_DIR}/")

    if missing_completely:
        print(f"\n2. Download missing images from Google Drive to:")
        print(f"   {IMAGES_DIR.absolute()}/")
        print(f"   (see data/images_needed.txt for full list)")

    print(f"\n3. After all images are uploaded, run:")
    print(f"   python -m scripts.bulk_import.link_images")
    print(f"   (This links BlobIDs to questions)")

    conn.close()


if __name__ == "__main__":
    main()
