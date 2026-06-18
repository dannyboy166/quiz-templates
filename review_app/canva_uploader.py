"""Canva Connect API integration — OAuth + asset upload.

Handles:
- OAuth 2.0 PKCE flow for one-time authorization
- Token storage on Railway volume (persists across deploys)
- Auto-refresh of access tokens before expiry
- Uploading generated images to user's Canva content library
- Asset naming matching Georgia's convention: {ItemID} - {description}
"""

import base64
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path

import requests

# Canva API endpoints
AUTH_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
URL_ASSET_UPLOAD_URL = "https://api.canva.com/rest/v1/url-asset-uploads"
GET_UPLOAD_JOB_URL = "https://api.canva.com/rest/v1/url-asset-uploads"  # GET {id}
FOLDERS_URL = "https://api.canva.com/rest/v1/folders"
MOVE_ITEM_URL = "https://api.canva.com/rest/v1/folders/move"

# Token storage on Railway volume (persists across deploys)
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers"))
TOKEN_FILE = DATA_DIR / "canva_tokens.json"
FOLDER_ID_FILE = DATA_DIR / "canva_folder_id.txt"

# Target folder name in Canva
CANVA_FOLDER_NAME = "WorldWise Images"


def get_client_id():
    return os.environ.get("CANVA_CLIENT_ID", "")


def get_client_secret():
    return os.environ.get("CANVA_CLIENT_SECRET", "")


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge for OAuth."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------

def _load_tokens():
    """Load stored tokens from disk."""
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [Canva] Warning: failed to load tokens: {e}")
            return None
    return None


def _save_tokens(tokens):
    """Save tokens to disk."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"  [Canva] Tokens saved to {TOKEN_FILE}")


def is_connected():
    """Check if we have stored Canva tokens."""
    tokens = _load_tokens()
    return tokens is not None and "access_token" in tokens


def disconnect():
    """Remove stored tokens — forces re-authorization."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print("  [Canva] Tokens deleted — disconnected")
        return True
    return False


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------

def get_auth_url(redirect_uri, state_store):
    """Build the Canva OAuth authorization URL.

    state_store is a dict that will be updated with code_verifier and state
    so the callback can use them.
    """
    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    state_store["code_verifier"] = verifier
    state_store["state"] = state

    params = {
        "code_challenge": challenge,
        "code_challenge_method": "s256",
        "scope": "asset:read asset:write folder:read folder:write",
        "response_type": "code",
        "client_id": get_client_id(),
        "state": state,
        "redirect_uri": redirect_uri,
    }

    url = AUTH_URL + "?" + "&".join(
        f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()
    )
    print(f"  [Canva] Auth URL built, redirecting to Canva...")
    return url


def exchange_code(code, code_verifier, redirect_uri):
    """Exchange authorization code for access + refresh tokens."""
    client_id = get_client_id()
    client_secret = get_client_secret()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    print(f"  [Canva] Exchanging auth code for tokens...")
    resp = requests.post(TOKEN_URL, headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }, timeout=30)

    if not resp.ok:
        try:
            error_body = resp.json()
        except Exception:
            error_body = resp.text
        print(f"  [Canva] Token exchange failed {resp.status_code}: {error_body}")
        raise RuntimeError(f"Canva token exchange failed: {error_body}")

    tokens = resp.json()
    tokens["obtained_at"] = time.time()
    _save_tokens(tokens)
    print(f"  [Canva] Authorization successful! Token expires in {tokens.get('expires_in', '?')}s")
    return tokens


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _refresh_access_token():
    """Refresh the access token using the stored refresh token."""
    tokens = _load_tokens()
    if not tokens or "refresh_token" not in tokens:
        print("  [Canva] No refresh token found — need to re-authorize")
        raise RuntimeError("Canva session expired — visit /canva/auth to reconnect")

    client_id = get_client_id()
    client_secret = get_client_secret()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    print(f"  [Canva] Refreshing access token...")
    resp = requests.post(TOKEN_URL, headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }, timeout=30)

    if not resp.ok:
        try:
            error_body = resp.json()
        except Exception:
            error_body = resp.text
        print(f"  [Canva] Token refresh failed {resp.status_code}: {error_body}")
        # Delete stale tokens so is_connected() returns False
        disconnect()
        raise RuntimeError("Canva session expired — visit /canva/auth to reconnect")

    new_tokens = resp.json()
    new_tokens["obtained_at"] = time.time()
    _save_tokens(new_tokens)
    print(f"  [Canva] Token refreshed OK, expires in {new_tokens.get('expires_in', '?')}s")
    return new_tokens


