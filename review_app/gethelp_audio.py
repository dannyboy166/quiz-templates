"""Per-scene Get Help audio: generate (ElevenLabs Vonnie), version history, approve.

Audio for lesson `slug`, scene file `scene-{n}-{title}.mp3` is stored under:
    {DATA_DIR}/help-audio/{slug}/scene-{n}-{title}.mp3
with version snapshots `...__vN.mp3` beside it (same scheme as question voiceovers).

Approval state lives in {DATA_DIR}/help-audio/gethelp_audio_state.json:
    { "<slug>/<filename>": {"approved": bool, "generated_at": iso, "approved_at": iso} }

Reuses the existing ElevenLabs plumbing from generate_voiceovers (voice, API settings)
via a thin scene wrapper, so scene audio sounds identical to question voiceovers.
"""

import os
import re
import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "cupfa8uelkW7cWxLMRa7")

# Reuse the finalised API settings from the voiceover generator so scene audio
# matches question audio exactly.
try:
    from scripts.bulk_import.generate_voiceovers import API_SETTINGS as _VO_API_SETTINGS
    _VOICE_SETTINGS = _VO_API_SETTINGS.get("voice_settings", {})
    _MODEL_ID = _VO_API_SETTINGS.get("model_id", "eleven_multilingual_v2")
except Exception:
    _VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75}
    _MODEL_ID = "eleven_multilingual_v2"

AUDIO_ROOT = Path(os.environ.get("DATA_DIR", _project_root / "data" / "voiceovers")) / "help-audio"
STATE_FILE = AUDIO_ROOT / "gethelp_audio_state.json"

# The 7 already-built lessons keep their original audio here (in the repo), so Zoe/Georgia
# can LISTEN to the existing voiceovers and only regenerate the ones they don't like.
# Folder names differ from the lesson slug in a couple of cases, so map explicitly.
EXISTING_AUDIO_ROOT = _project_root / "audio"
EXISTING_AUDIO_FOLDER = {
    "partitioning-numbers": "help-partitioning",
    "partitioning":         "help-partitioning",
    "addition":             "help-addition-scenes",
    "subtraction":          "help-subtraction",
    "counting":             "help-counting",
    "ordinal-numbers":      "help-ordinal-numbers",
    "telling-the-time":     "help-telling-time",
    "telling-time":         "help-telling-time",
    "homophones":           "help-homophones",
}


def existing_audio_for_scene(slug, scene_n):
    """Return a repo-relative filename of the original built audio for this scene, or None.

    Matches by SCENE NUMBER (the reliable key) since the original slugs differ from the
    script-derived ones. e.g. scene 9 of subtraction -> audio/help-subtraction/scene-9-*.mp3
    """
    folder = EXISTING_AUDIO_FOLDER.get(slug)
    if not folder:
        return None
    d = EXISTING_AUDIO_ROOT / folder
    if not d.is_dir():
        return None
    matches = sorted(d.glob(f"scene-{scene_n}-*.mp3"))
    # guard against scene-1 matching scene-10: require exact "scene-N-" prefix
    matches = [m for m in matches if re.match(rf"^scene-{scene_n}-", m.name)]
    return f"{folder}/{matches[0].name}" if matches else None


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def lesson_dir(slug):
    return AUDIO_ROOT / slug


def scene_audio_path(slug, filename):
    return lesson_dir(slug) / filename


def audio_key(slug, filename):
    return f"{slug}/{filename}"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def save_state(state):
    AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def get_scene_state(state, slug, filename):
    return state.get(audio_key(slug, filename), {
        "approved": False, "generated_at": None, "approved_at": None,
    })


def update_scene_state(state, slug, filename, **kwargs):
    key = audio_key(slug, filename)
    cur = state.get(key, {"approved": False, "generated_at": None, "approved_at": None})
    cur.update(kwargs)
    state[key] = cur
    save_state(state)
    return cur


def has_scene_audio(slug, filename):
    return scene_audio_path(slug, filename).exists()


def adopt_existing_audio(slug, scene_n, filename):
    """Copy Dan's original built audio for this scene into the tab's audio store as the
    current take, so it can be approved/versioned like any generated take. Returns True
    if adopted, False if there was no existing audio."""
    rel = existing_audio_for_scene(slug, scene_n)
    if not rel:
        return False
    src = EXISTING_AUDIO_ROOT / rel
    if not src.exists():
        return False
    lesson_dir(slug).mkdir(parents=True, exist_ok=True)
    _snapshot_current(slug, filename)
    scene_audio_path(slug, filename).write_bytes(src.read_bytes())
    return True


# ---------------------------------------------------------------------------
# Version history (mirror of the question-voiceover versioning scheme)
# ---------------------------------------------------------------------------

def _version_glob(slug, filename):
    stem = Path(filename).stem
    return sorted(lesson_dir(slug).glob(f"{stem}__v*.mp3"))


def get_versions(slug, filename):
    """Return [{version:int, filename:str}] of prior takes, newest last."""
    out = []
    for vf in _version_glob(slug, filename):
        m = re.search(r"__v(\d+)\.mp3$", vf.name)
        if m:
            out.append({"version": int(m.group(1)), "filename": vf.name})
    return sorted(out, key=lambda v: v["version"])


def _snapshot_current(slug, filename):
    """Before overwriting, copy the current mp3 to the next __vN.mp3 snapshot."""
    cur = scene_audio_path(slug, filename)
    if not cur.exists():
        return
    existing = get_versions(slug, filename)
    nxt = (existing[-1]["version"] + 1) if existing else 1
    stem = Path(filename).stem
    cur.replace(lesson_dir(slug) / f"{stem}__v{nxt}.mp3")  # move current -> version


def restore_version(slug, filename, version_num):
    """Make an old take current again (snapshotting the current one first)."""
    stem = Path(filename).stem
    vf = lesson_dir(slug) / f"{stem}__v{version_num}.mp3"
    if not vf.exists():
        raise FileNotFoundError(vf)
    data = vf.read_bytes()
    _snapshot_current(slug, filename)
    scene_audio_path(slug, filename).write_bytes(data)


# ---------------------------------------------------------------------------
# Generation (ElevenLabs)
# ---------------------------------------------------------------------------

def _clean_for_speech(text):
    """Light cleanup so TTS reads naturally (mirrors the JS generator's intent)."""
    t = (text or "").strip()
    t = t.replace("—", " — ").replace("  ", " ")
    return t


def generate_scene_audio(slug, filename, narration, speed=0.9):
    """Generate (or regenerate) one scene's MP3. Snapshots any current take first.

    Returns (bytes_written, error_or_None).
    """
    if not ELEVENLABS_API_KEY:
        return 0, "ELEVENLABS_API_KEY not set"
    text = _clean_for_speech(narration)
    if not text:
        return 0, "empty narration"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    voice_settings = dict(_VOICE_SETTINGS)
    voice_settings["speed"] = speed
    payload = {
        "text": text,
        "model_id": _MODEL_ID,
        "output_format": "mp3_44100_128",
        "voice_settings": voice_settings,
    }
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
    except Exception as e:
        return 0, f"request failed: {e}"
    if resp.status_code != 200:
        return 0, f"ElevenLabs {resp.status_code}: {resp.text[:200]}"

    lesson_dir(slug).mkdir(parents=True, exist_ok=True)
    _snapshot_current(slug, filename)          # keep the previous take
    out = scene_audio_path(slug, filename)
    out.write_bytes(resp.content)

    # regenerating invalidates a prior approval
    state = load_state()
    update_scene_state(state, slug, filename,
                       generated_at=now_iso(), approved=False, approved_at=None)
    return len(resp.content), None
