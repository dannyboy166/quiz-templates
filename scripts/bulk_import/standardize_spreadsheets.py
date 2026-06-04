#!/usr/bin/env python3
"""
Standardize question spreadsheets into a consistent format for bulk import.

This script:
1. Reads original spreadsheets (different column layouts)
2. Maps to a standard format
3. Detects template type (Select One, True/False, etc.)
4. Parses hints into separate columns
5. Outputs clean standardized files

Usage:
    source venv/bin/activate
    python -m scripts.bulk_import.standardize_spreadsheets
"""

import pandas as pd
import re
from pathlib import Path
from typing import Optional

# Paths
ORIGINAL_DIR = Path("data/questions/original")
OUTPUT_DIR = Path("data/questions/standardized")

# Standard column names (output format)
STANDARD_COLUMNS = [
    "ItemID",           # Unique question identifier
    "TemplateID",       # 1=Select One, 2=Select All, 3=True/False, 4=Written, 5=Sort, 6=Link
    "Subject",          # e.g., "English", "Maths"
    "Category",         # e.g., "Phonics", "Numbers"
    "Grade",            # e.g., 1, 2, "Year 1"
    "Topic",            # Sub-category / topic name
    "QuestionText",     # The question itself
    "Option1",          # Answer option 1
    "Option2",          # Answer option 2
    "Option3",          # Answer option 3
    "Option4",          # Answer option 4
    "Answer",           # Correct answer (1, 2, 3, or 4)
    "Level",            # Difficulty level (1, 2, 3)
    "MediaType",        # P, VO, or VONWQ
    "ImageRequired",    # Y or N
    "ImageDescription",  # Image description/brief for Georgia
    "Hint1",            # First hint
    "Hint2",            # Second hint
    "Hint3",            # Third hint
    "Notes",            # Internal notes
]

# Column mappings for different file formats
# Format: output_column -> input_column_index

ENGLISH_MAPPING = {
    "ItemID": 0,
    "Subject": 1,
    "Category": 2,
    "Grade": 3,
    "Topic": 4,  # Also contains question text in some rows
    "ImageDescription": 5,  # Previous image file
    "Option1": 6,
    "Option2": 7,
    "Option3": 8,
    "Option4": 9,
    "Answer": 10,
    "Level": 11,
    "ImageRequired": 12,
    "MediaType": 13,
    "Notes": 14,
    "Hints": 15,  # Will be parsed into Hint1, Hint2, Hint3
}

MATHS_MAPPING = {
    "ItemID": 0,
    "Subject": 1,
    "Category": 2,
    "Grade": 3,
    "Topic": 4,
    "NewImageNo": 5,  # Extra column in Math file
    "ImageDescription": 6,  # Previous image file
    "Option1": 7,
    "Option2": 8,
    "Option3": 9,
    "Option4": 10,
    "Answer": 11,
    "Level": 12,
    "ImageRequired": 13,
    "MediaType": 14,
    "Notes": 15,
    "Hints": 16,
}


def detect_file_format(df: pd.DataFrame) -> dict:
    """Detect which column mapping to use based on header row."""
    # Check row 1 (header row) for "New Image No." column
    if len(df) > 1:
        header_row = df.iloc[1]
        for i, val in enumerate(header_row):
            if pd.notna(val) and "New Image No" in str(val):
                return MATHS_MAPPING
    return ENGLISH_MAPPING


def parse_hints(hint_text: str) -> tuple:
    """Parse hints text into separate H1, H2, H3 values."""
    if pd.isna(hint_text) or not hint_text:
        return None, None, None

    hint_text = str(hint_text).strip()

    # Handle special cases
    if hint_text == '"':  # Just a quote mark means "same as above"
        return None, None, None

    hints = [None, None, None]

    # Try to parse H1, H2, H3 patterns
    # Patterns like "H1 - hint text" or "H1: hint text" or "H1 hint text"
    patterns = [
        r'H1\s*[-:.]?\s*(.+?)(?=H2|$)',
        r'H2\s*[-:.]?\s*(.+?)(?=H3|$)',
        r'H3\s*[-:.]?\s*(.+?)$',
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, hint_text, re.IGNORECASE | re.DOTALL)
        if match:
            hints[i] = match.group(1).strip()

    # If no H1/H2/H3 patterns found, treat whole text as H1
    if hints[0] is None and hint_text and hint_text != '"':
        hints[0] = hint_text

    return tuple(hints)


