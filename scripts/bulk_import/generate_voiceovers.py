#!/usr/bin/env python3
"""
Generate voice over MP3s for questions using ElevenLabs API.

Usage:
    source venv/bin/activate

    # Test batch of 20 random questions
    python -m scripts.bulk_import.generate_voiceovers --test 20

    # Generate for specific QIDs
    python -m scripts.bulk_import.generate_voiceovers --qids 7590 124 5212

    # Dry run (show text that would be sent to API, no generation)
    python -m scripts.bulk_import.generate_voiceovers --test 20 --dry-run

    # Full bulk generation (all questions needing audio)
    python -m scripts.bulk_import.generate_voiceovers --all

    # Resume bulk generation (skip already generated)
    python -m scripts.bulk_import.generate_voiceovers --all --resume
"""

import os
import re
import sys
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

from .db_connect import get_connection

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "cupfa8uelkW7cWxLMRa7")

# ElevenLabs API settings (tested and finalized 4 May 2026)
API_SETTINGS = {
    "model_id": "eleven_flash_v2_5",
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.9,
        "use_speaker_boost": False,
    },
    "speed": 0.85,
}

# Output directory
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "voiceovers"

# Template IDs
TEMPLATE_SELECT_ONE = 1
TEMPLATE_SELECT_ALL = 2
TEMPLATE_TRUE_FALSE = 3

# Keywords that mean we should NOT read options aloud
NO_READ_OPTIONS_KEYWORDS = [
    "spelling", "correct spelling", "homophone", "homophones", "spelt"
]


# =============================================================================
# Text transformations
# =============================================================================

def fix_jammed_text(text):
    """Add space where punctuation meets number: 'dots?15' -> 'dots? 15'"""
    return re.sub(r'([?.!,;:])(\d)', r'\1 \2', text)


def underscores_to_blank(text):
    """Replace sequences of underscores with the word 'blank'."""
    return re.sub(r'_{2,}', 'blank', text)


def math_operators_to_words(text):
    """Convert math operators to spoken words."""
    # = ___ -> "equals what"
    text = re.sub(r'=\s*_{2,}', 'equals what', text)
    # = (at end or before punctuation)
    text = re.sub(r'\s*=\s*$', ' equals', text)
    text = re.sub(r'\s*=\s*(?=[?.!])', ' equals', text)
    # Standalone = between numbers/words
    text = re.sub(r'\s*=\s*', ' equals ', text)
    # + between numbers
    text = re.sub(r'(\d)\s*\+\s*(\d)', r'\1 plus \2', text)
    # + between words/dollars (e.g., "two dollars + one dollar")
    text = re.sub(r'\s*\+\s*', ' plus ', text)
    # - between numbers (minus)
    text = re.sub(r'(\d)\s*-\s*(\d)', r'\1 minus \2', text)
    # × or x between numbers (times)
    text = re.sub(r'(\d)\s*[×x]\s*(\d)', r'\1 times \2', text)
    # ÷ between numbers
    text = re.sub(r'(\d)\s*÷\s*(\d)', r'\1 divided by \2', text)
    return text


