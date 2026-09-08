#!/usr/bin/env python3
"""
Import images from Airtable to Azure Blob Storage and link to questions.

This script:
1. Reads image attachments from Airtable "Graphics for Questions" base
2. Downloads images (SVG/JSON)
3. Uploads to Azure Blob Storage (devtest/images/)
4. Inserts Blob records in database
5. Links Question.ImageBlobID and SelectionOption.ImageBlobID

Usage:
    source venv/bin/activate
    az login
    python -m scripts.bulk_import.import_from_airtable --help
    python -m scripts.bulk_import.import_from_airtable --schema DevTest --dry-run
    python -m scripts.bulk_import.import_from_airtable --schema DevTest
    python -m scripts.bulk_import.import_from_airtable --schema DevTest --table "HSIE"
"""

import argparse
import os
import time
import tempfile
from pathlib import Path

import requests
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from .db_connect import get_connection

# Airtable config
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN', '')
AIRTABLE_BASE_ID = 'apptbIO1ziocd4RHA'

# Azure Storage config
STORAGE_ACCOUNT = "worldwiseaustg"

# Schema configs: schema name -> (container, user_id)
SCHEMA_CONFIG = {
    "DanTest": ("danassets", 2),
    "DevTest": ("devtestblobs", 8),
}

# All Airtable tables to process
AIRTABLE_TABLES = [
    'Graphics Library',
    'Statistics & Probability',
    'Measurement & Space',
    'Phonological Awareness',
    'Spelling',
    'Punctuation',
    'HSIE',
    'Science & technology',
    'Creative Arts',
    'PD H PE',
]

# Column name -> (blob name suffix, target field)
# Question images: {ItemID}-question.ext -> Question.ImageBlobID
# Answer images: {ItemID}-answer{N}.ext -> SelectionOption.ImageBlobID
# Hint images: {ItemID}-hint{N}.ext -> stored for future use
IMAGE_COLUMNS = {
    'Question Image SVG': ('question', 'question'),
    'Question Image JSON': ('question', 'question'),
    'Answer A Image': ('answer1', 'option'),
    'Answer B Image': ('answer2', 'option'),
    'Answer C Image': ('answer3', 'option'),
    'Answer D Image': ('answer4', 'option'),
    'Hint 1 Image': ('hint1', 'hint'),
    'Hint 2 Image': ('hint2', 'hint'),
    'Hint 3 Image': ('hint3', 'hint'),
}

# Content types by extension
CONTENT_TYPES = {
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.json': 'application/json',
    '.webp': 'image/webp',
}

# WebP conversion — matches Victor's converted library (native resolution, lossy).
WEBP_QUALITY = 85  # visually lossless for quiz images; ~90% smaller than raster-in-SVG


def convert_to_webp(src_path, file_ext):
    """If src is a raster PNG/JPG OR a 'fake' SVG (SVG wrapping an embedded base64 raster),
    convert it to a WebP file and return (webp_path, True). If it's a REAL vector SVG (no
    embedded raster) or a Lottie JSON, return (src_path, False) — leave it untouched.

    The embedded raster is the full-quality source, so no originals are needed and no
    quality is lost beyond WebP's lossy step at q85.
    """
    import base64
    import io
    import re
    from PIL import Image

    ext = file_ext.lower()
    img = None

    if ext in ('.png', '.jpg', '.jpeg'):
        img = Image.open(src_path)
    elif ext == '.svg':
        raw = open(src_path, 'rb').read()
        txt = raw.decode('utf-8', 'ignore')
        m = re.search(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)', txt)
        if not m:
            return src_path, False  # real vector SVG — leave alone
        img = Image.open(io.BytesIO(base64.b64decode(m.group(2))))
    else:
        return src_path, False  # json/gif/etc — leave alone

    webp_path = src_path + '.webp'
    img.convert('RGB').save(webp_path, 'WEBP', quality=WEBP_QUALITY, method=6)
    return webp_path, True


