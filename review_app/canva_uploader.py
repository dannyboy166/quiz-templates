"""Canva Connect API integration — OAuth + asset upload."""

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

import requests

# Canva API endpoints
AUTH_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
ASSET_UPLOAD_URL = "https://api.canva.com/rest/v1/asset-uploads"
URL_ASSET_UPLOAD_URL = "https://api.canva.com/rest/v1/url-asset-uploads"

# Token storage on Railway volume (persists across deploys)
DATA_DIR = Path(os.environ.get("DATA_DIR", "data/voiceovers"))
TOKEN_FILE = DATA_DIR / "canva_tokens.json"


def get_client_id():
    return os.environ.get("CANVA_CLIENT_ID", "")


def get_client_secret():
    return os.environ.get("CANVA_CLIENT_SECRET", "")


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def _load_tokens():
    """Load stored tokens from disk."""
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _save_tokens(tokens):
    """Save tokens to disk."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def is_connected():
    """Check if we have stored Canva tokens."""
    tokens = _load_tokens()
    return tokens is not None and "access_token" in tokens


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
        "scope": "asset:read asset:write",
        "response_type": "code",
        "client_id": get_client_id(),
        "state": state,
        "redirect_uri": redirect_uri,
    }

    return AUTH_URL + "?" + "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())


def exchange_code(code, code_verifier, redirect_uri):
    """Exchange authorization code for access + refresh tokens."""
    client_id = get_client_id()
    client_secret = get_client_secret()

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(TOKEN_URL, headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }, timeout=30)

    resp.raise_for_status()
    tokens = resp.json()
    tokens["obtained_at"] = time.time()
    _save_tokens(tokens)
    return tokens


def _refresh_access_token():
    """Refresh the access token using the stored refresh token."""
    tokens = _load_tokens()
    if not tokens or "refresh_token" not in tokens:
        raise RuntimeError("No refresh token — need to re-authorize via /canva/auth")

    client_id = get_client_id()
    client_secret = get_client_secret()
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(TOKEN_URL, headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }, timeout=30)

    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["obtained_at"] = time.time()
    _save_tokens(new_tokens)
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


def upload_image_from_url(image_url, name):
    """Upload an image to Canva from a public URL.

    Returns (job_id, status) tuple.
    """
    access_token = _get_access_token()

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
        print(f"  Canva API error {resp.status_code}: {error_body}")

        # "already exists" means it uploaded successfully before — not a real error
        if isinstance(error_body, dict) and "already exists" in error_body.get("message", ""):
            return None, "already_uploaded"

        raise RuntimeError(f"Canva API {resp.status_code}: {error_body}")

    result = resp.json()
    job = result.get("job", {})
    return job.get("id"), job.get("status")


def clean_prompt_for_name(prompt):
    """Strip boilerplate from AI prompt to get a short image description.

    Georgia's style: '50 stars in square with word 50', '125 on an abacus'
    Our prompts: 'A simple, clear, colorful cartoon illustration... White background, no text...'
    """
    if not prompt:
        return ""
    import re
    # Remove common boilerplate phrases from OpenAI prompts
    boilerplate = [
        r"A simple,? ?clear,? ?colorful cartoon illustration for a children'?s educational quiz[^.]*\.\s*",
        r"A simple,? ?clear,? ?colorful cartoon illustration[^.]*\.\s*",
        r"A simple cartoon illustration[^.]*\.\s*",
        r"White background,?\s*no text,?\s*no labels,?\s*child-?friendly style\.?\s*",
        r"White background,?\s*no text[^.]*\.?\s*",
        r"No text,?\s*no labels[^.]*\.?\s*",
        r"\(ages \d+-\d+\)\.?\s*",
    ]
    text = prompt
    for pattern in boilerplate:
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
