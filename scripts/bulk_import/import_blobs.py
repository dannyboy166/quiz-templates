#!/usr/bin/env python3
"""
Bulk import blobs (images, audio, video) to Azure.

This script:
1. Uploads files to Azure Blob Storage (danassets container for testing)
2. Inserts records into DanTest.Blob table
3. Checks for duplicates (by filename)
4. Reports stats

Usage:
    source venv/bin/activate
    az login
    python -m scripts.bulk_import.import_blobs --help
    python -m scripts.bulk_import.import_blobs audio/balloon-pop/  # upload a folder
    python -m scripts.bulk_import.import_blobs logo_256x256.png    # upload single file
    python -m scripts.bulk_import.import_blobs --dry-run audio/    # preview without uploading
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient

from .db_connect import get_connection

# Azure Storage config
STORAGE_ACCOUNT = "worldwiseaustg"

# Schema configs: schema name -> (container, user_id)
SCHEMA_CONFIG = {
    "DanTest": ("danassets", 2),
    "DevTest": ("devtestblobs", 8),
}

# BlobTypeCD values from ReferenceData
BLOB_TYPES = {
    # Images
    ".png": 110, ".jpg": 110, ".jpeg": 110, ".gif": 110, ".svg": 110, ".webp": 110,
    # Audio
    ".mp3": 111, ".wav": 111, ".ogg": 111, ".m4a": 111,
    # Video
    ".mp4": 112, ".webm": 112, ".mov": 112,
}


def get_blob_service():
    """Connect to Azure Blob Storage using CLI credentials."""
    credential = AzureCliCredential()
    account_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=credential)


def get_blob_type_cd(filepath: Path) -> int:
    """Get the BlobTypeCD for a file based on extension."""
    ext = filepath.suffix.lower()
    if ext not in BLOB_TYPES:
        raise ValueError(f"Unsupported file type: {ext}")
    return BLOB_TYPES[ext]


def file_exists_in_db(conn, schema: str, filename: str) -> bool:
    """Check if a blob with this filename already exists."""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT COUNT(*) FROM {schema}.Blob WHERE Filename = ?",
        (filename,)
    )
    count = cursor.fetchone()[0]
    return count > 0


def upload_file_to_storage(blob_service, filepath: Path, blob_path: str,
                           container_name: str) -> str:
    """Upload a file to Azure Blob Storage. Returns the URL."""
    container_client = blob_service.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_path)

    with open(filepath, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)

    return blob_client.url


def insert_blob_record(conn, schema: str, filename: str, path: str, blob_type_cd: int,
                       name: str = None, title: str = None, description: str = None,
                       file_ext: str = None, user_id: int = 2) -> int:
    """Insert a record into Blob table. Returns the new BlobID."""
    cursor = conn.cursor()

    cursor.execute(f"""
        INSERT INTO {schema}.Blob
            (BlobTypeCD, Name, Title, Description, Filename, Path,
             StatusCD, CreatedUserID, LastModUserID, FileTypeExtn)
        OUTPUT INSERTED.BlobID
        VALUES (?, ?, ?, ?, ?, ?, 4, ?, ?, ?)
    """, (
        blob_type_cd,
        name[:30] if name else None,  # varchar(30)
        title[:1000] if title else None,  # varchar(1000)
        description[:1000] if description else None,  # varchar(1000)
        filename[:50],  # nvarchar(50)
        path[:200],  # nvarchar(200)
        user_id,
        user_id,
        file_ext[:10] if file_ext else None,  # nvarchar(10)
    ))

    blob_id = cursor.fetchone()[0]
    conn.commit()
    return blob_id


def process_file(filepath: Path, blob_service, conn, schema: str,
                 container_name: str, user_id: int,
                 dry_run: bool = False, prefix: str = "") -> dict:
    """Process a single file. Returns stats dict."""
    filename = filepath.name
    file_ext = filepath.suffix.lower().lstrip(".")

    result = {
        "file": str(filepath),
        "status": "unknown",
        "blob_id": None,
        "url": None,
    }

    # Check file type
    try:
        blob_type_cd = get_blob_type_cd(filepath)
    except ValueError as e:
        result["status"] = "skipped"
        result["reason"] = str(e)
        return result

    # Check for duplicates
    if file_exists_in_db(conn, schema, filename):
        result["status"] = "duplicate"
        result["reason"] = f"Filename '{filename}' already exists in database"
        return result

    if dry_run:
        result["status"] = "would_upload"
        result["blob_type_cd"] = blob_type_cd
        return result

    # Build blob path (preserve folder structure)
    if prefix:
        blob_path = f"{prefix}/{filename}"
    else:
        blob_path = filename

    # Upload to storage
    try:
        url = upload_file_to_storage(blob_service, filepath, blob_path, container_name)
        result["url"] = url
    except Exception as e:
        result["status"] = "upload_failed"
        result["reason"] = str(e)
        return result

    # Insert database record
    try:
        # Use filename without extension as name/title
        name = filepath.stem[:30]
        blob_id = insert_blob_record(
            conn,
            schema=schema,
            filename=filename,
            path=url,
            blob_type_cd=blob_type_cd,
            name=name,
            title=filepath.stem,
            file_ext=file_ext,
            user_id=user_id,
        )
        result["status"] = "success"
        result["blob_id"] = blob_id
    except Exception as e:
        result["status"] = "db_failed"
        result["reason"] = str(e)
        return result

    return result


def process_path(path: Path, blob_service, conn, schema: str,
                 container_name: str, user_id: int,
                 dry_run: bool = False, recursive: bool = True) -> list:
    """Process a file or directory. Returns list of results."""
    results = []

    if path.is_file():
        result = process_file(path, blob_service, conn, schema, container_name,
                              user_id, dry_run)
        results.append(result)
    elif path.is_dir():
        # Get all files in directory
        pattern = "**/*" if recursive else "*"
        for filepath in path.glob(pattern):
            if filepath.is_file() and filepath.suffix.lower() in BLOB_TYPES:
                # Use relative path as prefix for blob storage
                rel_path = filepath.relative_to(path)
                prefix = str(rel_path.parent) if rel_path.parent != Path(".") else ""
                result = process_file(filepath, blob_service, conn, schema,
                                      container_name, user_id, dry_run, prefix)
                results.append(result)
    else:
        print(f"Error: {path} is not a file or directory")
        sys.exit(1)

    return results


def print_results(results: list):
    """Print summary of results."""
    success = [r for r in results if r["status"] == "success"]
    duplicates = [r for r in results if r["status"] == "duplicate"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] in ("upload_failed", "db_failed")]
    would_upload = [r for r in results if r["status"] == "would_upload"]

    print("\n" + "=" * 60)
    print("IMPORT RESULTS")
    print("=" * 60)

    if would_upload:
        print(f"\n[DRY RUN] Would upload {len(would_upload)} files:")
        for r in would_upload:
            print(f"  + {r['file']}")

    if success:
        print(f"\n✓ Successfully imported: {len(success)}")
        for r in success:
            print(f"  + {r['file']} → BlobID={r['blob_id']}")

    if duplicates:
        print(f"\n⊘ Skipped (already exists): {len(duplicates)}")
        for r in duplicates:
            print(f"  - {r['file']}")

    if skipped:
        print(f"\n○ Skipped (unsupported type): {len(skipped)}")
        for r in skipped:
            print(f"  - {r['file']}: {r.get('reason', '')}")

    if failed:
        print(f"\n✗ Failed: {len(failed)}")
        for r in failed:
            print(f"  ! {r['file']}: {r.get('reason', '')}")

    print("\n" + "-" * 60)
    total = len(results)
    print(f"Total files processed: {total}")
    if not would_upload:
        print(f"  Imported: {len(success)}")
        print(f"  Duplicates: {len(duplicates)}")
        print(f"  Skipped: {len(skipped)}")
        print(f"  Failed: {len(failed)}")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk import blobs to Azure Storage and database"
    )
    parser.add_argument(
        "path",
        type=Path,
        help="File or directory to import"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be uploaded without actually doing it"
    )
    parser.add_argument(
        "--no-recursive", "-R",
        action="store_true",
        help="Don't recurse into subdirectories"
    )
    parser.add_argument(
        "--schema", "-s",
        default="DanTest",
        choices=SCHEMA_CONFIG.keys(),
        help="Database schema to import into (default: DanTest)"
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: {args.path} does not exist")
        sys.exit(1)

    schema = args.schema
    container_name, user_id = SCHEMA_CONFIG[schema]

    print("Connecting to Azure...")
    print("(May open browser for authentication)")

    # Connect to services
    blob_service = get_blob_service()
    conn = get_connection()

    print(f"Connected!")
    print(f"Storage: {STORAGE_ACCOUNT}/{container_name}")
    print(f"Schema: {schema}, UserID: {user_id}")

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]")

    print(f"\nProcessing: {args.path}")

    # Process files
    results = process_path(
        args.path,
        blob_service,
        conn,
        schema=schema,
        container_name=container_name,
        user_id=user_id,
        dry_run=args.dry_run,
        recursive=not args.no_recursive
    )

    # Print results
    print_results(results)

    conn.close()


if __name__ == "__main__":
    main()
