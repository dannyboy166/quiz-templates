"""Read Kristie's Get Help lesson scripts (.docx) from Google Drive and parse into scenes.

Scripts live in Drive folders (teacher-reviewed). Each .docx has a consistent shape:

    # <Topic>
    Help Lesson Script
    Subject: ...
    Category: ...
    Question types: ...
    Scenes: N
    Status: APPROVED ...
    Instructions: ...
    Topics Covered (...):
      • ...
    Scene-Topic Mapping ...
    ____________________
    ## Scene 0: Intro
    "narration line one"
    "narration line two"
    ## Scene 1: <Title>
    "..."
    ON SCREEN: <visual directions — NOT narrated>
    ...

This module turns each .docx into:
    { topic, subject, category, status, scenes: [ {n, title, narration, on_screen} ] }

`narration` is the combined quoted lines for that scene — exactly what gets sent to
ElevenLabs. `on_screen` is the ON SCREEN directions (visual brief, not narrated).

Source of truth is Drive; we cache the parsed result on disk and expose a refresh.
Auth reuses the same service-account credentials as gsheets_loader (drive scope).
"""

import io
import os
import re
import json
import time
from pathlib import Path

# The three sibling folders under "Help Video Scripts" (verified 14 Sep 2026).
# We read from all of them so every script shows up regardless of review stage.
SCRIPT_FOLDER_IDS = {
    "To be Checked":              "1KRfI50EtKlykRO7q0bBCjKGqzekAQ8W7",
    "Scripts Completed":          "1of3ypiq4qFgAY4ucK9LJE-zqeMCSG0wa",
    "Script and Video completed": "1xmQqhAR4yn2Id0uYXr3T2cIAO9zYIH3F",
}

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Cache parsed scripts on the volume (or local) so we don't hit Drive every request.
_CACHE_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers")) / "gethelp"
_CACHE_FILE = _CACHE_DIR / "scripts_cache.json"


# ---------------------------------------------------------------------------
# Google Drive access (service account) — mirrors gsheets_loader credentials
# ---------------------------------------------------------------------------

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _have_credentials():
    if os.environ.get("GOOGLE_SA_JSON", "").strip():
        return True
    key = os.environ.get("GOOGLE_SA_KEY", "").strip()
    return bool(key) and os.path.exists(key)


def is_available():
    """True if we can attempt a live Drive load (deps importable + credentials)."""
    try:
        import googleapiclient.discovery  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
        import docx  # noqa: F401  (python-docx)
    except ImportError:
        return False
    return _have_credentials()


def _credentials():
    from google.oauth2.service_account import Credentials
    inline = os.environ.get("GOOGLE_SA_JSON", "").strip()
    if inline:
        return Credentials.from_service_account_info(json.loads(inline), scopes=_DRIVE_SCOPES)
    key = os.environ.get("GOOGLE_SA_KEY", "").strip()
    if key and os.path.exists(key):
        return Credentials.from_service_account_file(key, scopes=_DRIVE_SCOPES)
    raise RuntimeError("No Google credentials — set GOOGLE_SA_JSON or GOOGLE_SA_KEY")


