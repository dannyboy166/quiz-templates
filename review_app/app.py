"""QuestionReview Flask app — voice over review tool for Zoe/Julie."""

import json
import os
import time
import threading
import queue
from pathlib import Path

from flask import (
    Flask, render_template, jsonify, request,
    send_from_directory, abort,
)

from .spreadsheet_loader import load_all_questions, TEMPLATE_NAMES
from .state import (
    load_state, save_state, get_item_state, update_item_state,
    has_audio, now_iso, VOICEOVER_DIR, DATA_DIR,
)
from .voiceover_engine import (
    get_ssml_for_question, generate_for_question,
)
from .image_state import (
    load_image_state, save_image_state, get_image_item_state,
    update_image_item_state, has_question_image, has_answer_image,
    IMAGE_DATA_DIR, now_iso as img_now_iso,
)
from .image_engine import (
    build_question_prompt, build_answer_prompt,
    generate_question_image, generate_answer_image,
)
from .airtable_loader import (
    load_airtable_images, load_cached_airtable_images,
    save_airtable_cache,
)
from .airtable_push import (
    push_question_image as at_push_question,
    push_answer_image as at_push_answer,
)

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

    project_root = Path(__file__).resolve().parent.parent

    # Load data on startup
    print("Loading spreadsheets...")
    questions, questions_list, subjects, topics_by_subject, sheets = load_all_questions()
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

    # --- Static file routes for project assets ---

    @app.route("/assets/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(project_root / "css", filename)

    @app.route("/assets/fonts/<path:filename>")
    def serve_fonts(filename):
        return send_from_directory(project_root / "fonts", filename)

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

    @app.route("/questions/<item_id>")
    def question_detail(item_id):
        q = questions.get(item_id)
        if not q:
            abort(404)
        item_state = get_item_state(state, item_id)
        audio_exists = has_audio(item_id)
        ssml = get_ssml_for_question(q, item_state.get("speech_override"))

        # Find prev/next for navigation
        idx = next((i for i, qq in enumerate(questions_list) if qq["item_id"] == item_id), None)
        prev_id = questions_list[idx - 1]["item_id"] if idx and idx > 0 else None
        next_id = questions_list[idx + 1]["item_id"] if idx is not None and idx < len(questions_list) - 1 else None

        return render_template("question_detail.html",
                               q=q, state=item_state,
                               audio_exists=audio_exists,
                               ssml=ssml,
                               template_name=TEMPLATE_NAMES.get(q.get("template_id"), "Unknown"),
                               prev_id=prev_id, next_id=next_id)

    # --- API routes ---

    @app.route("/api/generate/<item_id>", methods=["POST"])
    def api_generate(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        item_state = get_item_state(state, item_id)
        try:
            ssml, file_size = generate_for_question(q, item_state)
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

    @app.route("/api/stats")
    def api_stats():
        return jsonify(_compute_stats(questions_list, state))

    @app.route("/api/bulk-generate", methods=["POST"])
    def api_bulk_generate():
        data = request.get_json(silent=True) or {}
        item_ids = data.get("item_ids", [])
        valid_ids = [iid for iid in item_ids if iid in questions]
        if not valid_ids:
            return jsonify({"error": "No valid item IDs"}), 400
        bulk_queue.put(valid_ids)
        return jsonify({"ok": True, "count": len(valid_ids)})

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

    # Load Airtable data — use local cache if available (instant),
    # otherwise fetch from API in background (~60s)
    print("Loading Airtable images...")
    cached = load_cached_airtable_images()
    airtable_images = cached if cached else {}
    if airtable_images:
        print(f"  Loaded {len(airtable_images)} images from cache")
    else:
        print("  No cache — Airtable data will load in background. Use /api/images/refresh-airtable to fetch.")
        def _load_airtable_bg():
            try:
                fresh = load_airtable_images()
                airtable_images.update(fresh)
                save_airtable_cache(airtable_images)
                print(f"  Airtable background load complete: {len(fresh)} images")
            except Exception as e:
                print(f"  Airtable background load failed: {e}")
        threading.Thread(target=_load_airtable_bg, daemon=True).start()

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

    @app.route("/api/images/generate/<item_id>", methods=["POST"])
    def api_generate_image(item_id):
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        prompt_override = data.get("prompt")
        try:
            prompt, file_size = generate_question_image(q, prompt_override)
            # Update state
            img_state = get_image_item_state(image_state, item_id)
            img_state["question_image"]["prompt"] = prompt
            img_state["question_image"]["generated_at"] = img_now_iso()
            update_image_item_state(image_state, item_id, **img_state)
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

    @app.route("/api/images/approve/<item_id>", methods=["POST"])
    def api_approve_image(item_id):
        """Approve an image AND push it to Airtable in one step."""
        q = questions.get(item_id)
        if not q:
            return jsonify({"error": "Question not found"}), 404
        data = request.get_json(silent=True) or {}
        image_type = data.get("image_type", "question")
        option_num = data.get("option_num")

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

        # Push to Airtable automatically
        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost:5050")
        scheme = "https" if "railway" in domain else "http"
        push_error = None

        try:
            if image_type == "question":
                filename = f"{item_id}-question.png"
                image_url = f"{scheme}://{domain}/generated-images/{filename}"
                table_name, record_id, msg = at_push_question(q, image_url, airtable_images)
                img_st["question_image"]["pushed_at"] = img_now_iso()
            elif image_type == "answer" and option_num:
                filename = f"{item_id}-answer{option_num}.png"
                image_url = f"{scheme}://{domain}/generated-images/{filename}"
                table_name, record_id, msg = at_push_answer(q, int(option_num), image_url, airtable_images)
                ans = img_st["answer_images"].setdefault(str(option_num), {})
                ans["pushed_at"] = img_now_iso()

            update_image_item_state(image_state, item_id, **img_st)
        except Exception as e:
            push_error = str(e)
            print(f"  Airtable push error for {item_id}: {e}")

        return jsonify({
            "ok": True,
            "pushed": push_error is None,
            "push_error": push_error,
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
            filename = f"{item_id}-question.png"
            image_url = f"{scheme}://{domain}/generated-images/{filename}"
            try:
                table_name, record_id, msg = at_push_question(q, image_url, airtable_images)
                img_st = get_image_item_state(image_state, item_id)
                img_st["question_image"]["pushed_at"] = img_now_iso()
                update_image_item_state(image_state, item_id, **img_st)
                return jsonify({"ok": True, "table": table_name, "message": msg})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        elif image_type == "answer" and option_num:
            filename = f"{item_id}-answer{option_num}.png"
            image_url = f"{scheme}://{domain}/generated-images/{filename}"
            try:
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
        valid_ids = [iid for iid in item_ids if iid in questions]
        if not valid_ids:
            return jsonify({"error": "No valid item IDs"}), 400
        img_bulk_queue.put((valid_ids, prompts))
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

    # --- Image bulk worker ---

    def image_bulk_worker():
        while True:
            queue_item = img_bulk_queue.get()
            if queue_item is None:
                break

            # Unpack — supports (item_ids, prompts) tuple or just item_ids list
            if isinstance(queue_item, tuple):
                item_ids, prompts = queue_item
            else:
                item_ids, prompts = queue_item, {}

            with img_bulk_lock:
                img_bulk_status["running"] = True
                img_bulk_status["total"] = len(item_ids)
                img_bulk_status["completed"] = 0
                img_bulk_status["errors"] = []

            for item_id in item_ids:
                with img_bulk_lock:
                    img_bulk_status["current_item"] = item_id

                q = questions.get(item_id)
                if not q:
                    with img_bulk_lock:
                        img_bulk_status["errors"].append({"item_id": item_id, "error": "Not found"})
                        img_bulk_status["completed"] += 1
                    continue

                # Use prompt from list page if provided, otherwise from state
                prompt_override = prompts.get(item_id)
                if not prompt_override:
                    img_st = get_image_item_state(image_state, item_id)
                    prompt_override = img_st["question_image"].get("prompt") or None

                if not prompt_override:
                    with img_bulk_lock:
                        img_bulk_status["errors"].append({"item_id": item_id, "error": "No prompt — type a prompt first"})
                        img_bulk_status["completed"] += 1
                    continue

                try:
                    prompt, _ = generate_question_image(q, prompt_override)
                    img_st = get_image_item_state(image_state, item_id)
                    img_st["question_image"]["prompt"] = prompt
                    img_st["question_image"]["generated_at"] = img_now_iso()
                    update_image_item_state(image_state, item_id, **img_st)
                    time.sleep(1)  # OpenAI rate limit
                except Exception as e:
                    print(f"  Image generation error for {item_id}: {e}")
                    with img_bulk_lock:
                        img_bulk_status["errors"].append({"item_id": item_id, "error": str(e)})

                with img_bulk_lock:
                    img_bulk_status["completed"] += 1

            with img_bulk_lock:
                img_bulk_status["running"] = False
                img_bulk_status["current_item"] = None

            img_bulk_queue.task_done()

    img_worker = threading.Thread(target=image_bulk_worker, daemon=True)
    img_worker.start()

    # --- Voiceover Bulk worker ---

    def bulk_worker():
        while True:
            item_ids = bulk_queue.get()
            if item_ids is None:
                break

            with bulk_lock:
                bulk_status["running"] = True
                bulk_status["total"] = len(item_ids)
                bulk_status["completed"] = 0
                bulk_status["errors"] = []

            for item_id in item_ids:
                with bulk_lock:
                    bulk_status["current_item"] = item_id

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
                    time.sleep(0.5)  # ElevenLabs rate limit
                except Exception as e:
                    with bulk_lock:
                        bulk_status["errors"].append({"item_id": item_id, "error": str(e)})

                with bulk_lock:
                    bulk_status["completed"] += 1

            with bulk_lock:
                bulk_status["running"] = False
                bulk_status["current_item"] = None

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

    for q in questions_list:
        subj = q["subject"] or "Unknown"
        if subj not in by_subject:
            by_subject[subj] = {"total": 0, "approved": 0, "flagged": 0,
                                "has_audio": 0, "pending": 0}
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

    return {
        "by_subject": by_subject,
        "total": len(questions_list),
        "total_approved": total_approved,
        "total_audio": total_audio,
        "total_flagged": total_flagged,
    }


def _get_flagged(questions, state):
    """Get all flagged questions with their notes."""
    flagged = []
    for item_id, s in state.items():
        if s.get("status") == "flagged" and item_id in questions:
            q = questions[item_id]
            flagged.append({
                "item_id": item_id,
                "question_text": q["question_text"][:80],
                "subject": q["subject"],
                "note": s.get("flag_note", ""),
            })
    return flagged


def _questions_for_client(questions_list, state):
    """Build compact question list for client-side filtering."""
    result = []
    for q in questions_list:
        item_id = q["item_id"]
        s = state.get(item_id, {})
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
        })
    return result


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
        result.append({
            "idx": idx,  # preserve spreadsheet order
            "id": item_id,
            "text": q["question_text"][:80],
            "desc": q.get("image_description", "")[:80],
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
