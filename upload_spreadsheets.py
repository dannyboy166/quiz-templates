#!/usr/bin/env python3
"""One-time script to copy spreadsheets to the Railway volume.
Run via: railway ssh -- python3 /app/upload_spreadsheets.py
Or locally to verify paths.
"""
import os
import shutil
from pathlib import Path

# Source: app directory (committed to git temporarily)
SRC_DIR = Path("/app/data_upload")

# Destination: Railway volume
DST_DIR = Path(os.environ.get("DATA_DIR", "/data/voiceovers")) / "questions" / "drive_latest"

FILENAMES = [
    "Krisite Stage One English Questions WORLD WISE.xlsx",
    "Kristie Stage One Mathematics Questions WORLD WISE.xlsx",
    "Kristie Stage One Other Subjects Questions WORLD WISE.xlsx",
]

def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)

    for fn in FILENAMES:
        src = SRC_DIR / fn
        dst = DST_DIR / fn

        if dst.exists() and dst.stat().st_size > 0:
            print(f"  SKIP {fn} (already exists, {dst.stat().st_size:,} bytes)")
            continue

        if not src.exists():
            print(f"  MISSING {fn} in {SRC_DIR}")
            continue

        shutil.copy2(src, dst)
        print(f"  COPIED {fn} ({dst.stat().st_size:,} bytes)")

    print("\nDone. Files on volume:")
    for f in sorted(DST_DIR.iterdir()):
        print(f"  {f.name}: {f.stat().st_size:,} bytes")

if __name__ == "__main__":
    main()