def detect_template_type(row: pd.Series, mapping: dict) -> int:
    """Detect template type based on options and answer format."""
    opt1_idx = mapping.get("Option1")
    opt2_idx = mapping.get("Option2")
    opt3_idx = mapping.get("Option3")
    opt4_idx = mapping.get("Option4")

    opt1 = row.iloc[opt1_idx] if opt1_idx is not None and opt1_idx < len(row) else None
    opt2 = row.iloc[opt2_idx] if opt2_idx is not None and opt2_idx < len(row) else None
    opt3 = row.iloc[opt3_idx] if opt3_idx is not None and opt3_idx < len(row) else None
    opt4 = row.iloc[opt4_idx] if opt4_idx is not None and opt4_idx < len(row) else None

    # Convert to string for comparison
    def to_str(val):
        if pd.isna(val):
            return None
        # Handle booleans
        if isinstance(val, bool):
            return "true" if val else "false"
        s = str(val).strip().lower()
        # Treat empty string as None
        return None if s == '' else s

    s1, s2, s3, s4 = to_str(opt1), to_str(opt2), to_str(opt3), to_str(opt4)

    # True/False detection
    if s1 in ('true', 'false', '1', '0') and s2 in ('true', 'false', '1', '0'):
        if s3 is None and s4 is None:
            return 3  # True/False template

    # If we have options, it's Select One (standard MC)
    if s1 is not None and s2 is not None:
        return 1  # Select One

    # No options - might be embedded in question text (still Select One)
    # or might be Written answer - we'll mark as 4 and handle later
    if s1 is None and s2 is None:
        return 4  # Written/Embedded

    return 1  # Default to Select One


def parse_embedded_options(question_text: str) -> tuple:
    """
    Try to parse options embedded in question text.
    Format: "at / if / is / on" or "option1  /  option2  /  option3  /  option4"

    Returns: (cleaned_question, option1, option2, option3, option4)
    """
    if not question_text:
        return question_text, None, None, None, None

    # Check if text looks like embedded options (contains " / ")
    if "  /  " in question_text or " / " in question_text:
        # Split by various slash patterns
        parts = re.split(r'\s*/\s*', question_text)
        parts = [p.strip() for p in parts if p.strip()]

        if 2 <= len(parts) <= 5:
            # This looks like embedded options
            # The question might be the first part if it's longer, or missing
            if len(parts) == 4:
                # Just 4 options, no question text
                return None, parts[0], parts[1], parts[2], parts[3]
            elif len(parts) == 5:
                # First part is question, rest are options
                return parts[0], parts[1], parts[2], parts[3], parts[4] if len(parts) > 4 else None

    return question_text, None, None, None, None


def extract_question_text(topic_cell: str, has_item_id: bool) -> tuple:
    """
    Extract topic and question text from the combined Topic column.

    In these spreadsheets, the Topic column contains:
    - Topic name in category header rows (no ItemID)
    - Question text in question rows (has ItemID)

    Returns: (topic_name, question_text)
    """
    if pd.isna(topic_cell):
        return None, None

    text = str(topic_cell).strip()

    if has_item_id:
        # This row has an ItemID, so this is question text
        return None, text
    else:
        # No ItemID, so this is a topic/category header
        return text, None


def process_sheet(df: pd.DataFrame, mapping: dict, default_subject: str,
                  default_category: str) -> pd.DataFrame:
    """Process a single sheet into standardized format."""
    rows = []
    current_topic = None
    current_subject = default_subject
    current_category = default_category
    current_grade = None

    # Skip header rows (usually rows 0-1)
    start_row = 2

    for idx in range(start_row, len(df)):
        row = df.iloc[idx]

        # Get ItemID
        item_id = row.iloc[mapping["ItemID"]] if mapping["ItemID"] < len(row) else None
        has_item_id = pd.notna(item_id) and str(item_id).strip() != ''

        # Get topic/question from the combined column
        topic_col = mapping["Topic"]
        topic_cell = row.iloc[topic_col] if topic_col < len(row) else None

        # Update running values from category header rows
        subject = row.iloc[mapping["Subject"]] if mapping["Subject"] < len(row) else None
        category = row.iloc[mapping["Category"]] if mapping["Category"] < len(row) else None
        grade = row.iloc[mapping["Grade"]] if mapping["Grade"] < len(row) else None

        if pd.notna(subject) and str(subject).strip():
            current_subject = str(subject).strip()
        if pd.notna(category) and str(category).strip():
            current_category = str(category).strip()
        if pd.notna(grade):
            current_grade = grade

        # Extract topic vs question text
        extracted_topic, question_text = extract_question_text(topic_cell, has_item_id)
        if extracted_topic:
            current_topic = extracted_topic

        # Skip non-question rows
        if not has_item_id:
            continue

        # Skip rows without question text
        if not question_text:
            continue

        # Get other fields safely
        def get_val(col_name):
            if col_name not in mapping:
                return None
            col_idx = mapping[col_name]
            if col_idx >= len(row):
                return None
            try:
                val = row.iloc[col_idx]
                # Handle NaN and empty strings
                if pd.isna(val):
                    return None
                if isinstance(val, str) and val.strip() == '':
                    return None
                # Convert booleans to strings (Excel TRUE/FALSE)
                if isinstance(val, bool):
                    return "True" if val else "False"
                return val
            except Exception:
                return None

        # Parse hints
        hints_raw = get_val("Hints")
        hint1, hint2, hint3 = parse_hints(hints_raw)

        # Detect template type
        template_id = detect_template_type(row, mapping)

        # Get options
        opt1 = get_val("Option1")
        opt2 = get_val("Option2")
        opt3 = get_val("Option3")
        opt4 = get_val("Option4")

        # If no options but template detected as Written (4), try parsing embedded options
        if template_id == 4 and opt1 is None and opt2 is None:
            parsed_q, emb1, emb2, emb3, emb4 = parse_embedded_options(question_text)
            if emb1 and emb2:  # Successfully parsed embedded options
                template_id = 1  # Change to Select One
                opt1, opt2, opt3, opt4 = emb1, emb2, emb3, emb4
                # If we got a cleaned question, use it; otherwise keep original
                if parsed_q:
                    question_text = parsed_q

        # Build standardized row
        std_row = {
            "ItemID": item_id,
            "TemplateID": template_id,
            "Subject": current_subject,
            "Category": current_category,
            "Grade": current_grade,
            "Topic": current_topic,
            "QuestionText": question_text,
            "Option1": opt1,
            "Option2": opt2,
            "Option3": opt3,
            "Option4": opt4,
            "Answer": get_val("Answer"),
            "Level": get_val("Level"),
            "MediaType": get_val("MediaType"),
            "ImageRequired": get_val("ImageRequired"),
            "ImageDescription": get_val("ImageDescription"),
            "Hint1": hint1,
            "Hint2": hint2,
            "Hint3": hint3,
            "Notes": get_val("Notes"),
        }

        rows.append(std_row)

    return pd.DataFrame(rows, columns=STANDARD_COLUMNS)