def number_to_words(n):
    """Convert integer 0-9999 to words. Uses Australian 'and'."""
    if n < 0 or n > 9999:
        return str(n)

    ones = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
            'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
            'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy',
            'eighty', 'ninety']

    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + ('' if n % 10 == 0 else ' ' + ones[n % 10])
    if n < 1000:
        remainder = n % 100
        if remainder == 0:
            return ones[n // 100] + ' hundred'
        return ones[n // 100] + ' hundred and ' + number_to_words(remainder)
    # 1000-9999
    thousands = n // 1000
    remainder = n % 1000
    result = ones[thousands] + ' thousand'
    if remainder == 0:
        return result
    if remainder < 100:
        return result + ' and ' + number_to_words(remainder)
    return result + ' ' + number_to_words(remainder)


def numbers_to_words(text):
    """Convert standalone numbers 0-9999 to words. Skip numbers inside <break> tags."""
    # Protect break tags
    breaks = []
    def save_break(m):
        breaks.append(m.group(0))
        return f"__BREAK{len(breaks)-1}__"
    text = re.sub(r'<break[^>]*>', save_break, text)

    # Handle special numbers first
    # Triple zero (Australian emergency number)
    text = re.sub(r'\b000\b', 'triple zero', text)
    # Repeated digits like 123, 567 are fine as regular numbers

    # Handle decimal numbers (e.g., 3.5 -> three point five)
    def replace_decimal(m):
        whole = int(m.group(1))
        decimal_part = m.group(2)
        result = number_to_words(whole) + ' point '
        result += ' '.join(number_to_words(int(d)) for d in decimal_part)
        return result
    text = re.sub(r'\b(\d{1,4})\.(\d+)\b', replace_decimal, text)

    # Convert standalone numbers (not part of larger numbers, not inside tags)
    def replace_num(m):
        n = int(m.group(0))
        if 0 <= n <= 9999:
            return number_to_words(n)
        return m.group(0)

    text = re.sub(r'\b\d{1,4}\b', replace_num, text)

    # Restore break tags
    for i, b in enumerate(breaks):
        text = text.replace(f"__BREAK{i}__", b)

    return text


def cents_to_words(text):
    """Convert '10c' to 'ten cents'. Leave dollar signs as-is."""
    def replace_cents(m):
        n = int(m.group(1))
        word = number_to_words(n)
        return word + (' cent' if n == 1 else ' cents')
    return re.sub(r'\b(\d{1,4})c\b', replace_cents, text)


def dollars_to_words(text):
    """Convert '$5' to 'five dollars', '$1' to 'one dollar'."""
    def replace_dollars(m):
        n = int(m.group(1))
        word = number_to_words(n)
        return word + (' dollar' if n == 1 else ' dollars')
    return re.sub(r'\$(\d{1,4})\b', replace_dollars, text)


def time_to_words(text):
    """Convert time formats like '2:30' to 'two thirty', '02:30:00' to 'two thirty'."""
    # 24h format with seconds: 02:30:00 -> two thirty
    def replace_full_time(m):
        h = int(m.group(1))
        mins = int(m.group(2))
        if mins == 0:
            return number_to_words(h) + " o'clock"
        return number_to_words(h) + ' ' + number_to_words(mins)
    text = re.sub(r'\b(\d{1,2}):(\d{2}):00\b', replace_full_time, text)
    # Simple time: 2:30 -> two thirty
    def replace_simple_time(m):
        h = int(m.group(1))
        mins = int(m.group(2))
        if mins == 0:
            return number_to_words(h) + " o'clock"
        return number_to_words(h) + ' ' + number_to_words(mins)
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', replace_simple_time, text)
    return text


def ordinals_to_words(text):
    """Convert '1st', '2nd', '3rd', '4th' etc. to spoken words."""
    ordinal_map = {
        1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth',
        6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth',
        11: 'eleventh', 12: 'twelfth', 13: 'thirteenth', 14: 'fourteenth',
        15: 'fifteenth', 16: 'sixteenth', 17: 'seventeenth', 18: 'eighteenth',
        19: 'nineteenth', 20: 'twentieth', 21: 'twenty first', 22: 'twenty second',
        23: 'twenty third', 24: 'twenty fourth', 25: 'twenty fifth',
        30: 'thirtieth', 31: 'thirty first',
    }
    def replace_ordinal(m):
        n = int(m.group(1))
        if n in ordinal_map:
            return ordinal_map[n]
        return m.group(0)  # leave as-is if not in map
    return re.sub(r'\b(\d{1,2})(?:st|nd|rd|th)\b', replace_ordinal, text)


def strip_parenthetical_units(text):
    """Remove parenthetical unit abbreviations like (cm), (m), (kg), (km), (L), (mL)."""
    return re.sub(r'\s*\((?:cm|m|km|kg|g|L|mL|mm)\)', '', text)


def units_to_words(text):
    """Convert unit abbreviations to spoken words in options."""
    unit_map = {
        'cm': 'centimetres', 'mm': 'millimetres', 'km': 'kilometres',
        'm': 'metres', 'kg': 'kilograms', 'g': 'grams',
        'L': 'litres', 'mL': 'millilitres',
    }
    # Match number + unit: "5 cm" or "5cm"
    def replace_unit(m):
        return m.group(1) + ' ' + unit_map[m.group(2)]
    # Order matters — check longer units first (cm before m, mL before L, km before m)
    for unit in ['cm', 'mm', 'km', 'mL', 'kg', 'm', 'g', 'L']:
        text = re.sub(r'(\d)\s*' + re.escape(unit) + r'\b', lambda m, u=unit: m.group(1) + ' ' + unit_map[u], text)
    return text


def strip_tf_endings(text):
    """Remove existing 'True or false?' endings including typos."""
    # Match variations: true or false, true or fasle, true or flase, etc.
    text = re.sub(
        r'\s*[Tt]rue\s+or\s+[Ff](?:alse|asle|lase)\s*[?.!]?\s*$',
        '',
        text
    )
    return text.strip()


def strip_abcd_markers(text):
    """Remove (a)(b)(c)(d) markers from question text."""
    return re.sub(r'\([a-dA-D]\)\s*', '', text)


def fix_counting_options(text):
    """Convert '1's (ones)' format to just 'ones'."""
    return re.sub(r"\d+'s\s*\((\w+)\)", r'\1', text)


def uppercase_single_letters(text):
    """Uppercase standalone single letters in text (Vonnie drops lowercase ones)."""
    def upper_letter(m):
        return m.group(1) + m.group(2).upper() + m.group(3)
    # Match single letter surrounded by word boundaries, but not inside tags
    return re.sub(r'(^|[\s,])\b([a-z])\b([\s,?.!]|$)', upper_letter, text)


def clean_text_for_speech(text):
    """Apply all text transformations in order."""
    text = time_to_words(text)  # FIRST — before fix_jammed_text splits "2:30" into "2: 30"
    text = fix_jammed_text(text)
    text = underscores_to_blank(text)
    text = strip_parenthetical_units(text)
    text = math_operators_to_words(text)
    text = dollars_to_words(text)
    text = cents_to_words(text)
    text = units_to_words(text)
    text = ordinals_to_words(text)
    text = strip_tf_endings(text)
    text = strip_abcd_markers(text)
    text = fix_counting_options(text)
    # Numbers to words AFTER math operators (so "8 plus 5" not "eight plus five" too early)
    text = numbers_to_words(text)
    # Clean up multiple spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def clean_option_for_speech(text):
    """Clean an option text for reading aloud."""
    text = fix_counting_options(text)
    text = uppercase_single_letters(text)
    text = time_to_words(text)
    text = dollars_to_words(text)
    text = cents_to_words(text)
    text = units_to_words(text)
    text = ordinals_to_words(text)
    text = numbers_to_words(text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


# =============================================================================
# SSML construction
# =============================================================================

def should_read_options(question_text, options):
    """Decide if we should read the options aloud."""
    if not options:
        return False
    text_lower = question_text.lower()
    for keyword in NO_READ_OPTIONS_KEYWORDS:
        if keyword in text_lower:
            return False
    # Don't read options if any option has an image (image-based answers)
    if any(o.get("image_blob_id") for o in options):
        return False
    return True


def is_yes_no(options):
    """Check if options are just YES/NO."""
    if len(options) < 2:
        return False
    texts = {o["text"].strip().upper() for o in options if o.get("text")}
    return texts == {"YES", "NO"}


def build_ssml(question_text, template_id, options):
    """Build the full SSML text to send to ElevenLabs."""
    cleaned = clean_text_for_speech(question_text)

    # Lead-in pause
    ssml = f'<break time="0.3s" /> {cleaned}'

    if template_id == TEMPLATE_TRUE_FALSE:
        # True/False format
        # Make sure it ends with proper punctuation before adding T/F
        if not ssml.rstrip().endswith(('?', '.', '!')):
            ssml = ssml.rstrip() + '.'
        ssml += ' <break time="0.6s" /> True? <break time="0.3s" /> Or false?'

    elif is_yes_no(options):
        # Yes/No format
        if not ssml.rstrip().endswith(('?', '.', '!')):
            ssml = ssml.rstrip() + '?'
        ssml += ' <break time="0.6s" /> Yes? <break time="0.3s" /> Or no?'

    elif should_read_options(question_text, options):
        # Read options aloud
        cleaned_opts = [clean_option_for_speech(o["text"]) for o in options if o.get("text")]
        if cleaned_opts:
            ssml += ' <break time="1.0s" /> '
            for i, opt in enumerate(cleaned_opts):
                if i == len(cleaned_opts) - 1 and i > 0:
                    ssml += f', <break time="0.5s" /> or {opt}?'
                elif i > 0:
                    ssml += f', <break time="0.5s" /> {opt}'
                else:
                    ssml += opt

    return ssml


# =============================================================================
# ElevenLabs API
# =============================================================================

def generate_audio(ssml_text, output_path):
    """Generate MP3 from text using ElevenLabs API."""
    import requests

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": ssml_text,
        "model_id": API_SETTINGS["model_id"],
        "voice_settings": API_SETTINGS["voice_settings"],
        "speed": API_SETTINGS["speed"],
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"ElevenLabs API error {response.status_code}: {response.text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    return len(response.content)


# =============================================================================
# Database queries
# =============================================================================

def get_questions_needing_audio(conn, qids=None, limit=None, exclude_qids=None):
    """Fetch questions that need voice overs."""
    cursor = conn.cursor()

    if qids:
        placeholders = ','.join('?' for _ in qids)
        cursor.execute(f"""
            SELECT q.QuestionID, q.TextHTML, q.TemplateID,
                   x.SpreadsheetRecordID as ItemID
            FROM DevTest.Question q
            LEFT JOIN DevTest.SpreadsheetXRef x
                ON x.QuestionID = q.QuestionID AND x.TableName = 'Question'
            WHERE q.QuestionID IN ({placeholders})
            ORDER BY q.QuestionID
        """, qids)
    else:
        exclude_clause = ""
        params = []
        if exclude_qids:
            placeholders = ','.join('?' for _ in exclude_qids)
            exclude_clause = f"AND q.QuestionID NOT IN ({placeholders})"
            params = list(exclude_qids)

        limit_clause = f"TOP {limit}" if limit else ""
        # Random order for test batches, consistent order for --all (so --resume works)
        order = "NEWID()" if limit else "q.QuestionID"
        cursor.execute(f"""
            SELECT {limit_clause} q.QuestionID, q.TextHTML, q.TemplateID,
                   x.SpreadsheetRecordID as ItemID
            FROM DevTest.Question q
            LEFT JOIN DevTest.SpreadsheetXRef x
                ON x.QuestionID = q.QuestionID AND x.TableName = 'Question'
            WHERE q.PlayAudioOnRenderFlag = 1
            AND q.ReaderBlobID IS NULL
            {exclude_clause}
            ORDER BY {order}
        """, params)

    questions = []
    for row in cursor.fetchall():
        questions.append({
            "qid": row[0],
            "text": row[1],
            "template_id": row[2],
            "item_id": row[3],
        })
    return questions


def get_options(conn, qid):
    """Get selection options for a question."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT OptionNum, TextHTML, ImageBlobID
        FROM DevTest.SelectionOption
        WHERE QuestionID = ?
        ORDER BY OptionNum
    """, (qid,))
    return [{"num": r[0], "text": r[1], "image_blob_id": r[2]} for r in cursor.fetchall()]


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate voice over MP3s for questions")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", type=int, metavar="N", help="Generate N random test questions")
    group.add_argument("--qids", type=int, nargs="+", help="Generate for specific QuestionIDs")
    group.add_argument("--all", action="store_true", help="Generate for ALL questions needing audio")
    parser.add_argument("--batch", type=int, metavar="N", help="Stop after generating N files (use with --all --resume)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show SSML without generating")
    parser.add_argument("--resume", action="store_true", help="Skip already generated files")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="Output directory")

    args = parser.parse_args()

    if not args.dry_run and not ELEVENLABS_API_KEY:
        print("Error: ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    print("Connecting to database...")
    conn = get_connection()

    # Get questions
    if args.test:
        questions = get_questions_needing_audio(conn, limit=args.test)
        print(f"Selected {len(questions)} random questions for testing")
    elif args.qids:
        questions = get_questions_needing_audio(conn, qids=args.qids)
        print(f"Found {len(questions)} questions")
    else:
        questions = get_questions_needing_audio(conn)
        print(f"Found {len(questions)} questions needing audio")

    if not questions:
        print("No questions to process!")
        return

    # Process
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    total_chars = 0
    total_bytes = 0
    generated = 0
    skipped = 0
    errors = 0

    for i, q in enumerate(questions):
        qid = q["qid"]
        item_id = q["item_id"] or f"QID{qid}"
        template_id = q["template_id"]

        # Build filename using ItemID convention
        filename = f"{item_id}-question.mp3"
        output_path = output_dir / filename

        # Skip if already exists and resuming
        if args.resume and output_path.exists():
            skipped += 1
            continue

        # Get options
        options = get_options(conn, qid)

        # Build SSML
        ssml = build_ssml(q["text"], template_id, options)
        total_chars += len(ssml)

        # Template name for display
        template_names = {1: "Select One", 2: "Select All", 3: "True/False"}
        tname = template_names.get(template_id, f"Template {template_id}")

        if args.dry_run:
            print(f"\n[{i+1}/{len(questions)}] QID {qid} ({tname}) -> {filename}")
            print(f"  Original: {q['text'][:80]}")
            print(f"  SSML: {ssml[:120]}...")
            if options:
                opt_texts = [o['text'] for o in options]
                print(f"  Options: {opt_texts}")
                yn = is_yes_no(options)
                read = should_read_options(q['text'], options)
                print(f"  Yes/No: {yn}, Read options: {read}")
        else:
            # Check batch limit
            if args.batch and generated >= args.batch:
                print(f"\nBatch limit reached ({args.batch}). Run again with --resume to continue.")
                break

            try:
                size = generate_audio(ssml, output_path)
                total_bytes += size
                generated += 1
                print(f"  [{generated}/{args.batch or len(questions)}] QID {qid} ({tname}) -> {filename} ({size//1024}KB)")
            except Exception as e:
                errors += 1
                print(f"  [ERROR] QID {qid} ({tname}): {e}")

            # Rate limit: ~2 requests/sec to be safe
            if i < len(questions) - 1:
                time.sleep(0.5)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total questions: {len(questions)}")
    print(f"Total characters: {total_chars:,}")
    if not args.dry_run:
        print(f"Generated: {generated}")
        print(f"Skipped (existing): {skipped}")
        print(f"Errors: {errors}")
        print(f"Total size: {total_bytes // 1024:,} KB ({total_bytes // (1024*1024):.1f} MB)")
    print(f"Output: {output_dir}")

    conn.close()


if __name__ == "__main__":
    main()