def _drive_service():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _list_docx_in_folder(service, folder_id):
    """Return [{id, name, modifiedTime}] for .docx files directly in a folder."""
    q = f"'{folder_id}' in parents and mimeType = '{_DOCX_MIME}' and trashed = false"
    out, page_token = [], None
    while True:
        resp = service.files().list(
            q=q, fields="nextPageToken, files(id, name, modifiedTime)",
            pageSize=100, pageToken=page_token,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _download_docx_bytes(service, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    req = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_META_KEYS = ("subject", "category", "question types", "scenes", "status")


def _docx_paragraphs(buf):
    """Yield non-empty paragraph texts from a .docx byte buffer."""
    import docx
    document = docx.Document(buf)
    for p in document.paragraphs:
        t = (p.text or "").strip()
        if t:
            yield t


def parse_script_text(paragraphs, fallback_topic=""):
    """Parse an ordered list of paragraph strings into a lesson dict.

    Robust to the '#'/'##' markdown-ish headings the generator emits and to the
    quoted-narration + 'ON SCREEN:' convention.
    """
    topic = fallback_topic
    meta = {"subject": "", "category": "", "status": "", "question_types": ""}
    scenes = []
    current = None

    def _flush():
        if current is not None:
            current["narration"] = " ".join(current["_lines"]).strip()
            current.pop("_lines", None)
            scenes.append(current)

    for raw in paragraphs:
        line = raw.strip()
        low = line.lower().lstrip("# ").strip()

        # Title: first "# Topic" heading (single #, not ##)
        if re.match(r"^#(?!#)\s+", line):
            topic = re.sub(r"^#\s+", "", line).strip()
            continue

        # Scene heading: "## Scene N: Title"
        m = re.match(r"^#{0,3}\s*Scene\s+(\d+)\s*:?\s*(.*)$", line, re.IGNORECASE)
        if m:
            _flush()
            current = {
                "n": int(m.group(1)),
                "title": m.group(2).strip(),
                "on_screen": "",
                "_lines": [],
            }
            continue

        # Metadata lines (only before the first scene)
        if current is None:
            for key in _META_KEYS:
                if low.startswith(key + ":"):
                    val = line.split(":", 1)[1].strip()
                    if key == "question types":
                        meta["question_types"] = val
                    else:
                        meta[key] = val
                    break
            continue

        # Inside a scene:
        # ON SCREEN directions — visual brief, not narrated
        if low.startswith("on screen"):
            directions = line.split(":", 1)[1].strip() if ":" in line else ""
            current["on_screen"] = (current["on_screen"] + " " + directions).strip()
            continue

        # Narration = quoted lines. Accept straight or smart quotes.
        q = _extract_quoted(line)
        if q:
            current["_lines"].append(q)
        # Non-quoted, non-ON-SCREEN prose inside a scene is ignored (rare).

    _flush()
    scenes.sort(key=lambda s: s["n"])
    return {
        "topic": topic,
        "subject": meta["subject"],
        "category": meta["category"],
        "status": meta["status"],
        "question_types": meta["question_types"],
        "scenes": scenes,
    }


def _extract_quoted(line):
    """Return the narration text if the line is a quoted narration line, else ''.

    Handles straight quotes and smart quotes; tolerates a trailing/leading stray quote.
    """
    # Normalise smart quotes to straight for detection.
    norm = line.replace("“", '"').replace("”", '"')
    m = re.search(r'"(.*?)"', norm, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    # Some lines are a full quoted sentence but missing the closing quote.
    if norm.startswith('"') and len(norm) > 1:
        return norm.lstrip('"').strip()
    return ""


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "scene"


def topic_slug(topic):
    """Folder-name slug for a lesson, e.g. 'Ordering Numbers' -> 'ordering-numbers'."""
    return _slug(topic)


def scene_audio_filename(scene):
    """`scene-{n}-{slug}.mp3` — matches Dan's lesson-build convention."""
    return f"scene-{scene['n']}-{_slug(scene['title'])}.mp3"


# ---------------------------------------------------------------------------
# Public API: load all lessons (cached), with refresh
# ---------------------------------------------------------------------------

def load_lessons(force_refresh=False):
    """Return {"lessons": [...], "source": ..., "warnings": [...]}.

    Reads from cache unless force_refresh; on refresh, pulls every .docx from the
    three Drive folders, parses, and rewrites the cache. Later folders win on
    duplicate topic names (so 'Script and Video completed' beats 'To be Checked').
    """
    if not force_refresh and _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text())
        except Exception:
            pass  # fall through to refresh

    warnings = []
    if not is_available():
        return {"lessons": [], "source": "unavailable",
                "warnings": ["Drive/docx deps or credentials missing"]}

    service = _drive_service()
    by_topic = {}
    for folder_name, folder_id in SCRIPT_FOLDER_IDS.items():
        try:
            files = _list_docx_in_folder(service, folder_id)
        except Exception as e:
            warnings.append(f"{folder_name}: {e}")
            continue
        for f in files:
            try:
                buf = _download_docx_bytes(service, f["id"])
                paras = list(_docx_paragraphs(buf))
                fallback = os.path.splitext(f["name"])[0]
                # The two legacy filenames (HELP_LESSON(S)_SCRIPTS_*.docx) have no clean
                # "# Topic" heading — give them their real topic name so they slug correctly
                # (Partitioning Numbers / Addition are 2 of the 7 built lessons).
                upper = f["name"].upper()
                if upper.startswith("HELP_LESSON"):
                    if "PARTITION" in upper:
                        fallback = "Partitioning Numbers"
                    elif "ADDITION" in upper:
                        fallback = "Addition"
                lesson = parse_script_text(paras, fallback_topic=fallback)
                lesson["source_folder"] = folder_name
                lesson["drive_file_id"] = f["id"]
                lesson["drive_modified"] = f.get("modifiedTime", "")
                lesson["slug"] = topic_slug(lesson["topic"] or fallback)
                if lesson["scenes"]:
                    by_topic[lesson["slug"]] = lesson
            except Exception as e:
                warnings.append(f"{f.get('name','?')}: {e}")

    lessons = sorted(by_topic.values(), key=lambda l: l["topic"].lower())
    result = {"lessons": lessons, "source": "google-drive",
              "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "warnings": warnings}
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(result, indent=2))
    except Exception as e:
        warnings.append(f"cache write failed: {e}")
    return result


def get_lesson(slug):
    """Return one lesson dict by slug, or None."""
    for l in load_lessons().get("lessons", []):
        if l.get("slug") == slug:
            return l
    return None