def get_airtable_records(table_name):
    """Fetch all records from an Airtable table."""
    headers = {'Authorization': f'Bearer {AIRTABLE_TOKEN}'}
    records = []
    offset = None

    while True:
        params = {'pageSize': 100}
        if offset:
            params['offset'] = offset

        response = requests.get(
            f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{requests.utils.quote(table_name)}',
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            print(f"  Error fetching {table_name}: {response.status_code}")
            break

        data = response.json()
        records.extend(data['records'])

        offset = data.get('offset')
        if not offset:
            break

        time.sleep(0.2)  # Rate limit

    return records


def download_attachment(url, dest_path):
    """Download an Airtable attachment to a local file."""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    return False


def blob_exists_in_db(cursor, schema, filename):
    """Check if an IMAGE blob with this filename already exists.

    MUST filter BlobTypeCD=110 (image). Audio blobs share the '{ItemID}-question'
    Filename base (different extension); matching on Filename alone would treat an
    existing AUDIO blob as a duplicate image and skip creating the image (the mirror
    of the voice-over collision bug fixed in ingest_voiceovers.blob_exists)."""
    cursor.execute(
        f"SELECT BlobID, FileTypeExtn FROM {schema}.Blob WHERE Filename = ? AND BlobTypeCD = 110",
        (filename,)
    )
    row = cursor.fetchone()
    return row is not None


def existing_image_blob(cursor, schema, filename):
    """Return (BlobID, FileTypeExtn) for an existing image blob, or None."""
    cursor.execute(
        f"SELECT BlobID, FileTypeExtn FROM {schema}.Blob WHERE Filename = ? AND BlobTypeCD = 110",
        (filename,)
    )
    row = cursor.fetchone()
    return (row[0], row[1]) if row else None


def update_blob_extn(cursor, conn, schema, blob_id, new_ext, user_id):
    """Update an existing Blob's FileTypeExtn (e.g. svg -> webp) after re-uploading
    the file to blob storage. Keeps the same BlobID so existing FK links are preserved."""
    cursor.execute(
        f"UPDATE {schema}.Blob SET FileTypeExtn = ?, LastModUserID = ?, LastModTime = GETDATE() "
        f"WHERE BlobID = ?",
        (new_ext, user_id, blob_id)
    )
    conn.commit()


def upload_to_blob_storage(blob_service, container_name, local_path, blob_name,
                           content_type):
    """Upload a file to Azure Blob Storage with correct content type."""
    container_client = blob_service.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)

    with open(local_path, 'rb') as f:
        blob_client.upload_blob(
            f,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )

    return blob_client.url


def insert_blob_record(cursor, conn, schema, name, filename, file_ext,
                       user_id):
    """Insert a Blob record. Returns BlobID."""
    cursor.execute(f"""
        INSERT INTO {schema}.Blob
            (BlobTypeCD, Name, Title, Filename, Path,
             StatusCD, CreatedUserID, LastModUserID, FileTypeExtn)
        OUTPUT INSERTED.BlobID
        VALUES (?, ?, ?, ?, 'images', 4, ?, ?, ?)
    """, (
        110 if file_ext != 'json' else 110,  # Both are images in this context
        name[:30],
        name[:1000],
        filename[:50],
        user_id,
        user_id,
        file_ext[:10],
    ))

    blob_id = cursor.fetchone()[0]
    conn.commit()
    return blob_id


def link_question_image(cursor, conn, schema, item_id, blob_id):
    """Link a blob to a question via ImageBlobID. Returns True if linked."""
    # Find QuestionID via SpreadsheetXRef
    cursor.execute(f"""
        SELECT QuestionID FROM {schema}.SpreadsheetXRef
        WHERE SpreadsheetRecordID = ? AND TableName = 'Question'
    """, (item_id,))
    row = cursor.fetchone()

    if not row:
        return False

    question_id = row[0]

    # Only update if not already set
    cursor.execute(f"""
        UPDATE {schema}.Question
        SET ImageBlobID = ?
        WHERE QuestionID = ? AND ImageBlobID IS NULL
    """, (blob_id, question_id))

    conn.commit()
    return cursor.rowcount > 0