def _get_access_token():
    """Get a valid access token, refreshing if needed."""
    tokens = _load_tokens()
    if not tokens:
        raise RuntimeError("Not connected to Canva — visit /canva/auth first")

    # Canva access tokens expire after ~4 hours. Refresh proactively.
    obtained_at = tokens.get("obtained_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    if time.time() - obtained_at > (expires_in - 300):  # refresh 5 min before expiry
        tokens = _refresh_access_token()

    return tokens["access_token"]


# ---------------------------------------------------------------------------
# Asset upload
# ---------------------------------------------------------------------------

def upload_image_from_url(image_url, name):
    """Upload an image to Canva from a public URL.

    Returns (job_id, status) tuple.
    Status is one of: "in_progress", "success", "failed", "already_uploaded"
    """
    access_token = _get_access_token()

    print(f"  [Canva] Uploading: {name}")
    print(f"  [Canva] URL: {image_url}")

    resp = requests.post(URL_ASSET_UPLOAD_URL, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }, json={
        "name": name[:255],  # Canva limit
        "url": image_url,
    }, timeout=60)

    if not resp.ok:
        try:
            error_body = resp.json()
        except Exception:
            error_body = resp.text
        print(f"  [Canva] Upload error {resp.status_code}: {error_body}")

        # "already exists" means it uploaded successfully before — not a real error
        if isinstance(error_body, dict) and "already exists" in error_body.get("message", ""):
            print(f"  [Canva] Image already in Canva (skipping)")
            return None, "already_uploaded"

        raise RuntimeError(f"Canva upload failed: {error_body}")

    result = resp.json()
    job = result.get("job", {})
    status = job.get("status", "unknown")
    job_id = job.get("id")
    print(f"  [Canva] Upload job={job_id} status={status}")

    # Try to get the asset ID and move to folder
    asset_id = None
    if job.get("asset"):
        asset_id = job["asset"].get("id")
    elif job_id and status == "in_progress":
        # Poll for completion to get asset ID
        asset_id = _poll_upload_job(job_id)

    if asset_id:
        _move_to_folder(asset_id)

    return job_id, status


# ---------------------------------------------------------------------------
# Upload job polling
# ---------------------------------------------------------------------------

def _poll_upload_job(job_id, max_attempts=5):
    """Poll an upload job until complete, return asset ID or None."""
    access_token = _get_access_token()
    for attempt in range(max_attempts):
        time.sleep(2)
        resp = requests.get(f"{GET_UPLOAD_JOB_URL}/{job_id}", headers={
            "Authorization": f"Bearer {access_token}",
        }, timeout=30)
        if resp.ok:
            job = resp.json().get("job", {})
            if job.get("status") == "success" and job.get("asset"):
                asset_id = job["asset"]["id"]
                print(f"  [Canva] Upload complete, asset_id={asset_id}")
                return asset_id
            elif job.get("status") == "failed":
                print(f"  [Canva] Upload job failed: {job.get('error')}")
                return None
    print(f"  [Canva] Upload job still processing after {max_attempts} polls, skipping folder move")
    return None


# ---------------------------------------------------------------------------
# Folder management
# ---------------------------------------------------------------------------

