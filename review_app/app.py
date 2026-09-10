"""QuestionReview Flask app — voice over review tool for Zoe/Julie."""

import json
import os
import re
import io
import csv
import time
import hmac
import zipfile
import threading
import queue
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from flask import (
    Flask, render_template, jsonify, request,
    send_from_directory, abort, redirect, Response,
    session, url_for,
)

from .spreadsheet_loader import load_all_questions, TEMPLATE_NAMES
from . import gsheets_loader
from . import final_stage
from . import final_state as final_state_mod
from .state import (
    load_state, save_state, get_item_state, update_item_state,
    has_audio, now_iso, VOICEOVER_DIR, DATA_DIR,
    get_hint_state, update_hint_state, has_hint_audio,
    get_option_state, update_option_state, has_option_audio,
)
from .voiceover_engine import (
    get_ssml_for_question, generate_for_question,
    get_ssml_for_hint, generate_for_hint,
    generate_for_option, get_ssml_for_option,
    generate_for_tf, has_tf_audio,
)
from .image_state import (
    load_image_state, save_image_state, get_image_item_state,
    update_image_item_state, has_question_image, has_answer_image, has_hint_image,
    IMAGE_DATA_DIR, now_iso as img_now_iso,
)
from .image_engine import (
    build_question_prompt, build_answer_prompt,
    generate_question_image, generate_answer_image, generate_hint_image,
    edit_question_image, get_version_files, restore_version,
    png_to_webp,
    IMAGE_DATA_DIR as IMG_ENGINE_DIR,
)
from .airtable_loader import (
    load_airtable_images, load_cached_airtable_images,
    save_airtable_cache,
)
from .airtable_push import (
    push_question_image as at_push_question,
    push_answer_image as at_push_answer,
    push_hint_image as at_push_hint,
)
from . import canva_uploader

# Bulk generation state (voiceovers)
bulk_status = {
    "running": False,
    "total": 0,
    "completed": 0,
    "errors": [],
    "current_item": None,
}
bulk_lock = threading.Lock()
bulk_queue = queue.Queue()

# Bulk generation state (images)
img_bulk_status = {
    "running": False,
    "total": 0,
    "completed": 0,
    "errors": [],
    "current_item": None,
}
img_bulk_lock = threading.Lock()
img_bulk_queue = queue.Queue()