def link_option_image(cursor, conn, schema, item_id, blob_id, option_num):
    """Link a blob to a selection option via ImageBlobID. Returns True if linked."""
    # Find QuestionID via SpreadsheetXRef
    cursor.execute(f"""
        SELECT QuestionID FROM {schema}.SpreadsheetXRef
        WHERE SpreadsheetRecordID = ? AND TableName = 'Question'
    """, (item_id,))
    row = cursor.fetchone()

    if not row:
        return False

    question_id = row[0]

    # Update the specific option
    cursor.execute(f"""
        UPDATE {schema}.SelectionOption
        SET ImageBlobID = ?
        WHERE QuestionID = ? AND OptionNum = ? AND ImageBlobID IS NULL
    """, (blob_id, question_id, option_num))

    conn.commit()
    return cursor.rowcount > 0


def process_record(record, cursor, conn, blob_service, schema, container_name,
                   user_id, dry_run, stats, convert_webp=False, replace_existing=False):
    """Process a single Airtable record."""
    fields = record['fields']
    item_id = str(fields.get('Which Question it refers to', '')).strip()

    if not item_id:
        stats['skipped_no_id'] += 1
        return

    for col_name, (suffix, target) in IMAGE_COLUMNS.items():
        attachments = fields.get(col_name, [])

        for attachment in attachments:
            orig_filename = attachment['filename']
            url = attachment['url']
            file_ext = Path(orig_filename).suffix.lower()

            if file_ext not in CONTENT_TYPES:
                stats['skipped_unsupported'] += 1
                continue

            blob_name_no_ext = f"{item_id}-{suffix}"

            # Check for duplicate (by base filename, image-type — collision-guarded)
            existing = existing_image_blob(cursor, schema, blob_name_no_ext)
            if existing:
                existing_id, existing_ext = existing
                # In replace mode: if the existing blob is a fake-SVG (or png/jpg) and we're
                # converting, re-upload as WebP + update the blob's extension IN PLACE (same
                # BlobID → existing question/option link is preserved). Otherwise skip.
                if not (replace_existing and convert_webp and (existing_ext or '').lower() in ('svg', 'png', 'jpg', 'jpeg')):
                    stats['skipped_duplicate'] += 1
                    continue
                if dry_run:
                    stats['would_replace'] = stats.get('would_replace', 0) + 1
                    continue
                # fall through to download+convert; we'll update instead of insert
            else:
                if dry_run:
                    stats['would_upload'] += 1
                    continue

            # Download from Airtable
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                tmp_path = tmp.name

            webp_path = None
            try:
                if not download_attachment(url, tmp_path):
                    stats['errors'].append(f"{item_id}: Failed to download {orig_filename}")
                    continue

                upload_path = tmp_path
                ext_no_dot = file_ext.lstrip('.')
                content_type = CONTENT_TYPES[file_ext]

                # Convert raster PNG/JPG and fake-SVG (raster-in-SVG) to WebP.
                # Real vector SVGs and Lottie JSON are left untouched.
                if convert_webp:
                    out_path, converted = convert_to_webp(tmp_path, file_ext)
                    if converted:
                        webp_path = out_path
                        upload_path = out_path
                        ext_no_dot = 'webp'
                        content_type = CONTENT_TYPES['.webp']
                        stats['converted_webp'] = stats.get('converted_webp', 0) + 1

                blob_filename = f"{blob_name_no_ext}.{ext_no_dot}"
                blob_path = f"images/{blob_filename}"

                # Upload to Azure Blob Storage (overwrite=True → replaces the old file bytes)
                upload_to_blob_storage(
                    blob_service, container_name, upload_path, blob_path,
                    content_type
                )

                if existing:
                    # REPLACE in place: same BlobID, just update the extension (svg -> webp).
                    # Existing question/option FK link is untouched. Old .svg blob file is left
                    # in storage (harmless, unreferenced) — nothing is deleted.
                    existing_id, _ = existing
                    update_blob_extn(cursor, conn, schema, existing_id, ext_no_dot, user_id)
                    stats['replaced'] = stats.get('replaced', 0) + 1
                else:
                    # Insert new Blob record + link
                    blob_id = insert_blob_record(
                        cursor, conn, schema,
                        name=blob_name_no_ext,
                        filename=blob_name_no_ext,
                        file_ext=ext_no_dot,
                        user_id=user_id
                    )
                    stats['uploaded'] += 1
                    if target == 'question':
                        if link_question_image(cursor, conn, schema, item_id, blob_id):
                            stats['linked_questions'] += 1
                    elif target == 'option':
                        option_num = int(suffix.replace('answer', ''))
                        if link_option_image(cursor, conn, schema, item_id, blob_id,
                                             option_num):
                            stats['linked_options'] += 1

            except Exception as e:
                stats['errors'].append(f"{item_id}: {str(e)[:100]}")
            finally:
                for p in (tmp_path, webp_path):
                    if p:
                        try:
                            os.unlink(p)
                        except OSError:
                            pass


