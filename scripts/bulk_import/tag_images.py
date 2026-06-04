#!/usr/bin/env python3
"""
Auto-tag images using Claude Vision API.

This script:
1. Reads all images from Blob table (configurable schema)
2. Downloads each from Azure Blob Storage
3. Sends to Claude Vision API for tagging
4. Saves tags to Blob.Description field

Cost: ~$5-15 for ~1,800 images

Usage:
    source venv/bin/activate
    export ANTHROPIC_API_KEY="your-key-here"
    python -m scripts.bulk_import.tag_images --schema DevTest
    python -m scripts.bulk_import.tag_images --schema DevTest --dry-run
    python -m scripts.bulk_import.tag_images --schema DevTest --limit 10
"""

import os
import sys
import argparse
import base64
import time
import io
from pathlib import Path

import anthropic
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient

try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False

from .db_connect import get_connection

# Azure config
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
STORAGE_ACCOUNT = "worldwiseaustg"

# Schema configs: schema name -> container name
SCHEMA_CONFIG = {
    "DanTest": "danassets",
    "DevTest": "devtestblobs",
}

# Claude config
MODEL = "claude-haiku-4-5-20251001"  # Cheapest option, good for image tagging
MAX_TOKENS = 200

# Rate limiting
DELAY_BETWEEN_CALLS = 0.5  # seconds


def get_blob_service():
    """Connect to Azure Blob Storage."""
    credential = AzureCliCredential()
    account_url = f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=credential)


def download_blob_to_bytes(blob_service, blob_path: str, container_name: str,
                           filename: str = None, extension: str = None) -> bytes:
    """Download a blob and return its bytes."""
    if blob_path.startswith("http"):
        # Full URL - extract blob name
        blob_name = blob_path.split(f"/{container_name}/")[-1]
    elif "/" not in blob_path and filename:
        # Relative folder (e.g., "images") - construct full blob path
        ext = (extension or "png").lstrip(".")
        blob_name = f"{blob_path}/{filename}.{ext}"
    else:
        blob_name = blob_path

    container_client = blob_service.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)

    return blob_client.download_blob().readall()


def convert_svg_to_png(svg_bytes: bytes) -> bytes:
    """Convert SVG bytes to PNG bytes."""
    if not HAS_CAIROSVG:
        raise ValueError("cairosvg not installed - cannot convert SVG")

    png_bytes = cairosvg.svg2png(bytestring=svg_bytes)
    return png_bytes