def process_file(filepath: Path) -> pd.DataFrame:
    """Process an entire Excel file with multiple sheets."""
    print(f"\nProcessing: {filepath.name}")

    xl = pd.ExcelFile(filepath)
    all_rows = []

    for sheet_name in xl.sheet_names:
        print(f"  Sheet: {sheet_name}")
        # keep_default_na=False prevents "None" text from becoming NaN
        df = pd.read_excel(filepath, sheet_name=sheet_name, header=None,
                          keep_default_na=False, na_values=[])

        # Detect column mapping
        mapping = detect_file_format(df)
        mapping_name = "MATHS" if mapping == MATHS_MAPPING else "ENGLISH"
        print(f"    Using {mapping_name} mapping ({len(df)} rows)")

        # Process sheet
        std_df = process_sheet(df, mapping, sheet_name, sheet_name)
        print(f"    Extracted {len(std_df)} questions")

        all_rows.append(std_df)

    # Combine all sheets
    combined = pd.concat(all_rows, ignore_index=True)
    return combined


def analyze_results(df: pd.DataFrame):
    """Print analysis of standardized data."""
    print(f"\n{'='*60}")
    print("ANALYSIS")
    print('='*60)

    print(f"\nTotal questions: {len(df)}")

    print(f"\nBy Template:")
    template_names = {1: "Select One", 2: "Select All", 3: "True/False", 4: "Written", 5: "Sort", 6: "Link"}
    for tid, count in df["TemplateID"].value_counts().sort_index().items():
        print(f"  {template_names.get(tid, tid)}: {count}")

    print(f"\nBy Subject:")
    for subj, count in df["Subject"].value_counts().items():
        print(f"  {subj}: {count}")

    print(f"\nHints coverage:")
    has_hint1 = df["Hint1"].notna().sum()
    has_hint2 = df["Hint2"].notna().sum()
    has_hint3 = df["Hint3"].notna().sum()
    print(f"  With Hint1: {has_hint1} ({100*has_hint1/len(df):.1f}%)")
    print(f"  With Hint2: {has_hint2} ({100*has_hint2/len(df):.1f}%)")
    print(f"  With Hint3: {has_hint3} ({100*has_hint3/len(df):.1f}%)")

    print(f"\nMissing options (may be embedded in question):")
    no_options = df[(df["Option1"].isna()) & (df["Option2"].isna())]
    print(f"  Questions without Option1 and Option2: {len(no_options)}")

    if len(no_options) > 0:
        print(f"  Sample questions without options:")
        for _, row in no_options.head(3).iterrows():
            print(f"    [{row['ItemID']}] {str(row['QuestionText'])[:60]}...")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all original files
    files = list(ORIGINAL_DIR.glob("*.xlsx"))

    if not files:
        print(f"No Excel files found in {ORIGINAL_DIR}")
        return

    print(f"Found {len(files)} files to process")

    all_data = []

    for filepath in files:
        df = process_file(filepath)
        all_data.append(df)

        # Save individual standardized file
        output_name = filepath.stem.replace(" ", "_") + "_standardized.xlsx"
        output_path = OUTPUT_DIR / output_name
        df.to_excel(output_path, index=False)
        print(f"  Saved: {output_path}")

    # Combine all into one master file
    combined = pd.concat(all_data, ignore_index=True)
    master_path = OUTPUT_DIR / "ALL_QUESTIONS_STANDARDIZED.xlsx"
    combined.to_excel(master_path, index=False)
    print(f"\nSaved combined file: {master_path}")

    # Analyze
    analyze_results(combined)


if __name__ == "__main__":
    main()