def main():
    parser = argparse.ArgumentParser(
        description="Import images from Airtable to Azure Blob Storage"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be uploaded without actually doing it"
    )
    parser.add_argument(
        "--schema", "-s",
        default="DevTest",
        choices=SCHEMA_CONFIG.keys(),
        help="Database schema to import into (default: DevTest)"
    )
    parser.add_argument(
        "--table", "-t",
        default=None,
        help="Only process a specific Airtable table"
    )
    parser.add_argument(
        "--webp",
        action="store_true",
        help="Convert raster PNG/JPG and fake-SVG (raster-in-SVG) to WebP before upload "
             "(matches Victor's converted library; real vector SVGs + Lottie left untouched)"
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="With --webp: also re-convert images already in the DB as svg/png/jpg to WebP "
             "in place (same BlobID, link preserved). Without this, existing images are skipped."
    )

    args = parser.parse_args()

    # Load Airtable token from env
    global AIRTABLE_TOKEN
    if not AIRTABLE_TOKEN:
        # Try loading from .env file
        env_path = Path('.env')
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith('AIRTABLE_TOKEN='):
                    AIRTABLE_TOKEN = line.split('=', 1)[1].strip()
                    break

    if not AIRTABLE_TOKEN:
        print("Error: AIRTABLE_TOKEN not set. Add it to .env file.")
        return 1

    schema = args.schema
    container_name, user_id = SCHEMA_CONFIG[schema]

    print("Connecting to Azure...")
    credential = AzureCliCredential()
    blob_service = BlobServiceClient(
        f"https://{STORAGE_ACCOUNT}.blob.core.windows.net",
        credential=credential
    )
    conn = get_connection()
    cursor = conn.cursor()
    print(f"Connected! Schema: {schema}, Container: {container_name}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    # Determine which tables to process
    tables = [args.table] if args.table else AIRTABLE_TABLES

    stats = {
        'uploaded': 0,
        'linked_questions': 0,
        'linked_options': 0,
        'skipped_no_id': 0,
        'skipped_duplicate': 0,
        'skipped_unsupported': 0,
        'would_upload': 0,
        'errors': [],
    }

    for table in tables:
        print(f"\nProcessing: {table}")
        records = get_airtable_records(table)
        print(f"  {len(records)} records")

        for rec in records:
            process_record(rec, cursor, conn, blob_service, schema,
                          container_name, user_id, args.dry_run, stats,
                          convert_webp=args.webp, replace_existing=args.replace_existing)

        # Small delay between tables
        time.sleep(0.5)

    # Print results
    print("\n" + "=" * 60)
    print("IMPORT RESULTS")
    print("=" * 60)

    if args.dry_run:
        print(f"\n[DRY RUN] Would upload: {stats['would_upload']}")
        if stats.get('would_replace'):
            print(f"[DRY RUN] Would replace existing with WebP: {stats['would_replace']}")
    else:
        print(f"\nUploaded: {stats['uploaded']}")
        print(f"Replaced existing with WebP: {stats.get('replaced', 0)}")
        print(f"Converted to WebP: {stats.get('converted_webp', 0)}")
        print(f"Linked to questions: {stats['linked_questions']}")
        print(f"Linked to options: {stats['linked_options']}")

    print(f"Skipped (no ItemID): {stats['skipped_no_id']}")
    print(f"Skipped (duplicate): {stats['skipped_duplicate']}")
    print(f"Skipped (unsupported type): {stats['skipped_unsupported']}")

    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:
            print(f"  ! {err}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")

    conn.close()
    return 0


if __name__ == "__main__":
    exit(main())