def get_image_description(client: anthropic.Anthropic, image_bytes: bytes,
                          filename: str, media_type: str = "image/png",
                          question_text: str = None) -> str:
    """Send image to Claude and get an accessible description (alt text)."""

    # Convert to base64
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    if question_text:
        prompt = f"""This image is used in an educational question for primary school students.

The question is: "{question_text}"

Write a short, clear description of this image suitable for screen reader alt text (for visually impaired students). The description should help a student understand what the image shows in the context of the question.

Rules:
- 1-2 sentences maximum
- Describe what is shown, not what to do
- Include relevant details (numbers, text, colours, objects) that help answer the question
- Do NOT include the question text itself
- Do NOT start with "Image of" or "Picture of"

Description:"""
    else:
        prompt = """This image is used in an educational platform for primary school students.

Write a short, clear description of this image suitable for screen reader alt text (for visually impaired students).

Rules:
- 1-2 sentences maximum
- Describe what is shown clearly
- Include relevant details (numbers, text, colours, objects)
- Do NOT start with "Image of" or "Picture of"

Description:"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        description = response.content[0].text.strip()
        # Clean up - remove quotes if Claude wraps it
        description = description.strip('"\'')
        return description

    except Exception as e:
        print(f"    Error tagging {filename}: {e}")
        return None


def get_untagged_images(conn, schema: str) -> list:
    """Get all image blobs that don't have tags yet, with linked question text if available."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT b.BlobID, b.Filename, b.Path, b.FileTypeExtn,
               q.TextHTML, q.Title
        FROM {schema}.Blob b
        LEFT JOIN {schema}.Question q ON q.ImageBlobID = b.BlobID
        WHERE b.BlobTypeCD = 110  -- Images only
          AND (b.Description IS NULL OR b.Description = '')
        ORDER BY b.BlobID
    """)

    images = []
    for row in cursor.fetchall():
        images.append({
            "blob_id": row[0],
            "filename": row[1],
            "path": row[2],
            "extension": row[3] or "png",
            "question_text": row[4],
            "question_title": row[5],
        })

    return images


def get_media_type(extension: str) -> str:
    """Get MIME type from file extension."""
    ext = extension.lower().lstrip(".")
    types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return types.get(ext, "image/png")


def update_blob_tags(conn_holder: dict, blob_id: int, tags: str, schema: str):
    """Save tags to Blob.Description field with auto-reconnect."""
    for attempt in range(MAX_RETRIES):
        try:
            cursor = conn_holder["conn"].cursor()
            cursor.execute(f"""
                UPDATE {schema}.Blob
                SET Description = ?
                WHERE BlobID = ?
            """, (tags[:1000], blob_id))  # Description is varchar(1000)
            conn_holder["conn"].commit()
            return True
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"\n    DB connection lost, reconnecting (attempt {attempt + 2}/{MAX_RETRIES})...", end=" ")
                time.sleep(RETRY_DELAY)
                try:
                    conn_holder["conn"].close()
                except:
                    pass
                conn_holder["conn"] = get_connection()
                print("OK")
            else:
                raise e
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Auto-tag images using Claude Vision API"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would be tagged without making API calls"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="Limit number of images to process (for testing)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Tag local files in data/images/ instead of downloading from Azure"
    )
    parser.add_argument(
        "--schema", "-s",
        default="DevTest",
        choices=SCHEMA_CONFIG.keys(),
        help="Database schema to use (default: DevTest)"
    )

    args = parser.parse_args()

    schema = args.schema
    container_name = SCHEMA_CONFIG[schema]

    # Check for API key (check .env file first, then environment)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key and not args.dry_run:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("\nTo get an API key:")
        print("  1. Go to https://console.anthropic.com/")
        print("  2. Create an account or sign in")
        print("  3. Go to API Keys and create a new key")
        print("  4. Run: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    print("=" * 60)
    print("IMAGE AUTO-TAGGING")
    print("=" * 60)
    print(f"Schema: {schema}, Container: {container_name}")

    # Connect to services
    print("\nConnecting to Azure...")
    conn_holder = {"conn": get_connection()}
    blob_service = get_blob_service()
    print("Connected!")

    # Get untagged images
    images = get_untagged_images(conn_holder["conn"], schema)
    total = len(images)

    if args.limit > 0:
        images = images[:args.limit]

    print(f"\nFound {total} untagged images")
    if args.limit > 0:
        print(f"Processing first {args.limit} only (--limit)")

    if args.dry_run:
        print("\n[DRY RUN - No API calls will be made]")
        print("\nImages that would be tagged:")
        for img in images[:20]:
            print(f"  - {img['filename']}")
        if len(images) > 20:
            print(f"  ... and {len(images) - 20} more")

        # Estimate cost
        estimated_cost = len(images) * 0.005  # ~$0.005 per image
        print(f"\nEstimated cost: ${estimated_cost:.2f}")
        return

    if not images:
        print("No untagged images found!")
        return

    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)

    # Process images
    # NOTE: This is resumable! Each image is committed to DB immediately.
    # If the script crashes, just run it again - it only fetches images
    # where Description IS NULL, so already-tagged images are skipped.
    print(f"\nTagging {len(images)} images...")
    print("(Resumable - if it crashes, just run again to continue)")
    print("-" * 60)

    success = 0
    failed = 0
    consecutive_errors = 0

    for i, img in enumerate(images, 1):
        filename = img["filename"]
        print(f"[{i}/{len(images)}] {filename}...", end=" ", flush=True)

        try:
            # Download image
            image_bytes = download_blob_to_bytes(
                blob_service, img["path"], container_name,
                filename=img["filename"], extension=img["extension"]
            )

            # Skip unsupported formats
            ext = (img["extension"] or "png").lower().lstrip(".")
            if ext == "json":
                print("SKIPPED (JSON/Lottie - not an image)")
                failed += 1
                continue

            # Convert SVG to PNG for Claude Vision (SVG not supported)
            if ext == "svg":
                if not HAS_CAIROSVG:
                    print("SKIPPED (SVG - cairosvg not installed)")
                    failed += 1
                    continue
                image_bytes = convert_svg_to_png(image_bytes)
                media_type = "image/png"
            else:
                media_type = get_media_type(img["extension"])

            # Get description from Claude (with question context if available)
            description = get_image_description(
                client, image_bytes, filename, media_type,
                question_text=img.get("question_text")
            )

            if description:
                # Save to database immediately (each image committed individually)
                update_blob_tags(conn_holder, img["blob_id"], description, schema)
                print(f"OK")
                print(f"    Desc: {description[:100]}{'...' if len(description) > 100 else ''}")
                if img.get("question_text"):
                    print(f"    Q: {img['question_text'][:80]}{'...' if len(img['question_text']) > 80 else ''}")
                success += 1
                consecutive_errors = 0
            else:
                print("FAILED (no description returned)")
                failed += 1
                consecutive_errors += 1

        except anthropic.RateLimitError:
            print("RATE LIMITED - waiting 60s...")
            time.sleep(60)
            # Retry this image
            try:
                description = get_image_description(
                    client, image_bytes, filename, media_type,
                    question_text=img.get("question_text")
                )
                if description:
                    update_blob_tags(conn_holder, img["blob_id"], description, schema)
                    print(f"    Retry OK: {description[:80]}")
                    success += 1
                    consecutive_errors = 0
                else:
                    failed += 1
                    consecutive_errors += 1
            except Exception as e2:
                print(f"    Retry failed: {e2}")
                failed += 1
                consecutive_errors += 1

        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            print(f"\nAPI KEY ERROR: {e}")
            print("Check your ANTHROPIC_API_KEY is valid and has credit.")
            print(f"\nStopping. {success} images tagged successfully (saved to DB).")
            print("Run the script again after fixing the key to continue.")
            break

        except anthropic.APIStatusError as e:
            if "insufficient" in str(e).lower() or "credit" in str(e).lower():
                print(f"\nOUT OF CREDIT: {e}")
                print(f"\nStopping. {success} images tagged successfully (saved to DB).")
                print("Add credit at console.anthropic.com, then run again to continue.")
                break
            print(f"API ERROR: {e}")
            failed += 1
            consecutive_errors += 1

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
            consecutive_errors += 1

        # Stop if too many consecutive errors (probably a systemic issue)
        if consecutive_errors >= 10:
            print(f"\n10 consecutive errors - stopping to avoid wasting credit.")
            print(f"{success} images tagged successfully (saved to DB).")
            print("Fix the issue and run again to continue.")
            break

        # Progress report every 100 images
        if i % 100 == 0:
            print(f"\n--- Progress: {i}/{len(images)} done ({success} OK, {failed} failed) ---\n")

        # Rate limiting
        time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    print("\n" + "=" * 60)
    print("TAGGING COMPLETE")
    print("=" * 60)
    print(f"\nSuccess: {success}")
    print(f"Failed: {failed}")
    print(f"Remaining: {len(images) - success - failed}")
    if len(images) - success - failed > 0:
        print("\nRun the script again to process remaining images.")

    conn_holder["conn"].close()


if __name__ == "__main__":
    main()