def create_app():
    app = Flask(__name__)
    # Cap uploads (Georgia's "upload image" button) so a huge/bad file can't OOM the worker.
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB

    # --- Simple shared-password gate ------------------------------------
    # The app has no user accounts. If ACCESS_PASSWORD is set, every page
    # (except the login form and audio/static assets) requires the password
    # once per browser session. If it's unset, the app stays open (dev/local).
    ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD")

    # The session cookie that carries "authed" is only as trustworthy as the
    # signing key. If the gate is on, a real SECRET_KEY is mandatory — a known
    # default would let anyone forge an authed cookie and bypass the password.
    secret_key = os.environ.get("SECRET_KEY")
    if ACCESS_PASSWORD and not secret_key:
        raise RuntimeError(
            "ACCESS_PASSWORD is set but SECRET_KEY is not. Refusing to start: "
            "a signed session with a guessable key is not real auth. "
            "Set SECRET_KEY to a long random value."
        )
    app.secret_key = secret_key or "dev-insecure-open-mode"
    app.permanent_session_lifetime = timedelta(days=7)

    project_root = Path(__file__).resolve().parent.parent

    # Exact paths + asset prefixes that never require auth. Audio and generated
    # images must be reachable so the library can play/download files; static
    # assets (css/fonts/js) too. Everything else is gated.
    # Only truly-trivial, non-sensitive paths are auth-exempt. pipeline-stats leaks
    # all question content, so it stays gated. data-source only reports live/stale + counts.
    _OPEN_EXACT = {"/login", "/logout", "/favicon.ico", "/healthz", "/api/data-source"}
    _OPEN_PREFIXES = ("/assets/", "/static/", "/audio/", "/generated-images/")

    def _is_open_path(path):
        return path in _OPEN_EXACT or path.startswith(_OPEN_PREFIXES)

    def _safe_next(target):
        """Only allow same-site relative redirects (a single leading slash,
        not '//host' or 'https:'). Prevents open-redirect phishing."""
        if not target:
            return None
        if target.startswith("//") or "://" in target or "\\" in target:
            return None
        if not target.startswith("/"):
            return None
        return target

    @app.before_request
    def _require_login():
        if not ACCESS_PASSWORD:
            return  # gate disabled
        if _is_open_path(request.path):
            return
        if session.get("authed"):
            return
        # Programmatic callers (e.g. completeness_report.py) may pass the password as a
        # header instead of a browser session — lets gated API endpoints stay non-public.
        token = request.headers.get("X-Access-Token", "")
        if token and hmac.compare_digest(token, ACCESS_PASSWORD):
            return
        # Preserve the full original URL (path + query) so filtered/deep links
        # survive the login round-trip.
        return redirect(url_for("login", next=request.full_path.rstrip("?")))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not ACCESS_PASSWORD:
            return redirect(url_for("dashboard"))
        nxt = _safe_next(request.args.get("next")) or url_for("dashboard")
        if session.get("authed"):
            return redirect(nxt)
        error = None
        if request.method == "POST":
            supplied = request.form.get("password", "")
            if hmac.compare_digest(supplied, ACCESS_PASSWORD):
                session["authed"] = True
                session.permanent = True
                return redirect(nxt)
            error = "Incorrect password."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        if ACCESS_PASSWORD:
            return redirect(url_for("login"))
        return redirect(url_for("dashboard"))

    @app.route("/healthz")
    def healthz():
        # Trivial liveness probe for Railway. Does NO data work, so a slow/erroring
        # data endpoint can never take the deploy down. Must stay in _OPEN_EXACT.
        return "ok", 200

    # --- Question data source: LIVE Google Sheets are the source of truth. ---
    # Prefer live; if live fails, fall back to the xlsx snapshot BUT surface it loudly
    # (data_source_status drives a red banner + /healthz-adjacent status) so we never
    # serve stale data silently. Dan's rule (8 Sep 2026).
    data_source_status = {
        "mode": "unknown",        # "live" | "stale-fallback"
        "loaded_at": None,
        "error": None,
    }

    def _load_questions():
        if gsheets_loader.is_available():
            try:
                result = gsheets_loader.load_all_questions_live(force=True)
                data_source_status["mode"] = "live"
                data_source_status["loaded_at"] = gsheets_loader.cache_meta().get("loaded_at")
                data_source_status["error"] = None
                print(f"  DATA SOURCE: LIVE Google Sheets ({len(result[0])} questions)")
                return result
            except Exception as e:
                data_source_status["mode"] = "stale-fallback"
                data_source_status["error"] = str(e)
                print(f"  !!! LIVE Google Sheets FAILED: {e}\n  !!! Falling back to STALE xlsx snapshot.")
        else:
            data_source_status["mode"] = "stale-fallback"
            data_source_status["error"] = "Google Sheets credentials/gspread unavailable"
            print("  !!! Live Google Sheets not available — using STALE xlsx snapshot.")
        result = load_all_questions()
        data_source_status["loaded_at"] = None
        return result

    # Load data on startup
    print("Loading questions...")
    questions, questions_list, subjects, topics_by_subject, sheets = _load_questions()
    state = load_state()

    # Detect existing audio files from previous batches
    existing_audio = 0
    for q in questions_list:
        if has_audio(q["item_id"]) and q["item_id"] not in state:
            state[q["item_id"]] = {
                "status": "pending",
                "speech_override": None,
                "speed_override": None,
                "flag_note": "",
                "generated_at": None,
                "approved_at": None,
            }
            existing_audio += 1
    if existing_audio:
        save_state(state)
        print(f"  Found {existing_audio} existing audio files from previous batches")

    # --- Data-source status + live reload ---

    @app.route("/api/data-source")
    def api_data_source():
        """Report whether the app is serving LIVE Google Sheets or a stale fallback.

        Auth-exempt + trivial so the UI banner can always read it. Drives the red
        'STALE DATA' banner when mode != 'live'.
        """
        return jsonify({
            "mode": data_source_status["mode"],
            "loaded_at": data_source_status["loaded_at"],
            "error": data_source_status["error"],
            "question_count": len(questions),
            "live_available": gsheets_loader.is_available(),
            "warnings": gsheets_loader.cache_meta().get("warnings", []),
        })

    @app.route("/api/reload-questions", methods=["POST"])
    def api_reload_questions():
        """Re-fetch questions from LIVE Google Sheets and update in place.

        Refuses to silently replace live data with stale on failure — reports the error.
        """
        if not gsheets_loader.is_available():
            return jsonify({"ok": False, "error": "Live Google Sheets not available"}), 503
        try:
            new_q, new_list, new_subs, new_tbs, new_sheets = gsheets_loader.refresh()
        except Exception as e:
            data_source_status["error"] = str(e)
            return jsonify({"ok": False, "error": str(e)}), 502
        # Update shared containers in place so existing route closures see the new data.
        # (questions_list is aliased by image_questions_list; mutating in place keeps both fresh.)
        questions.clear()
        questions.update(new_q)
        questions_list[:] = new_list
        subjects[:] = new_subs
        topics_by_subject.clear()
        topics_by_subject.update(new_tbs)
        data_source_status["mode"] = "live"
        data_source_status["loaded_at"] = gsheets_loader.cache_meta().get("loaded_at")
        data_source_status["error"] = None
        print(f"  [reload] Live reload OK — {len(questions)} questions")
        return jsonify({
            "ok": True,
            "mode": "live",
            "question_count": len(questions),
            "loaded_at": data_source_status["loaded_at"],
            "warnings": gsheets_loader.cache_meta().get("warnings", []),
        })

    # --- Static file routes for project assets ---

    @app.route("/assets/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(project_root / "css", filename)

    @app.route("/assets/fonts/<path:filename>")
    def serve_fonts(filename):
        return send_from_directory(project_root / "fonts", filename)

    @app.route("/assets/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(project_root / "js", filename)

    @app.route("/audio/<path:filename>")
    def serve_audio(filename):
        return send_from_directory(VOICEOVER_DIR, filename)

    # --- Page routes ---

    @app.route("/")
    def dashboard():
        stats = _compute_stats(questions_list, state)
        flagged = _get_flagged(questions, state)
        return render_template("dashboard.html",
                               stats=stats, flagged=flagged,
                               total=len(questions_list))

    @app.route("/questions")
    def question_list():
        return render_template("question_list.html",
                               questions_json=json.dumps(
                                   _questions_for_client(questions_list, state),
                                   ensure_ascii=False),
                               subjects=subjects,
                               topics_by_subject=json.dumps(topics_by_subject),
                               sheets=sheets)

    # --- Voice-over Library (read-only, for Julie) ----------------------
    # Shows only APPROVED voice-overs that actually have audio on disk, so
    # they can be browsed, searched, played, and downloaded (single or ZIP)
    # for hand-off. A "Show all statuses" toggle reveals pending/flagged too.

    def _library_items(include_all=False):
        """Build the client-side list for the library.

        By default only items with status 'approved' AND an audio file.
        Each item carries its downloadable question/hint filenames.
        """
        items = []
        for q in questions_list:
            item_id = q["item_id"]
            s = state.get(item_id, {})
            status = s.get("status", "pending")
            q_has_audio = has_audio(item_id)

            # Approved hints that have audio (each independently shippable).
            hint_files = []
            for h in range(1, 4):
                if not q.get(f"hint{h}"):
                    continue
                hs = s.get("hints", {}).get(f"hint{h}", {})
                if has_hint_audio(item_id, h) and (include_all or hs.get("status") == "approved"):
                    hint_files.append({
                        "n": h,
                        "file": f"{item_id}-hint{h}.mp3",
                        "status": hs.get("status", "pending"),
                    })

            question_ready = q_has_audio and (include_all or status == "approved")
            if not question_ready and not hint_files:
                continue

            items.append({
                "id": item_id,
                "text": q["question_text"][:120],
                "subject": q["subject"],
                "topic": q["topic"],
                "type": q["question_type"],
                "grade": q["grade"],
                "status": status,
                "question_file": f"{item_id}-question.mp3" if question_ready else None,
                "hints": hint_files,
            })
        return items

    @app.route("/library")
    def library():
        include_all = request.args.get("all") == "1"
        items = _library_items(include_all=include_all)
        return render_template(
            "library.html",
            items_json=json.dumps(items, ensure_ascii=False),
            subjects=subjects,
            topics_by_subject=json.dumps(topics_by_subject),
            include_all=include_all,
            total=len(items),
        )

    @app.route("/api/library/download-zip", methods=["POST"])
    def library_download_zip():
        """Zip the requested item_ids' audio with a manifest.csv.

        Body: {"ids": ["20012001", ...], "all": false}. Files are renamed to
        self-describing names; manifest.csv maps them back to metadata.
        """
        data = request.get_json(silent=True) or {}
        include_all = bool(data.get("all"))
        # Require an explicit selection: either a non-empty id list, or the
        # caller must opt in to "everything shown" with want_all=True. This
        # avoids an empty/missing ids body silently zipping the whole library.
        raw_ids = data.get("ids")
        want_all = bool(data.get("want_all"))
        if raw_ids is None and not want_all:
            return jsonify({"ok": False, "error": "No items selected."}), 400
        wanted = set(raw_ids or [])

        items = _library_items(include_all=include_all)
        if not want_all:
            if not wanted:
                return jsonify({"ok": False, "error": "No items selected."}), 400
            items = [it for it in items if it["id"] in wanted]
        if not items:
            return jsonify({"ok": False, "error": "No matching audio."}), 400

        def _slug(txt):
            txt = re.sub(r"[^\w\s-]", "", str(txt or "")).strip()
            return re.sub(r"[\s-]+", "_", txt) or "na"

        def _csv_safe(val):
            """Neutralise CSV/Excel formula injection: a leading =,+,-,@ (or
            tab/CR) makes Excel evaluate the cell as a formula."""
            s = "" if val is None else str(val)
            if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
                return "'" + s
            return s

        buf = io.BytesIO()
        manifest_rows = [(
            "filename", "item_id", "kind", "subject", "topic",
            "question_type", "grade", "status", "question_text",
        )]
        used_names = set()

        def _unique(name):
            base, ext = os.path.splitext(name)
            candidate, i = name, 2
            while candidate in used_names:
                candidate = f"{base}_{i}{ext}"
                i += 1
            used_names.add(candidate)
            return candidate

        written = 0
        missing = []  # (item_id, filename) that were expected but not on disk
        voiceover_dir = Path(VOICEOVER_DIR)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for it in items:
                prefix = f"{_slug(it['subject'])}_{_slug(it['topic'])}_{it['id']}"
                sources = []
                if it.get("question_file"):
                    sources.append(("question", it["question_file"], f"{prefix}_question.mp3"))
                for h in it.get("hints", []):
                    sources.append((f"hint{h['n']}", h["file"], f"{prefix}_hint{h['n']}.mp3"))

                for kind, src_name, nice_name in sources:
                    src_path = voiceover_dir / src_name
                    if not src_path.exists():
                        missing.append((it["id"], src_name))
                        continue
                    arcname = _unique(nice_name)
                    zf.write(src_path, arcname)
                    written += 1
                    manifest_rows.append(tuple(_csv_safe(c) for c in (
                        arcname, it["id"], kind, it["subject"], it["topic"],
                        it["type"], it["grade"], it["status"], it["text"],
                    )))

            csv_buf = io.StringIO()
            csv.writer(csv_buf).writerows(manifest_rows)
            zf.writestr("manifest.csv", csv_buf.getvalue())

            # If anything expected was missing on disk, record it in the ZIP so
            # the hand-off is never silently short a file.
            if missing:
                note = "item_id,missing_file\n" + "\n".join(
                    f"{iid},{fn}" for iid, fn in missing
                )
                zf.writestr("MISSING_FILES.txt", note)

        if written == 0:
            return jsonify({"ok": False, "error": "No audio files found on disk."}), 404

        buf.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="worldwise-voiceovers.zip"'}
        if missing:
            # surface count without breaking the download
            headers["X-Missing-Files"] = str(len(missing))
        return Response(buf.getvalue(), mimetype="application/zip", headers=headers)

    @app.route("/questions/<item_id>")
    def question_detail(item_id):
        q = questions.get(item_id)
        if not q:
            abort(404)
        item_state = get_item_state(state, item_id)
        audio_exists = has_audio(item_id)
        ssml = get_ssml_for_question(q, item_state.get("speech_override"))

        # Build hint data
        hint_data = []
        for h in range(1, 4):
            hint_text = q.get(f"hint{h}", "")
            if hint_text:
                hs = get_hint_state(state, item_id, h)
                hint_data.append({
                    "num": h,
                    "text": hint_text,
                    "state": hs,
                    "audio_exists": has_hint_audio(item_id, h),
                    "ssml": get_ssml_for_hint(hint_text, hs.get("speech_override")),
                })

        # Find prev/next for navigation
        idx = next((i for i, qq in enumerate(questions_list) if qq["item_id"] == item_id), None)
        prev_id = questions_list[idx - 1]["item_id"] if idx and idx > 0 else None
        next_id = questions_list[idx + 1]["item_id"] if idx is not None and idx < len(questions_list) - 1 else None

        return render_template("question_detail.html",
                               q=q, state=item_state,
                               audio_exists=audio_exists,
                               ssml=ssml,
                               hint_data=hint_data,
                               template_name=TEMPLATE_NAMES.get(q.get("template_id"), "Unknown"),
                               prev_id=prev_id, next_id=next_id)

    # --- API routes ---

    @app.route("/api/generate/<item_id>", methods=["POST"])
    def api_generate(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        item_state = get_item_state(state, item_id)
        no_answers = request.args.get("no_answers") == "1"
        try:
            ssml, file_size = generate_for_question(q, item_state, no_answers=no_answers)
            update_item_state(state, item_id, generated_at=now_iso())
            return jsonify({"ok": True, "ssml": ssml, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/approve/<item_id>", methods=["POST"])
    def api_approve(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        update_item_state(state, item_id, status="approved",
                          approved_at=now_iso(), flag_note="")
        return jsonify({"ok": True})

    @app.route("/api/flag/<item_id>", methods=["POST"])
    def api_flag(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        note = data.get("note", "")
        update_item_state(state, item_id, status="flagged", flag_note=note)
        return jsonify({"ok": True})

    @app.route("/api/update-speech/<item_id>", methods=["POST"])
    def api_update_speech(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        updates = {}
        if "ssml" in data:
            updates["speech_override"] = data["ssml"] or None
        if "speed" in data:
            updates["speed_override"] = data["speed"] or None
        update_item_state(state, item_id, **updates)
        return jsonify({"ok": True})

    @app.route("/api/preview-ssml/<item_id>")
    def api_preview_ssml(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        ssml = get_ssml_for_question(q)
        return jsonify({"ssml": ssml})

    # --- Undo routes ---

    @app.route("/api/undo/<item_id>", methods=["POST"])
    def api_undo(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        update_item_state(state, item_id, status="pending",
                          approved_at=None, flag_note="")
        return jsonify({"ok": True})

    @app.route("/api/undo-hint/<item_id>/<int:hint_num>", methods=["POST"])
    def api_undo_hint(item_id, hint_num):
        if item_id not in questions or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        update_hint_state(state, item_id, hint_num,
                          status="pending", approved_at=None, flag_note="")
        return jsonify({"ok": True})

    # --- Hint API routes ---

    @app.route("/api/generate-hint/<item_id>/<int:hint_num>", methods=["POST"])
    def api_generate_hint(item_id, hint_num):
        q = questions.get(item_id)
        if not q or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        if not q.get(f"hint{hint_num}"):
            return jsonify({"error": f"No hint{hint_num} text"}), 400
        hs = get_hint_state(state, item_id, hint_num)
        try:
            ssml, file_size = generate_for_hint(q, hint_num, hs)
            update_hint_state(state, item_id, hint_num, generated_at=now_iso())
            return jsonify({"ok": True, "ssml": ssml, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Per-option voice-over (Phase 3) ---

    @app.route("/api/generate-option/<item_id>/<int:option_num>", methods=["POST"])
    def api_generate_option(item_id, option_num):
        q = questions.get(item_id)
        if not q or option_num not in (1, 2, 3, 4):
            return jsonify({"error": "Not found"}), 404
        if not q.get(f"option{option_num}"):
            return jsonify({"error": f"No option{option_num} text"}), 400
        os_state = get_option_state(state, item_id, option_num)
        try:
            ssml, file_size = generate_for_option(q, option_num, os_state)
            update_option_state(state, item_id, option_num, generated_at=now_iso())
            return jsonify({"ok": True, "ssml": ssml, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/generate-tf/<item_id>/<which>", methods=["POST"])
    def api_generate_tf(item_id, which):
        """Generate a voice-over for a True/False answer word ('true' or 'false')."""
        q = questions.get(item_id)
        if not q or which.lower() not in ("true", "false"):
            return jsonify({"error": "Not found"}), 404
        tf_state = get_option_state(state, item_id, f"tf_{which.lower()}")
        try:
            ssml, file_size = generate_for_tf(q, which, tf_state)
            update_option_state(state, item_id, f"tf_{which.lower()}", generated_at=now_iso())
            return jsonify({"ok": True, "ssml": ssml, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Audio version history / revert (question, hint, option) ---

    _STEM_RE = re.compile(r"^[0-9A-Za-z_-]+$")  # allowlist — stem goes into a filesystem glob

    @app.route("/api/audio-versions/<stem>")
    def api_audio_versions(stem):
        """List previous takes of an audio file. stem e.g. '20012002-option3'."""
        if not _STEM_RE.match(stem):
            return jsonify({"error": "bad stem"}), 400
        from .voiceover_engine import get_audio_versions
        vers = []
        for vf in get_audio_versions(stem):
            m = re.search(r"-v(\d+)\.mp3$", vf.name)
            if m:
                vers.append({"version": int(m.group(1)), "url": f"/audio/{vf.name}"})
        return jsonify({"stem": stem, "versions": vers})

    @app.route("/api/restore-audio/<stem>/<int:version_num>", methods=["POST"])
    def api_restore_audio(stem, version_num):
        """Revert an audio file to a previous take."""
        if not _STEM_RE.match(stem):
            return jsonify({"error": "bad stem"}), 400
        from .voiceover_engine import restore_audio_version
        try:
            restore_audio_version(stem, version_num)
            return jsonify({"ok": True})
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/approve-hint/<item_id>/<int:hint_num>", methods=["POST"])
    def api_approve_hint(item_id, hint_num):
        if item_id not in questions or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "audio_text")
        update_hint_state(state, item_id, hint_num,
                          status="approved", mode=mode,
                          approved_at=now_iso(), flag_note="")
        return jsonify({"ok": True})

    @app.route("/api/flag-hint/<item_id>/<int:hint_num>", methods=["POST"])
    def api_flag_hint(item_id, hint_num):
        if item_id not in questions or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(silent=True) or {}
        note = data.get("note", "")
        update_hint_state(state, item_id, hint_num,
                          status="flagged", flag_note=note)
        return jsonify({"ok": True})

    @app.route("/api/update-hint-speech/<item_id>/<int:hint_num>", methods=["POST"])
    def api_update_hint_speech(item_id, hint_num):
        if item_id not in questions or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(silent=True) or {}
        updates = {}
        if "ssml" in data:
            updates["speech_override"] = data["ssml"] or None
        if "speed" in data:
            updates["speed_override"] = data["speed"] or None
        update_hint_state(state, item_id, hint_num, **updates)
        return jsonify({"ok": True})

    @app.route("/api/preview-hint-ssml/<item_id>/<int:hint_num>")
    def api_preview_hint_ssml(item_id, hint_num):
        q = questions.get(item_id)
        if not q or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        hint_text = q.get(f"hint{hint_num}", "")
        if not hint_text:
            return jsonify({"error": f"No hint{hint_num}"}), 400
        ssml = get_ssml_for_hint(hint_text)
        return jsonify({"ssml": ssml})

    @app.route("/api/update-option-speech/<item_id>/<int:option_num>", methods=["POST"])
    def api_update_option_speech(item_id, option_num):
        if item_id not in questions or option_num not in (1, 2, 3, 4):
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(silent=True) or {}
        updates = {}
        if "ssml" in data:
            updates["speech_override"] = data["ssml"] or None
        if "speed" in data:
            updates["speed_override"] = data["speed"] or None
        update_option_state(state, item_id, option_num, **updates)
        return jsonify({"ok": True})

    @app.route("/api/speech-text/<item_id>")
    def api_speech_text(item_id):
        """Return the current 'how it's read' text for question / a hint / an option.

        Query: kind=question|hint|option, num=<n>. Returns {override, default} — the
        reviewer's saved override (if any) and the auto-generated default, so the edit box
        can be pre-filled and 'Reset' can restore the default. Does NOT change any text.
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        kind = request.args.get("kind", "question")
        num = request.args.get("num")
        try:
            if kind == "question":
                st = get_item_state(state, item_id)
                # Final Stage reads the QUESTION TEXT ONLY (options have their own VOs), so
                # the editor default must match that — not the bundled build_ssml.
                default = get_ssml_for_question(q, no_answers=True)
            elif kind == "hint" and num:
                st = get_hint_state(state, item_id, int(num))
                default = get_ssml_for_hint(q.get(f"hint{num}", ""))
            elif kind == "option" and num:
                st = get_option_state(state, item_id, int(num))
                default = get_ssml_for_option(q.get(f"option{num}", ""))
            else:
                return jsonify({"error": "bad kind/num"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"override": st.get("speech_override") or "", "default": default,
                        "speed": st.get("speed_override") or ""})

    @app.route("/api/stats")
    def api_stats():
        return jsonify(_compute_stats(questions_list, state))

    @app.route("/api/pipeline-stats")
    def api_pipeline_stats():
        """Read-only, auth-exempt pipeline readiness export.

        Returns aggregate counts plus a per-ItemID readiness map so the
        voiceover/hint approval state can be cross-referenced against the
        images (Airtable) and the database. Purely additive; no writes."""
        items = {}
        for q in questions_list:
            item_id = q["item_id"]
            s = state.get(item_id, {})
            hints = {}
            for h in range(1, 4):
                if q.get(f"hint{h}"):
                    hs = s.get("hints", {}).get(f"hint{h}", {})
                    hints[f"hint{h}"] = {
                        "status": hs.get("status", "pending"),
                        "has_audio": has_hint_audio(item_id, h),
                    }
            # options present in the spreadsheet (for completeness gating)
            opt_count = sum(1 for n in range(1, 5) if str(q.get(f"option{n}", "")).strip())
            # image readiness (Georgia): question image + per-answer images
            img_s = get_image_item_state(image_state, item_id) or {}
            answer_imgs = {}
            for n in range(1, 5):
                slot = (img_s.get("answer_images", {}) or {}).get(str(n), {}) or {}
                answer_imgs[str(n)] = {
                    "status": slot.get("status", "pending"),
                    "has_image": has_answer_image(item_id, n),
                }
            q_img_slot = img_s.get("question_image", {}) or {}
            items[item_id] = {
                "subject": q["subject"],
                "topic": q["topic"],
                "question_type": q.get("question_type", ""),
                "vo_status": s.get("status", "pending"),
                "has_vo_audio": has_audio(item_id),
                "hints": hints,
                # spreadsheet content presence
                "has_question_text": bool(str(q.get("question_text", "")).strip()),
                "option_count": opt_count,
                "has_answer": bool(str(q.get("answer", "")).strip()),
                "image_required": str(q.get("image_required", "")).strip().upper(),
                # image pipeline (Georgia)
                "question_image": {
                    "status": q_img_slot.get("status", "pending"),
                    "has_image": has_question_image(item_id),
                },
                "answer_images": answer_imgs,
            }
        return jsonify({
            "summary": _compute_stats(questions_list, state),
            "items": items,
        })

    @app.route("/api/bulk-generate", methods=["POST"])
    def api_bulk_generate():
        data = request.get_json(silent=True) or {}
        item_ids = data.get("item_ids", [])
        hint_jobs = data.get("hint_jobs", [])
        valid_ids = [iid for iid in item_ids if iid in questions]
        valid_hints = [hj for hj in hint_jobs
                       if hj.get("item_id") in questions
                       and hj.get("hint_num") in (1, 2, 3)]
        total = len(valid_ids) + len(valid_hints)
        if total == 0:
            return jsonify({"error": "No valid jobs"}), 400
        bulk_queue.put((valid_ids, valid_hints))
        return jsonify({"ok": True, "count": total})

    @app.route("/api/bulk-status")
    def api_bulk_status():
        with bulk_lock:
            return jsonify(bulk_status.copy())

    # --- Image generation ---

    print("Loading image modules...")
    print("  image_state OK")
    print("  image_engine OK")
    print("  airtable_loader OK")
    print("  airtable_push OK")

    print("Loading image state...")
    image_state = load_image_state()

    print("Loading final-approval ledger...")
    final_ledger = final_state_mod.load_final_state()
    print(f"  {len(final_state_mod.approved_ids(final_ledger))} question(s) already Final Approved")

    # Load Airtable data — use local cache if available (instant),
    # otherwise fetch from API in background (~60s)
    print("Loading Airtable images...")
    cached = load_cached_airtable_images()
    airtable_images = cached if cached else {}
    if airtable_images:
        print(f"  Loaded {len(airtable_images)} images from cache (refreshing in background)")

    # ALWAYS refresh Airtable in the background on startup, then periodically. This keeps
    # image-preview URLs fresh (Airtable attachment URLs expire after a few hours) so
    # reviewers never see blank previews and nobody has to click Sync.
    _AIRTABLE_REFRESH_SECONDS = 6 * 3600  # every 6 hours

    def _refresh_airtable_once():
        try:
            fresh = load_airtable_images()
            airtable_images.clear()
            airtable_images.update(fresh)
            save_airtable_cache(airtable_images)
            print(f"  Airtable refresh complete: {len(fresh)} images (urls updated)")
        except Exception as e:
            print(f"  Airtable refresh failed (keeping previous cache): {e}")

    def _airtable_refresh_loop():
        import time as _t
        _refresh_airtable_once()  # once at startup
        while True:
            _t.sleep(_AIRTABLE_REFRESH_SECONDS)
            _refresh_airtable_once()
    threading.Thread(target=_airtable_refresh_loop, daemon=True).start()

    # ALL questions get images eventually — show them all on the image page
    image_questions_list = questions_list
    print(f"  {len(image_questions_list)} total questions for image page")

    @app.route("/generated-images/<path:filename>")
    def serve_generated_image(filename):
        return send_from_directory(IMAGE_DATA_DIR, filename)

    @app.route("/images")
    def image_list():
        return render_template("image_list.html",
                               questions_json=json.dumps(
                                   _questions_for_image_client(image_questions_list, image_state, airtable_images),
                                   ensure_ascii=False),
                               subjects=subjects,
                               topics_by_subject=json.dumps(topics_by_subject))

    @app.route("/images/<item_id>")
    def image_detail(item_id):
        q = questions.get(item_id)
        if not q:
            abort(404)

        img_state = get_image_item_state(image_state, item_id)
        has_q_img = has_question_image(item_id)

        # Airtable data for this question
        at_data = airtable_images.get(item_id)

        # Build prompts — use Airtable description if available
        at_desc = at_data.get("description", "") if at_data else ""
        default_q_prompt = build_question_prompt(q, airtable_desc=at_desc)
        question_prompt = img_state["question_image"].get("prompt") or default_q_prompt

        # Answer prompts
        answer_prompts = {}
        answer_has_generated = {}
        for i in range(1, 5):
            opt = q.get(f"option{i}", "")
            if opt:
                saved = img_state["answer_images"].get(str(i), {}).get("prompt", "")
                answer_prompts[str(i)] = saved or build_answer_prompt(q, i, opt)
                answer_has_generated[str(i)] = has_answer_image(item_id, i)

        # Find prev/next in image_questions_list
        idx = next((i for i, qq in enumerate(image_questions_list) if qq["item_id"] == item_id), None)
        prev_id = image_questions_list[idx - 1]["item_id"] if idx and idx > 0 else None
        next_id = image_questions_list[idx + 1]["item_id"] if idx is not None and idx < len(image_questions_list) - 1 else None

        return render_template("image_detail.html",
                               q=q, img_state=img_state,
                               has_q_image=has_q_img,
                               at_data=at_data,
                               question_prompt=question_prompt,
                               default_question_prompt=default_q_prompt,
                               answer_prompts=answer_prompts,
                               answer_has_generated=answer_has_generated,
                               prev_id=prev_id, next_id=next_id)

    # --- Final Stage tab (Phase 1: read-only assembly + completeness) ---

    @app.route("/final")
    def final_list():
        presence = final_stage.build_presence()  # one dir listing, not 100k stat() calls
        rows = []
        for q in questions_list:
            row = final_stage.summary_row(q, image_state, state, airtable_images, presence=presence)
            led = final_state_mod.get_final_item(final_ledger, row["id"])
            row["approved"] = bool(led.get("approved"))
            row["flagged"] = bool(led.get("flagged"))
            rows.append(row)
        complete_n = sum(1 for r in rows if r["complete"])
        approved_n = sum(1 for r in rows if r["approved"])
        return render_template("final_list.html",
                               rows_json=json.dumps(rows, ensure_ascii=False),
                               subjects=subjects,
                               total=len(rows),
                               complete_n=complete_n,
                               approved_n=approved_n)

    @app.route("/final/<item_id>")
    def final_detail(item_id):
        q = questions.get(item_id)
        if not q:
            abort(404)
        assembled = final_stage.assemble(q, image_state, state, airtable_images)

        idx = next((i for i, qq in enumerate(questions_list) if qq["item_id"] == item_id), None)
        prev_id = questions_list[idx - 1]["item_id"] if idx and idx > 0 else None
        next_id = questions_list[idx + 1]["item_id"] if idx is not None and idx < len(questions_list) - 1 else None

        approval = final_state_mod.get_final_item(final_ledger, item_id)
        return render_template("final_detail.html",
                               a=assembled, prev_id=prev_id, next_id=next_id,
                               approval=approval)

    @app.route("/api/final/generate-all/<item_id>", methods=["POST"])
    def api_final_generate_all(item_id):
        """Generate every MISSING piece of a question in one go.

        By default only fills gaps (never overwrites existing media). Pass
        {"force": true} to regenerate everything. Returns a per-part result list.
        Reuses the same generators the individual buttons use — nothing new is
        written beyond the media files, and nothing is deleted.
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        force = bool(data.get("force"))
        # Optional image prompt typed by the reviewer (same box as the single-image button).
        typed_prompt = (data.get("image_prompt") or "").strip()
        results = []

        def _do(part, exists, fn):
            if exists and not force:
                results.append({"part": part, "status": "skipped", "reason": "already present"})
                return
            try:
                fn()
                results.append({"part": part, "status": "generated"})
            except Exception as e:
                results.append({"part": part, "status": "error", "error": str(e)})

        qtype = q.get("question_type", "")
        is_tf = qtype == "True/False"
        is_written = qtype == "Written"

        # Question image — NEVER send an empty prompt to OpenAI (wastes money on a blank
        # image). Use the reviewer's typed prompt, else the saved brief (Airtable desc /
        # image_description / notes). If there's genuinely no brief, skip and say so.
        at_desc = (airtable_images.get(item_id, {}) or {}).get("description", "")
        img_prompt = typed_prompt or build_question_prompt(q, airtable_desc=at_desc) or q.get("image_description", "")
        img_prompt = (img_prompt or "").strip()
        if has_question_image(item_id) and not force:
            results.append({"part": "question-image", "status": "skipped", "reason": "already present"})
        elif not img_prompt:
            results.append({"part": "question-image", "status": "skipped",
                            "reason": "no image brief — add one, then generate the image"})
        else:
            try:
                generate_question_image(q, img_prompt)
                results.append({"part": "question-image", "status": "generated"})
            except Exception as e:
                results.append({"part": "question-image", "status": "error", "error": str(e)})

        # Question voice-over
        def _gen_q_vo():
            generate_for_question(q, get_item_state(state, item_id))
            update_item_state(state, item_id, generated_at=now_iso())
        _do("question-vo", has_audio(item_id), _gen_q_vo)

        # Per-hint voice-overs (only levels that have hint text)
        for n in (1, 2, 3):
            if not q.get(f"hint{n}"):
                continue
            def _gen_hint(n=n):
                generate_for_hint(q, n, get_hint_state(state, item_id, n))
                update_hint_state(state, item_id, n, generated_at=now_iso())
            _do(f"hint{n}-vo", has_hint_audio(item_id, n), _gen_hint)

        # Per-option voice-overs (skip True/False + Written — no options list)
        if not is_tf and not is_written:
            for n in (1, 2, 3, 4):
                if not q.get(f"option{n}"):
                    continue
                def _gen_opt(n=n):
                    generate_for_option(q, n, get_option_state(state, item_id, n))
                    update_option_state(state, item_id, n, generated_at=now_iso())
                _do(f"option{n}-vo", has_option_audio(item_id, n), _gen_opt)

        generated = sum(1 for r in results if r["status"] == "generated")
        errors = [r for r in results if r["status"] == "error"]
        return jsonify({
            "ok": len(errors) == 0,
            "generated": generated,
            "results": results,
        })

    @app.route("/api/final/edit/<item_id>", methods=["POST"])
    def api_final_edit(item_id):
        """Edit ONE field of a question and write it straight to the live Google Sheet.

        Body: {"field": "question_text"|"option1".."option4"|"answer"|"hint1..3"|..., "value": "..."}
        Writes to the master sheet (source of truth), logs the change, and updates the
        in-memory question so the UI reflects it immediately. Requires live Sheets mode.
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        if data_source_status["mode"] != "live":
            return jsonify({"error": "Editing requires live Google Sheets (currently on stale fallback)"}), 409
        data = request.get_json(silent=True) or {}
        field = data.get("field", "")
        new_value = data.get("value", "")
        if field not in gsheets_loader.FIELD_TO_HEADER:
            return jsonify({"error": f"Field '{field}' is not editable"}), 400
        new_value = "" if new_value is None else str(new_value)
        try:
            old_value, cell = gsheets_loader.update_field(q, field, new_value)
        except Exception as e:
            print(f"  [edit] FAILED {item_id}.{field}: {e}")
            return jsonify({"error": str(e)}), 502
        # Update in-memory so the app shows the new value right away.
        q[field] = new_value
        # Log the change (append-only trail on the volume).
        _log_edit(item_id, field, old_value, new_value, data.get("by"))
        return jsonify({"ok": True, "field": field, "old": old_value, "new": new_value, "cell": cell})

    @app.route("/api/final/approve/<item_id>", methods=["POST"])
    def api_final_approve(item_id):
        """Mark a question Final Approved — ONLY if it passes all completeness gates.

        Server re-checks completeness (never trusts the client). Approved questions
        become the upload manifest; the terminal uploader inserts them into the DB.
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        assembled = final_stage.assemble(q, image_state, state, airtable_images)
        if not assembled["complete"]:
            failed = [g["label"] for g in assembled["gates"] if not g["ok"]]
            return jsonify({"ok": False,
                            "error": "Not complete — cannot approve",
                            "failed_gates": failed}), 400
        data = request.get_json(silent=True) or {}
        by = data.get("by")
        item = final_state_mod.set_approved(final_ledger, item_id, True, by=by)
        print(f"  [final] Approved {item_id} for upload")
        return jsonify({"ok": True, "approved": True, "approved_at": item["approved_at"]})

    @app.route("/api/final/unapprove/<item_id>", methods=["POST"])
    def api_final_unapprove(item_id):
        """Undo a Final Approval (e.g. reviewer changed their mind)."""
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        final_state_mod.set_approved(final_ledger, item_id, False)
        print(f"  [final] Unapproved {item_id}")
        return jsonify({"ok": True, "approved": False})

    @app.route("/api/final/flag/<item_id>", methods=["POST"])
    def api_final_flag(item_id):
        """Flag a question with a note (why it's not being approved), or clear the flag."""
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        flagged = bool(data.get("flagged", True))
        note = (data.get("note") or "").strip()
        final_state_mod.set_flag(final_ledger, item_id, flagged, note, by=data.get("by"))
        return jsonify({"ok": True, "flagged": flagged, "note": note})

    @app.route("/api/final/manifest")
    def api_final_manifest():
        """Export the upload manifest: all Final Approved questions + their assets.

        This is what the terminal uploader will read. Read-only; no DB access.
        """
        out = []
        for item_id in final_state_mod.approved_ids(final_ledger):
            q = questions.get(item_id)
            if not q:
                continue  # question no longer in the sheet — skip, don't guess
            assembled = final_stage.assemble(q, image_state, state, airtable_images)
            ledger = final_state_mod.get_final_item(final_ledger, item_id)
            out.append({
                "item_id": item_id,
                "subject": assembled["subject"],
                "topic": assembled["topic"],
                "question_type": assembled["question_type"],
                "template_id": assembled["template_id"],
                "answer": assembled["answer"],
                "still_complete": assembled["complete"],
                "approved_at": ledger.get("approved_at"),
                "approved_by": ledger.get("approved_by"),
                "uploaded_at": ledger.get("uploaded_at"),
            })
        return jsonify({"count": len(out), "questions": out})

    @app.route("/api/final/stats")
    def api_final_stats():
        presence = final_stage.build_presence()
        rows = [final_stage.summary_row(q, image_state, state, airtable_images, presence=presence)
                for q in questions_list]
        approved = sum(1 for q in questions_list
                       if final_state_mod.get_final_item(final_ledger, q["item_id"]).get("approved"))
        return jsonify({
            "total": len(rows),
            "complete": sum(1 for r in rows if r["complete"]),
            "approved": approved,
        })

    @app.route("/api/images/upload/<item_id>", methods=["POST"])
    def api_upload_image(item_id):
        """Upload a hand-made image (e.g. from ChatGPT) for question/option/hint.

        Accepts any raster (PNG/JPG/WebP) or a fake-SVG (raster extracted); saves it as the
        local PNG so it flows through the normal approve->WebP->Airtable path. Format is
        handled here, so it doesn't matter what Georgia downloads.
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file uploaded"}), 400
        image_type = request.form.get("image_type", "question")
        num = request.form.get("num")
        # target local PNG path (same names the rest of the app uses)
        if image_type == "answer" and num:
            stem = f"{item_id}-answer{num}"; itype, onum = "answer", int(num)
        elif image_type == "hint" and num:
            stem = f"{item_id}-hint{num}"; itype, onum = "hint", int(num)
        else:
            stem = f"{item_id}-question"; itype, onum = "question", None
        try:
            from PIL import Image as _Img
            import io as _io
            content = f.read()
            if content[:300].lstrip().startswith(b"<svg") or b"<svg" in content[:300]:
                raster = _extract_raster_from_svg(content)
                if raster is None:
                    return jsonify({"error": "That SVG has no embedded photo — upload a PNG/JPG."}), 400
                content = raster
            im = _Img.open(_io.BytesIO(content))
            im = im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")
            from .image_engine import _archive_current_image
            _archive_current_image(item_id, itype, onum)  # keep prior version
            out = IMG_ENGINE_DIR / f"{stem}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            im.save(out, format="PNG")
            # Reset approval/push state for this slot — the image changed (mirror generate).
            img_st = get_image_item_state(image_state, item_id)
            if itype == "question":
                img_st["question_image"]["approved_at"] = None
                img_st["question_image"]["pushed_at"] = None
            elif itype == "answer":
                ans = img_st["answer_images"].setdefault(str(onum), {})
                ans["approved_at"] = None; ans["pushed_at"] = None
            img_st["status"] = "pending"
            update_image_item_state(image_state, item_id, **img_st)
            return jsonify({"ok": True, "size": out.stat().st_size})
        except Exception as e:
            return jsonify({"error": f"Could not read that image: {e}"}), 400

    @app.route("/api/images/generate/<item_id>", methods=["POST"])
    def api_generate_image(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        prompt_override = data.get("prompt")
        size = data.get("size", "1024x1024")
        try:
            prompt, file_size = generate_question_image(q, prompt_override, size=size)
            # Update state — reset approval since image changed
            img_st = get_image_item_state(image_state, item_id)
            img_st["question_image"]["prompt"] = prompt
            img_st["question_image"]["generated_at"] = img_now_iso()
            img_st["question_image"]["approved_at"] = None
            img_st["question_image"]["canva_pushed_at"] = None
            img_st["status"] = "pending"
            update_image_item_state(image_state, item_id, **img_st)
            return jsonify({"ok": True, "prompt": prompt, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/images/generate-answer/<item_id>/<int:option_num>", methods=["POST"])
    def api_generate_answer_image(item_id, option_num):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        prompt_override = data.get("prompt")
        try:
            prompt, file_size = generate_answer_image(q, option_num, prompt_override)
            img_state = get_image_item_state(image_state, item_id)
            ans = img_state["answer_images"].setdefault(str(option_num), {})
            ans["prompt"] = prompt
            ans["generated_at"] = img_now_iso()
            update_image_item_state(image_state, item_id, **img_state)
            return jsonify({"ok": True, "prompt": prompt, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/images/generate-hint/<item_id>/<int:hint_num>", methods=["POST"])
    def api_generate_hint_image(item_id, hint_num):
        """Generate a HINT image (for the occasional hint that shows a picture)."""
        q = questions.get(item_id)
        if not q or hint_num not in (1, 2, 3):
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(silent=True) or {}
        prompt_override = data.get("prompt")
        use_q_img = bool(data.get("use_question_image"))
        try:
            prompt, file_size = generate_hint_image(q, hint_num, prompt_override,
                                                    use_question_image=use_q_img)
            return jsonify({"ok": True, "prompt": prompt, "size": file_size})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/images/approve/<item_id>", methods=["POST"])
    def api_approve_image(item_id):
        """Approve an image: convert PNG -> WebP and push straight to Airtable.

        (Canva staging step removed — the app now pushes clean WebP directly.)
        """
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        image_type = data.get("image_type", "question")
        option_num = data.get("option_num")
        hint_num = data.get("hint_num")

        # Update local state
        img_st = get_image_item_state(image_state, item_id)
        if image_type == "question":
            img_st["question_image"]["approved_at"] = img_now_iso()
        elif image_type == "answer" and option_num:
            ans = img_st["answer_images"].setdefault(str(option_num), {})
            ans["approved_at"] = img_now_iso()

        img_st["status"] = "approved"
        img_st["flag_note"] = ""
        update_image_item_state(image_state, item_id, **img_st)

        # Build public URL base for the image (Airtable downloads it server-side)
        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5050")
        scheme = "https" if "railway" in domain else "http"

        airtable_error = None
        pushed = False

        try:
            # Cache-buster so Airtable treats a regenerated image as new
            ts = int(time.time())
            if image_type == "question":
                png_path = IMG_ENGINE_DIR / f"{item_id}-question.png"
                webp_path = png_to_webp(png_path)
                image_url = f"{scheme}://{domain}/generated-images/{webp_path.name}?v={ts}"
                table_name, record_id, msg = at_push_question(q, image_url, airtable_images)
                img_st["question_image"]["pushed_at"] = img_now_iso()
                pushed = True
            elif image_type == "answer" and option_num:
                png_path = IMG_ENGINE_DIR / f"{item_id}-answer{option_num}.png"
                webp_path = png_to_webp(png_path)
                image_url = f"{scheme}://{domain}/generated-images/{webp_path.name}?v={ts}"
                table_name, record_id, msg = at_push_answer(q, int(option_num), image_url, airtable_images)
                ans = img_st["answer_images"].setdefault(str(option_num), {})
                ans["pushed_at"] = img_now_iso()
                pushed = True
            elif image_type == "hint" and hint_num:
                png_path = IMG_ENGINE_DIR / f"{item_id}-hint{hint_num}.png"
                webp_path = png_to_webp(png_path)
                image_url = f"{scheme}://{domain}/generated-images/{webp_path.name}?v={ts}"
                table_name, record_id, msg = at_push_hint(q, int(hint_num), image_url, airtable_images)
                pushed = True

            update_image_item_state(image_state, item_id, **img_st)
            if pushed:
                print(f"  Airtable push for {item_id} ({image_type}): {table_name} — {msg}")
        except Exception as e:
            airtable_error = str(e)
            print(f"  Airtable push error for {item_id}: {e}")

        return jsonify({
            "ok": True,
            "pushed": pushed,
            "airtable_error": airtable_error,
        })

    @app.route("/api/images/flag/<item_id>", methods=["POST"])
    def api_flag_image(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        note = data.get("note", "")
        img_state = get_image_item_state(image_state, item_id)
        img_state["status"] = "flagged"
        img_state["flag_note"] = note
        update_image_item_state(image_state, item_id, **img_state)
        return jsonify({"ok": True})

    @app.route("/api/images/undo/<item_id>", methods=["POST"])
    def api_undo_image(item_id):
        """Reset image state back to pending — undo approve/flag."""
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        img_st = get_image_item_state(image_state, item_id)
        img_st["status"] = "pending"
        img_st["flag_note"] = ""
        if "question_image" in img_st:
            img_st["question_image"]["approved_at"] = None
            img_st["question_image"]["canva_pushed_at"] = None
        update_image_item_state(image_state, item_id, **img_st)
        return jsonify({"ok": True})

    def _ensure_local_png_from_airtable(item_id):
        """If there's no local PNG but Airtable has a raster image, download+convert it to
        a local PNG so it can be edited. Returns (ok, error_message).

        OpenAI images.edit needs a raster PNG. SVG/Lottie(JSON) can't be edited that way —
        the reviewer should use "Make new image" instead.
        """
        local = IMG_ENGINE_DIR / f"{item_id}-question.png"
        if local.exists():
            return True, None
        at = airtable_images.get(item_id) or {}
        qi = at.get("question_image") or {}
        url = qi.get("url", "")
        itype = (qi.get("type") or "").lower()
        if not url:
            return False, "No image to edit — generate one first."
        # SVG (incl. Canva "fake SVGs" with an embedded photo + cutout mask) and Lottie can't
        # be safely raster-edited without risking the transparency/cutout — the reviewer should
        # just generate a fresh one (Dan's call). Only tweak genuine raster images.
        if "svg" in itype or "json" in itype:
            return False, "This image can't be tweaked — click 'Make new image' to generate a fresh one."
        try:
            import requests as _rq
            from PIL import Image as _Img
            import io as _io
            r = _rq.get(url, timeout=30)
            r.raise_for_status()
            im = _Img.open(_io.BytesIO(r.content))
            im = im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")
            local.parent.mkdir(parents=True, exist_ok=True)
            im.save(local, format="PNG")
            return True, None
        except Exception as e:
            return False, f"Couldn't load the current image to edit: {e}"

    @app.route("/api/images/edit/<item_id>", methods=["POST"])
    def api_edit_image(item_id):
        """Edit an existing image with an instruction (e.g. 'remove the text')."""
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        edit_prompt = data.get("prompt", "")
        size = data.get("size", "1024x1024")
        if not edit_prompt:
            return jsonify({"error": "Edit instruction required"}), 400
        # If the shown image is Airtable-only (no local PNG), pull it down first so it's editable.
        ok, err = _ensure_local_png_from_airtable(item_id)
        if not ok:
            return jsonify({"error": err}), 400
        try:
            prompt, file_size = edit_question_image(q, edit_prompt, size=size)
            img_st = get_image_item_state(image_state, item_id)
            img_st["question_image"]["edit_prompt"] = prompt
            img_st["question_image"]["generated_at"] = img_now_iso()
            img_st["question_image"]["approved_at"] = None
            img_st["question_image"]["canva_pushed_at"] = None
            img_st["status"] = "pending"
            update_image_item_state(image_state, item_id, **img_st)
            return jsonify({"ok": True, "prompt": prompt, "size": file_size})
        except FileNotFoundError:
            return jsonify({"error": "No image exists to edit — generate one first"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/images/versions/<item_id>")
    def api_image_versions(item_id):
        """Get version history for an image."""
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404

        versions = []
        for vfile in get_version_files(item_id, "question"):
            # Extract version number from filename
            name = vfile.name
            versions.append({
                "filename": name,
                "url": f"/generated-images/{name}",
                "size": vfile.stat().st_size,
            })

        current_path = IMG_ENGINE_DIR / f"{item_id}-question.png"
        current = None
        if current_path.exists():
            current = {
                "filename": current_path.name,
                "url": f"/generated-images/{current_path.name}",
                "size": current_path.stat().st_size,
            }

        return jsonify({"current": current, "versions": versions})

    @app.route("/api/images/restore-version/<item_id>", methods=["POST"])
    def api_restore_version(item_id):
        """Restore a previous version as the current image."""
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        version_num = data.get("version")
        if not version_num:
            return jsonify({"error": "Version number required"}), 400
        try:
            restore_version(item_id, version_num, "question")
            img_st = get_image_item_state(image_state, item_id)
            img_st["question_image"]["generated_at"] = img_now_iso()
            img_st["question_image"]["approved_at"] = None
            img_st["question_image"]["canva_pushed_at"] = None
            img_st["status"] = "pending"
            update_image_item_state(image_state, item_id, **img_st)
            return jsonify({"ok": True})
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/images/save-prompt/<item_id>", methods=["POST"])
    def api_save_image_prompt(item_id):
        if item_id not in questions:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        image_type = data.get("image_type", "question")
        option_num = data.get("option_num")
        prompt = data.get("prompt", "")

        img_state = get_image_item_state(image_state, item_id)
        if image_type == "question":
            img_state["question_image"]["prompt"] = prompt
        elif image_type == "answer" and option_num:
            ans = img_state["answer_images"].setdefault(str(option_num), {})
            ans["prompt"] = prompt

        update_image_item_state(image_state, item_id, **img_state)
        return jsonify({"ok": True})

    @app.route("/api/images/push-airtable/<item_id>", methods=["POST"])
    def api_push_airtable(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404

        data = request.get_json(silent=True) or {}
        image_type = data.get("image_type", "question")
        option_num = data.get("option_num")

        # Build public URL for the generated image
        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5050")
        scheme = "https" if "railway" in domain else "http"

        if image_type == "question":
            try:
                webp_path = png_to_webp(IMG_ENGINE_DIR / f"{item_id}-question.png")
                image_url = f"{scheme}://{domain}/generated-images/{webp_path.name}"
                table_name, record_id, msg = at_push_question(q, image_url, airtable_images)
                img_st = get_image_item_state(image_state, item_id)
                img_st["question_image"]["pushed_at"] = img_now_iso()
                update_image_item_state(image_state, item_id, **img_st)
                return jsonify({"ok": True, "table": table_name, "message": msg})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        elif image_type == "answer" and option_num:
            try:
                webp_path = png_to_webp(IMG_ENGINE_DIR / f"{item_id}-answer{option_num}.png")
                image_url = f"{scheme}://{domain}/generated-images/{webp_path.name}"
                table_name, record_id, msg = at_push_answer(q, int(option_num), image_url, airtable_images)
                img_st = get_image_item_state(image_state, item_id)
                ans = img_st["answer_images"].setdefault(str(option_num), {})
                ans["pushed_at"] = img_now_iso()
                update_image_item_state(image_state, item_id, **img_st)
                return jsonify({"ok": True, "table": table_name, "message": msg})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"error": "Invalid image_type or missing option_num"}), 400

    @app.route("/api/images/bulk-generate", methods=["POST"])
    def api_bulk_generate_images():
        data = request.get_json(silent=True) or {}
        item_ids = data.get("item_ids", [])
        prompts = data.get("prompts", {})  # {item_id: prompt_text}
        size = data.get("size", "1024x1024")
        valid_ids = [iid for iid in item_ids if iid in questions]
        if not valid_ids:
            return jsonify({"error": "No valid item IDs"}), 400
        img_bulk_queue.put((valid_ids, prompts, size))
        return jsonify({"ok": True, "count": len(valid_ids)})

    @app.route("/api/images/bulk-status")
    def api_bulk_image_status():
        with img_bulk_lock:
            return jsonify(img_bulk_status.copy())

    @app.route("/api/images/stats")
    def api_image_stats():
        return jsonify(_compute_image_stats(image_questions_list, image_state))

    @app.route("/api/images/refresh-airtable", methods=["POST"])
    def api_refresh_airtable():
        """Re-fetch all Airtable data and update cache."""
        try:
            fresh = load_airtable_images()
            airtable_images.clear()
            airtable_images.update(fresh)
            save_airtable_cache(airtable_images)
            return jsonify({"ok": True, "count": len(fresh)})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Canva OAuth routes ---

    # In-memory store for OAuth state (code_verifier, state param)
    canva_oauth_state = {}

    @app.route("/canva/auth")
    def canva_auth():
        """Start Canva OAuth flow — Georgia visits this once to connect."""
        if canva_uploader.is_connected():
            return """<!DOCTYPE html><html><head><title>Canva Connected</title>
            <style>body{font-family:system-ui;max-width:500px;margin:60px auto;text-align:center}
            .btn{display:inline-block;padding:10px 20px;border-radius:6px;text-decoration:none;margin:8px}
            .btn-primary{background:#4CAF50;color:white}.btn-secondary{background:#eee;color:#333}
            </style></head><body>
            <h2>Canva is connected!</h2>
            <p>Images will auto-upload to Canva when you approve them.</p>
            <a class="btn btn-primary" href="/images">Back to Images</a>
            <br><a class="btn btn-secondary" href="/canva/disconnect">Disconnect &amp; Reconnect</a>
            </body></html>"""

        if not canva_uploader.get_client_id():
            return """<!DOCTYPE html><html><head><title>Canva Not Configured</title>
            <style>body{font-family:system-ui;max-width:500px;margin:60px auto;text-align:center}
            </style></head><body>
            <h2>Canva not configured</h2>
            <p>Missing CANVA_CLIENT_ID environment variable. Add it in Railway.</p>
            </body></html>""", 500

        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5050")
        scheme = "https" if "railway" in domain else "http"
        redirect_uri = f"{scheme}://{domain}/canva/callback"

        auth_url = canva_uploader.get_auth_url(redirect_uri, canva_oauth_state)
        return redirect(auth_url)

    @app.route("/canva/callback")
    def canva_callback():
        """Handle Canva OAuth callback — exchange code for tokens."""
        error = request.args.get("error")
        if error:
            error_desc = request.args.get("error_description", error)
            return f"""<!DOCTYPE html><html><head><title>Canva Error</title>
            <style>body{{font-family:system-ui;max-width:500px;margin:60px auto;text-align:center}}
            .error{{background:#fee;border:1px solid #fcc;padding:16px;border-radius:8px;margin:20px 0}}
            .btn{{display:inline-block;padding:10px 20px;background:#4CAF50;color:white;
            border-radius:6px;text-decoration:none}}</style></head><body>
            <h2>Canva authorization failed</h2>
            <div class="error">{error_desc}</div>
            <a class="btn" href="/canva/auth">Try again</a>
            </body></html>""", 400

        code = request.args.get("code")
        state = request.args.get("state")

        if not code:
            return """<!DOCTYPE html><html><body>
            <h2>Missing authorization code</h2>
            <a href="/canva/auth">Try again</a></body></html>""", 400

        # Verify state matches (CSRF protection)
        expected_state = canva_oauth_state.get("state")
        if state != expected_state:
            print(f"  [Canva] State mismatch: got={state}, expected={expected_state}")
            return """<!DOCTYPE html><html><body>
            <h2>State mismatch — please try again</h2>
            <a href="/canva/auth">Retry authorization</a></body></html>""", 403

        code_verifier = canva_oauth_state.get("code_verifier")
        if not code_verifier:
            return """<!DOCTYPE html><html><body>
            <h2>Session expired — please try again</h2>
            <a href="/canva/auth">Retry authorization</a></body></html>""", 400

        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5050")
        scheme = "https" if "railway" in domain else "http"
        redirect_uri = f"{scheme}://{domain}/canva/callback"

        try:
            canva_uploader.exchange_code(code, code_verifier, redirect_uri)
            return """<!DOCTYPE html><html><head><title>Canva Connected</title>
            <style>body{font-family:system-ui;max-width:500px;margin:60px auto;text-align:center}
            .success{background:#efe;border:1px solid #cfc;padding:16px;border-radius:8px;margin:20px 0}
            .btn{display:inline-block;padding:10px 20px;background:#4CAF50;color:white;
            border-radius:6px;text-decoration:none}</style></head><body>
            <h2>Canva connected!</h2>
            <div class="success">Images will now auto-upload to Canva when you approve them.</div>
            <a class="btn" href="/images">Go to Images</a>
            </body></html>"""
        except Exception as e:
            print(f"  [Canva] Token exchange error: {e}")
            return f"""<!DOCTYPE html><html><head><title>Canva Error</title>
            <style>body{{font-family:system-ui;max-width:500px;margin:60px auto;text-align:center}}
            .error{{background:#fee;border:1px solid #fcc;padding:16px;border-radius:8px;margin:20px 0;
            word-break:break-word}}.btn{{display:inline-block;padding:10px 20px;background:#4CAF50;
            color:white;border-radius:6px;text-decoration:none}}</style></head><body>
            <h2>Connection failed</h2>
            <div class="error">{e}</div>
            <a class="btn" href="/canva/auth">Try again</a>
            </body></html>""", 500

    @app.route("/canva/disconnect")
    def canva_disconnect():
        """Disconnect Canva — delete tokens and allow re-authorization."""
        canva_uploader.disconnect()
        return redirect("/canva/auth")

    @app.route("/api/canva/status")
    def api_canva_status():
        """Check if Canva is connected."""
        return jsonify({"connected": canva_uploader.is_connected()})

    # --- Image bulk worker ---

    # Number of parallel image generations (safe for Tier 1-2)
    IMG_PARALLEL = 3

    def _generate_one_image(item_id, prompt_override, size):
        """Generate a single image — called from thread pool."""
        q = questions.get(item_id)
        if not q:
            return item_id, None, "Not found"

        if not prompt_override:
            return item_id, None, "No prompt — type a prompt first"

        try:
            prompt, _ = generate_question_image(q, prompt_override, size=size)
            img_st = get_image_item_state(image_state, item_id)
            img_st["question_image"]["prompt"] = prompt
            img_st["question_image"]["generated_at"] = img_now_iso()
            update_image_item_state(image_state, item_id, **img_st)
            return item_id, prompt, None
        except Exception as e:
            print(f"  Image generation error for {item_id}: {e}")
            return item_id, None, str(e)

    def image_bulk_worker():
        while True:
            queue_item = img_bulk_queue.get()
            if queue_item is None:
                break

            # Unpack — supports (item_ids, prompts, size) tuple or just item_ids list
            if isinstance(queue_item, tuple) and len(queue_item) == 3:
                item_ids, prompts, size = queue_item
            elif isinstance(queue_item, tuple):
                item_ids, prompts = queue_item
                size = "1024x1024"
            else:
                item_ids, prompts, size = queue_item, {}, "1024x1024"

            # Build jobs list with prompts resolved
            jobs = []
            for item_id in item_ids:
                prompt_override = prompts.get(item_id)
                if not prompt_override:
                    img_st = get_image_item_state(image_state, item_id)
                    prompt_override = img_st["question_image"].get("prompt") or None
                jobs.append((item_id, prompt_override, size))

            with img_bulk_lock:
                img_bulk_status["running"] = True
                img_bulk_status["total"] = len(jobs)
                img_bulk_status["completed"] = 0
                img_bulk_status["errors"] = []

            print(f"  [Bulk] Starting {len(jobs)} images, {IMG_PARALLEL} parallel")

            with ThreadPoolExecutor(max_workers=IMG_PARALLEL) as pool:
                futures = {
                    pool.submit(_generate_one_image, item_id, prompt, sz): item_id
                    for item_id, prompt, sz in jobs
                }
                for future in as_completed(futures):
                    item_id, prompt, error = future.result()
                    with img_bulk_lock:
                        img_bulk_status["completed"] += 1
                        img_bulk_status["current_item"] = item_id
                        if error:
                            img_bulk_status["errors"].append({"item_id": item_id, "error": error})

            with img_bulk_lock:
                img_bulk_status["running"] = False
                img_bulk_status["current_item"] = None

            print(f"  [Bulk] Done — {img_bulk_status['completed']} completed, {len(img_bulk_status['errors'])} errors")
            img_bulk_queue.task_done()

    img_worker = threading.Thread(target=image_bulk_worker, daemon=True)
    img_worker.start()

    # --- Voiceover Bulk worker ---

    def bulk_worker():
        while True:
            job = bulk_queue.get()
            if job is None:
                break

            # Support both old format (list) and new format (tuple)
            if isinstance(job, tuple):
                item_ids, hint_jobs = job
            else:
                item_ids, hint_jobs = job, []

            total = len(item_ids) + len(hint_jobs)

            with bulk_lock:
                bulk_status["running"] = True
                bulk_status["total"] = total
                bulk_status["completed"] = 0
                bulk_status["errors"] = []
                bulk_status["current_type"] = "question"

            # Generate question audio
            for item_id in item_ids:
                with bulk_lock:
                    bulk_status["current_item"] = item_id
                    bulk_status["current_type"] = "question"

                q = questions.get(item_id)
                if not q:
                    with bulk_lock:
                        bulk_status["errors"].append({"item_id": item_id, "error": "Not found"})
                        bulk_status["completed"] += 1
                    continue

                item_state = get_item_state(state, item_id)
                try:
                    generate_for_question(q, item_state)
                    update_item_state(state, item_id, generated_at=now_iso())
                    time.sleep(0.5)
                except Exception as e:
                    with bulk_lock:
                        bulk_status["errors"].append({"item_id": item_id, "error": str(e)})

                with bulk_lock:
                    bulk_status["completed"] += 1

            # Generate hint audio
            for hj in hint_jobs:
                item_id = hj["item_id"]
                hint_num = hj["hint_num"]

                with bulk_lock:
                    bulk_status["current_item"] = f"{item_id} hint{hint_num}"
                    bulk_status["current_type"] = "hint"

                q = questions.get(item_id)
                if not q or not q.get(f"hint{hint_num}"):
                    with bulk_lock:
                        bulk_status["errors"].append({"item_id": item_id, "error": f"No hint{hint_num}"})
                        bulk_status["completed"] += 1
                    continue

                hs = get_hint_state(state, item_id, hint_num)
                try:
                    generate_for_hint(q, hint_num, hs)
                    update_hint_state(state, item_id, hint_num, generated_at=now_iso())
                    time.sleep(0.5)
                except Exception as e:
                    with bulk_lock:
                        bulk_status["errors"].append({"item_id": f"{item_id}:hint{hint_num}", "error": str(e)})

                with bulk_lock:
                    bulk_status["completed"] += 1

            with bulk_lock:
                bulk_status["running"] = False
                bulk_status["current_item"] = None
                bulk_status["current_type"] = None

            bulk_queue.task_done()

    worker = threading.Thread(target=bulk_worker, daemon=True)
    worker.start()

    return app


def _compute_stats(questions_list, state):
    """Compute progress stats by subject."""
    by_subject = {}
    total_approved = 0
    total_audio = 0
    total_flagged = 0
    total_hints = 0
    total_hints_audio = 0
    total_hints_approved = 0
    total_hints_flagged = 0

    for q in questions_list:
        subj = q["subject"] or "Unknown"
        if subj not in by_subject:
            by_subject[subj] = {"total": 0, "approved": 0, "flagged": 0,
                                "has_audio": 0, "pending": 0,
                                "hints_total": 0, "hints_audio": 0,
                                "hints_approved": 0, "hints_flagged": 0}
        by_subject[subj]["total"] += 1

        item_id = q["item_id"]
        s = state.get(item_id, {})
        status = s.get("status", "pending")

        if status == "approved":
            by_subject[subj]["approved"] += 1
            total_approved += 1
        elif status == "flagged":
            by_subject[subj]["flagged"] += 1
            total_flagged += 1
        else:
            by_subject[subj]["pending"] += 1

        if has_audio(item_id):
            by_subject[subj]["has_audio"] += 1
            total_audio += 1

        # Hint stats
        for h in range(1, 4):
            if q.get(f"hint{h}"):
                total_hints += 1
                by_subject[subj]["hints_total"] += 1
                if has_hint_audio(item_id, h):
                    total_hints_audio += 1
                    by_subject[subj]["hints_audio"] += 1
                hs = s.get("hints", {}).get(f"hint{h}", {})
                if hs.get("status") == "approved":
                    total_hints_approved += 1
                    by_subject[subj]["hints_approved"] += 1
                elif hs.get("status") == "flagged":
                    total_hints_flagged += 1
                    by_subject[subj]["hints_flagged"] += 1

    return {
        "by_subject": by_subject,
        "total": len(questions_list),
        "total_approved": total_approved,
        "total_audio": total_audio,
        "total_flagged": total_flagged,
        "total_hints": total_hints,
        "total_hints_audio": total_hints_audio,
        "total_hints_approved": total_hints_approved,
        "total_hints_flagged": total_hints_flagged,
    }


def _get_flagged(questions, state):
    """Get all flagged questions and hints with their notes."""
    flagged = []
    for item_id, s in state.items():
        if item_id not in questions:
            continue
        q = questions[item_id]
        if s.get("status") == "flagged":
            flagged.append({
                "item_id": item_id,
                "question_text": q["question_text"][:80],
                "subject": q["subject"],
                "note": s.get("flag_note", ""),
                "type": "question",
            })
        for h in range(1, 4):
            hs = s.get("hints", {}).get(f"hint{h}", {})
            if hs.get("status") == "flagged":
                flagged.append({
                    "item_id": item_id,
                    "question_text": f"Hint {h}: {q.get(f'hint{h}', '')[:60]}",
                    "subject": q["subject"],
                    "note": hs.get("flag_note", ""),
                    "type": "hint",
                })
    return flagged


def _questions_for_client(questions_list, state):
    """Build question list with hint summaries for client-side filtering."""
    result = []
    for q in questions_list:
        item_id = q["item_id"]
        s = state.get(item_id, {})

        hints = []
        for h in range(1, 4):
            hint_text = q.get(f"hint{h}", "")
            if hint_text:
                hs = s.get("hints", {}).get(f"hint{h}", {})
                hints.append({
                    "n": h,
                    "t": hint_text[:60],
                    "audio": has_hint_audio(item_id, h),
                    "status": hs.get("status", "pending"),
                    "mode": hs.get("mode", "audio_text"),
                })

        result.append({
            "id": item_id,
            "text": q["question_text"][:80],
            "subject": q["subject"],
            "topic": q["topic"],
            "sheet": q["sheet"],
            "type": q["question_type"],
            "status": s.get("status", "pending"),
            "audio": has_audio(item_id),
            "grade": q["grade"],
            "hints": hints,
        })
    return result


def _extract_raster_from_svg(svg_bytes):
    """Pull the real photo out of a 'fake SVG' (base64 raster embedded in an SVG wrapper).

    Canva exports wrap the image in an SVG and often embed TWO rasters: a small grayscale
    ALPHA MASK plus the full-colour photo. We must return the PHOTO, not the mask — so pick
    the LARGEST embedded raster (by decoded byte size). Returns raster bytes, or None if the
    SVG has no embedded raster (a genuine vector SVG).
    """
    import re
    import base64
    try:
        text = svg_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return None
    matches = re.findall(r'data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+?)["\')]', text)
    if not matches:
        # fall back to a looser match (no trailing delimiter captured)
        m = re.search(r'data:image/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)', text)
        matches = [m.group(1)] if m else []
    best = None
    for b64 in matches:
        try:
            raw = base64.b64decode(re.sub(r"\s+", "", b64))
        except Exception:
            continue
        if best is None or len(raw) > len(best):
            best = raw
    return best


def _log_edit(item_id, field, old_value, new_value, by):
    """Append an edit to a change log on the volume (audit trail for sheet writes)."""
    import json as _json
    log_path = DATA_DIR / "final_edit_log.jsonl"
    entry = {
        "at": now_iso(), "item_id": item_id, "field": field,
        "old": old_value, "new": new_value, "by": by,
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  [edit-log] could not write log: {e}")


def _questions_for_image_client(questions_list, image_state, at_images):
    """Build compact question list for image page client-side filtering.

    Order matches the spreadsheet (file → sheet → row).
    """
    result = []
    for idx, q in enumerate(questions_list):
        item_id = q["item_id"]
        s = image_state.get(item_id, {})
        at = at_images.get(item_id)
        has_at_img = bool(at and (at.get("question_image") or at.get("answer_images")))
        saved_prompt = s.get("question_image", {}).get("prompt", "")
        result.append({
            "idx": idx,  # preserve spreadsheet order
            "id": item_id,
            "text": q["question_text"][:80],
            "desc": q.get("notes", "")[:80],
            "saved_prompt": saved_prompt[:200] if saved_prompt else "",
            "subject": q["subject"],
            "category": q.get("category", ""),
            "topic": q["topic"],
            "sheet": q.get("sheet", ""),
            "img_req": q.get("image_required", ""),
            "has_at_image": has_at_img,
            "has_gen_image": has_question_image(item_id),
            "img_status": s.get("status", "pending"),
        })
    return result


def _compute_image_stats(questions_list, image_state):
    """Compute image generation stats."""
    total = len(questions_list)
    generated = 0
    approved = 0
    flagged = 0

    for q in questions_list:
        item_id = q["item_id"]
        if has_question_image(item_id):
            generated += 1
        s = image_state.get(item_id, {})
        status = s.get("status", "pending")
        if status == "approved":
            approved += 1
        elif status == "flagged":
            flagged += 1

    return {
        "total": total,
        "generated": generated,
        "approved": approved,
        "flagged": flagged,
    }
