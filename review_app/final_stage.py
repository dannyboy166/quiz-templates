"""Final Stage — assemble a whole question and compute its completeness gates.

App-side view only: uses the live spreadsheet (Google Sheets) + Airtable image cache +
local audio/image approval state. Does NOT touch Victor's DB (the deployed app has no
azure/pyodbc). Mirrors the completeness rules from docs/FINAL-REVIEW-TAB-PROPOSAL §3 and
verify_complete, but scoped to what the app can see, so it's a pre-upload QC checklist.

The 7 gates (per proposal §3):
  1. Question text + type set + correct answer set + options present (>=2, except True/False)
  2. Question image present
  3. Select All: an image on every option
  4. Question voice-over present
  5. Every hint level has its own voice-over
  6. (hints audio-only — an ingest-time concern; surfaced as info, not blocked here)
  7. Template type set and known
"""

from .state import (
    has_audio, has_hint_audio, has_option_audio,
    get_item_state, get_hint_state,
)
from .image_state import has_question_image, has_answer_image, get_image_item_state


def _options(q):
    """Non-empty option texts for a question, as a list of (num, text)."""
    out = []
    for i in range(1, 5):
        t = q.get(f"option{i}", "")
        if t:
            out.append((i, t))
    return out


def _hint_levels(q):
    """Which hint levels (1..3) have hint text in the sheet."""
    return [n for n in (1, 2, 3) if q.get(f"hint{n}", "")]


def assemble(q, image_state, review_state, airtable_images):
    """Build the full assembled view of one question + its completeness gates.

    Returns a dict the template renders directly.
    """
    item_id = q["item_id"]
    qtype = q.get("question_type", "")
    template_id = q.get("template_id")
    is_true_false = (qtype == "True/False")
    is_select_all = (qtype == "Select All")
    is_written = (qtype == "Written")

    options = _options(q)
    hint_levels = _hint_levels(q)

    # --- media/state lookups (app-side) ---
    at = airtable_images.get(item_id) or {}
    has_q_image = has_question_image(item_id) or bool(at.get("question_image"))
    at_answer_images = at.get("answer_images") or {}

    # per-option image presence (generated locally OR in Airtable)
    option_rows = []
    for num, text in options:
        opt_img = has_answer_image(item_id, num) or bool(at_answer_images.get(str(num)))
        option_rows.append({
            "num": num,
            "text": text,
            "has_image": opt_img,
            # per-option VO (Phase 3) — file naming {item_id}-option{n}.mp3
            "has_vo": has_option_audio(item_id, num),
        })

    q_vo = has_audio(item_id)
    hint_rows = []
    for n in hint_levels:
        hint_rows.append({
            "num": n,
            "text": q.get(f"hint{n}", ""),
            "has_vo": has_hint_audio(item_id, n),
        })

    # --- the gates ---
    answer_set = bool(q.get("answer", "")) or is_true_false
    enough_options = is_true_false or is_written or len(options) >= 2
    gates = []

    gates.append(_gate("Question text", bool(q.get("question_text"))))
    gates.append(_gate("Template type set", bool(template_id), detail=qtype or "unknown"))
    gates.append(_gate("Correct answer set", answer_set, detail=q.get("answer", "") or ("True/False" if is_true_false else "")))
    gates.append(_gate("Options present (≥2)", enough_options,
                       detail=("n/a" if (is_true_false or is_written) else f"{len(options)} options")))
    gates.append(_gate("Question image", has_q_image))
    if is_select_all:
        all_opt_imgs = all(r["has_image"] for r in option_rows) and bool(option_rows)
        gates.append(_gate("Every option has an image (Select All)", all_opt_imgs))
    gates.append(_gate("Question voice-over", q_vo))
    if hint_levels:
        all_hints_voiced = all(r["has_vo"] for r in hint_rows)
        gates.append(_gate(f"All {len(hint_levels)} hint(s) voiced", all_hints_voiced))
    else:
        gates.append(_gate("Hints voiced", True, detail="no hints"))

    complete = all(g["ok"] for g in gates)

    return {
        "item_id": item_id,
        "question_text": q.get("question_text", ""),
        "subject": q.get("subject", ""),
        "category": q.get("category", ""),
        "topic": q.get("topic", ""),
        "grade": q.get("grade", ""),
        "level": q.get("level", ""),
        "question_type": qtype,
        "template_id": template_id,
        "answer": q.get("answer", ""),
        "media_type": q.get("media_type", ""),
        "image_required": q.get("image_required", ""),
        "image_description": q.get("image_description", ""),
        "get_help": q.get("get_help", ""),
        "notes": q.get("notes", ""),
        "is_true_false": is_true_false,
        "is_select_all": is_select_all,
        "is_written": is_written,
        "has_q_image": has_q_image,
        "q_vo": q_vo,
        "options": option_rows,
        "hints": hint_rows,
        "gates": gates,
        "complete": complete,
    }


def summary_row(q, image_state, review_state, airtable_images):
    """Lightweight per-question row for the Final Stage list (counts only)."""
    a = assemble(q, image_state, review_state, airtable_images)
    passed = sum(1 for g in a["gates"] if g["ok"])
    total = len(a["gates"])
    return {
        "id": a["item_id"],
        "text": a["question_text"][:80],
        "subject": a["subject"],
        "topic": a["topic"],
        "type": a["question_type"],
        "passed": passed,
        "total": total,
        "complete": a["complete"],
    }


def _gate(label, ok, detail=""):
    return {"label": label, "ok": bool(ok), "detail": detail}