def _get_folder_id():
    """Get the WorldWise Images folder ID, creating it if needed."""
    # Check cached folder ID
    if FOLDER_ID_FILE.exists():
        folder_id = FOLDER_ID_FILE.read_text().strip()
        if folder_id:
            return folder_id

    access_token = _get_access_token()

    # Search for existing folder
    resp = requests.get(FOLDERS_URL, headers={
        "Authorization": f"Bearer {access_token}",
    }, params={"query": CANVA_FOLDER_NAME}, timeout=30)

    if resp.ok:
        items = resp.json().get("items", [])
        for item in items:
            if item.get("folder", {}).get("name") == CANVA_FOLDER_NAME:
                folder_id = item["folder"]["id"]
                FOLDER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
                FOLDER_ID_FILE.write_text(folder_id)
                print(f"  [Canva] Found existing folder: {CANVA_FOLDER_NAME} ({folder_id})")
                return folder_id

    # Create new folder
    print(f"  [Canva] Creating folder: {CANVA_FOLDER_NAME}")
    resp = requests.post(FOLDERS_URL, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }, json={
        "name": CANVA_FOLDER_NAME,
        "parent_folder_id": "root",
    }, timeout=30)

    if resp.ok:
        folder = resp.json().get("folder", {})
        folder_id = folder.get("id")
        if folder_id:
            FOLDER_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
            FOLDER_ID_FILE.write_text(folder_id)
            print(f"  [Canva] Created folder: {CANVA_FOLDER_NAME} ({folder_id})")
            return folder_id

    print(f"  [Canva] Could not create folder: {resp.status_code} {resp.text}")
    return None


def _move_to_folder(asset_id):
    """Move an asset to the WorldWise Images folder."""
    folder_id = _get_folder_id()
    if not folder_id:
        print(f"  [Canva] No folder ID — skipping move")
        return

    access_token = _get_access_token()
    resp = requests.post(MOVE_ITEM_URL, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }, json={
        "item_id": asset_id,
        "to_folder_id": folder_id,
    }, timeout=30)

    if resp.status_code == 204:
        print(f"  [Canva] Moved to {CANVA_FOLDER_NAME} folder")
    else:
        print(f"  [Canva] Move failed: {resp.status_code} {resp.text}")


# ---------------------------------------------------------------------------
# Asset naming
# ---------------------------------------------------------------------------

# Boilerplate phrases to strip from AI prompts when building Canva asset names
_PROMPT_BOILERPLATE = [
    r"We are making images for a children'?s educational quiz\.?\s*",
    r"Make a simple,? ?colorful cartoon image for this question:\s*",
    r"A simple,? ?clear,? ?colorful cartoon illustration for a children'?s educational quiz[^.]*\.\s*",
    r"A simple,? ?clear,? ?colorful cartoon illustration[^.]*\.\s*",
    r"A simple cartoon illustration[^.]*\.\s*",
    r"White background,?\s*no text,?\s*no labels,?\s*child-?friendly style\.?\s*",
    r"White background,?\s*no text[^.]*\.?\s*",
    r"No text,?\s*no labels[^.]*\.?\s*",
    r"\(ages \d+-\d+\)\.?\s*",
    r"child-?friendly style\.?\s*",
]


def clean_prompt_for_name(prompt):
    """Strip boilerplate from AI prompt to get a short image description.

    Georgia's style: '50 stars in square with word 50', '125 on an abacus'
    """
    if not prompt:
        return ""
    text = prompt
    for pattern in _PROMPT_BOILERPLATE:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip().rstrip(".")


def build_asset_name(item_id, prompt):
    """Build Canva asset name matching Georgia's convention.

    Format: {ItemID} - {short description}
    Examples: '130001 - 50 stars in square', '20012001 - The sun shining brightly'
    """
    desc = clean_prompt_for_name(prompt)
    if not desc:
        desc = "question image"
    # Truncate to fit 255 char Canva limit
    max_desc = 255 - len(item_id) - 3  # " - " separator
    desc = desc[:max_desc].strip()
    return f"{item_id} - {desc}"
