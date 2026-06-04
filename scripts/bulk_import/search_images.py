#!/usr/bin/env python3
"""
Search images by tags.

Usage:
    source venv/bin/activate
    python -m scripts.bulk_import.search_images dog
    python -m scripts.bulk_import.search_images "animal red"
    python -m scripts.bulk_import.search_images --list-tags
"""

import argparse
from collections import Counter

from .db_connect import get_connection


def search_images(conn, search_terms: list) -> list:
    """Search for images matching ALL search terms in tags."""
    cursor = conn.cursor()

    # Build query - all terms must match (AND logic)
    conditions = " AND ".join(["Description LIKE ?" for _ in search_terms])
    params = [f"%{term}%" for term in search_terms]

    cursor.execute(f"""
        SELECT BlobID, Filename, Description, Path
        FROM DanTest.Blob
        WHERE BlobTypeCD = 110
          AND Description IS NOT NULL
          AND {conditions}
        ORDER BY Filename
    """, params)

    results = []
    for row in cursor.fetchall():
        results.append({
            "blob_id": row[0],
            "filename": row[1],
            "tags": row[2],
            "url": row[3]
        })

    return results


def get_all_tags(conn) -> Counter:
    """Get all unique tags and their counts."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Description
        FROM DanTest.Blob
        WHERE BlobTypeCD = 110
          AND Description IS NOT NULL
          AND Description != ''
    """)

    tag_counts = Counter()
    for row in cursor.fetchall():
        tags = row[0]
        if tags:
            for tag in tags.split(","):
                tag = tag.strip().lower()
                if tag:
                    tag_counts[tag] += 1

    return tag_counts


def main():
    parser = argparse.ArgumentParser(
        description="Search images by tags"
    )
    parser.add_argument(
        "search",
        nargs="*",
        help="Search terms (space-separated, all must match)"
    )
    parser.add_argument(
        "--list-tags", "-t",
        action="store_true",
        help="List all available tags"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Max results to show (default: 20)"
    )

    args = parser.parse_args()

    # Connect
    conn = get_connection()

    if args.list_tags:
        print("All tags (sorted by frequency):\n")
        tag_counts = get_all_tags(conn)

        if not tag_counts:
            print("No tagged images found.")
            print("Run: python -m scripts.bulk_import.tag_images")
            return

        for tag, count in tag_counts.most_common(50):
            print(f"  {tag}: {count}")

        if len(tag_counts) > 50:
            print(f"\n  ... and {len(tag_counts) - 50} more tags")

        print(f"\nTotal unique tags: {len(tag_counts)}")
        conn.close()
        return

    if not args.search:
        parser.print_help()
        return

    # Search
    search_terms = args.search
    print(f"Searching for: {' AND '.join(search_terms)}\n")

    results = search_images(conn, search_terms)

    if not results:
        print("No images found matching those tags.")
        print("\nTry: python -m scripts.bulk_import.search_images --list-tags")
        return

    print(f"Found {len(results)} images:\n")

    for i, img in enumerate(results[:args.limit], 1):
        print(f"{i}. {img['filename']} (BlobID: {img['blob_id']})")
        print(f"   Tags: {img['tags'][:80]}{'...' if len(img['tags']) > 80 else ''}")
        print()

    if len(results) > args.limit:
        print(f"... and {len(results) - args.limit} more (use --limit to see more)")

    conn.close()


if __name__ == "__main__":
    main()
