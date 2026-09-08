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
    get_item_state, get_hint_state, VOICEOVER_DIR,
)
from .image_state import (
    has_question_image, has_answer_image, get_image_item_state, IMAGE_DATA_DIR,
)


class Presence:
    """Fast in-memory presence check built from ONE directory listing per dir.

    Building the Final Stage list called ~13 os.path.exists() per question × 7,900 ≈
    100k syscalls. Instead list each dir once into a set and do membership tests.
    Pass an instance into assemble()/summary_row(); if None, they fall back to the
    per-file helpers (still correct, just slower).
    """
    def __init__(self):
        self.audio = self._listing(VOICEOVER_DIR, ".mp3")
        self.images = self._listing(IMAGE_DATA_DIR, ".png")

    @staticmethod
    def _listing(directory, ext):
        import os
        try:
            return {f for f in os.listdir(directory) if f.endswith(ext)}
        except OSError:
            return set()

    def q_audio(self, iid):
        return f"{iid}-question.mp3" in self.audio

    def hint_audio(self, iid, n):
        return f"{iid}-hint{n}.mp3" in self.audio

    def option_audio(self, iid, n):
        return f"{iid}-option{n}.mp3" in self.audio

    def q_image(self, iid):
        return f"{iid}-question.png" in self.images

    def answer_image(self, iid, n):
        return f"{iid}-answer{n}.png" in self.images


def build_presence():
    """Build a fresh Presence snapshot (call once per list render)."""
    return Presence()


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


def _correct_option_nums(answer):
    """Parse an Answer cell into the set of correct option numbers.

    Handles "1", "1 and 3", "1,2,3,4", "2 and 3" etc. Returns a set of ints.
    Whole-number match only (regex \\d+) so "10" != option 1 and "1" != option 10.
    True/False answers ("True"/"False") yield an empty set (no option numbers).
    """
    import re
    if not answer:
        return set()
    return {int(m) for m in re.findall(r"\d+", str(answer))}


def assemble(q, image_state, review_state, airtable_images, presence=None):
    """Build the full assembled view of one question + its completeness gates.

    Returns a dict the template renders directly. Pass a Presence snapshot to avoid
    per-file filesystem checks (used by the list); falls back to per-file helpers if None.
    """
    item_id = q["item_id"]
    qtype = q.get("question_type", "")
    template_id = q.get("template_id")
    is_true_false = (qtype == "True/False")
    is_select_all = (qtype == "Select All")
    is_written = (qtype == "Written")

    # presence checks (in-memory snapshot or per-file fallback)
    _q_image = presence.q_image if presence else has_question_image
    _answer_image = presence.answer_image if presence else has_answer_image
    _q_audio = presence.q_audio if presence else has_audio
    _hint_audio = presence.hint_audio if presence else has_hint_audio
    _option_audio = presence.option_audio if presence else has_option_audio

    options = _options(q)
    hint_levels = _hint_levels(q)

    # --- media/state lookups (app-side) ---
    at = airtable_images.get(item_id) or {}
    at_q_image = at.get("question_image") or {}
    has_local_q_image = _q_image(item_id)
    has_q_image = has_local_q_image or bool(at_q_image)
    # URL for display: prefer the local generated PNG, else the Airtable URL if present.
    if has_local_q_image:
        q_image_url = f"/generated-images/{item_id}-question.png"
    else:
        q_image_url = at_q_image.get("url", "")
    at_answer_images = at.get("answer_images") or {}

    correct_nums = _correct_option_nums(q.get("answer", ""))

    # per-option image presence (generated locally OR in Airtable)
    option_rows = []
    for num, text in options:
        has_local_opt = _answer_image(item_id, num)
        at_opt = at_answer_images.get(str(num)) or {}
        opt_img = has_local_opt or bool(at_opt)
        if has_local_opt:
            opt_img_url = f"/generated-images/{item_id}-answer{num}.png"
        else:
            opt_img_url = at_opt.get("url", "") if isinstance(at_opt, dict) else ""
        option_rows.append({
            "num": num,
            "text": text,
            "has_image": opt_img,
            "image_url": opt_img_url,
            "is_correct": num in correct_nums,
            "has_vo": _option_audio(item_id, num),
        })

    q_vo = _q_audio(item_id)
    hint_rows = []
    for n in hint_levels:
        hint_rows.append({
            "num": n,
            "text": q.get(f"hint{n}", ""),
            "has_vo": _hint_audio(item_id, n),
        })

    # --- the gates ---
    # Written questions are free-text: no options list, and an Answer cell is optional
    # (acceptable answers are configured elsewhere), so don't block on it.
    answer_set = is_true_false or is_written or bool(q.get("answer", ""))
    enough_options = is_true_false or is_written or len(options) >= 2
    option_num_set = {n for n, _ in options}
    # Answer must reference real option numbers (catches typos like "5" on a 4-option Q).
    answer_in_range = (is_true_false or is_written
                       or (bool(correct_nums) and correct_nums <= option_num_set))
    gates = []

    gates.append(_gate("Question text", bool(q.get("question_text"))))
    gates.append(_gate("Question type", bool(template_id), detail=qtype or "unknown — check the sheet"))
    gates.append(_gate("Correct answer", answer_set,
                       detail=q.get("answer", "") or ("True/False" if is_true_false
                                                      else "free text" if is_written else "missing")))
    if not is_true_false and not is_written:
        gates.append(_gate("Answer matches an option", answer_in_range,
                           detail="ok" if answer_in_range else f"answer '{q.get('answer','')}' not in options 1-{len(options)}"))
    gates.append(_gate("At least 2 options", enough_options,
                       detail=("not needed" if (is_true_false or is_written) else f"{len(options)} options")))
    gates.append(_gate("Question image", has_q_image))
    if is_select_all:
        all_opt_imgs = all(r["has_image"] for r in option_rows) and bool(option_rows)
        gates.append(_gate("Image on every option", all_opt_imgs))
    gates.append(_gate("Question voice-over", q_vo))
    # Per-option voice-over: required for each option THAT HAS TEXT to read aloud.
    # Image-only options (Select All grid) have nothing to read, so they're exempt.
    if not is_true_false and not is_written and option_rows:
        need_vo = [r for r in option_rows if (r["text"] or "").strip()]
        if need_vo:
            voiced_n = sum(1 for r in need_vo if r["has_vo"])
            all_opts_voiced = voiced_n == len(need_vo)
            gates.append(_gate(f"Each option voiced", all_opts_voiced,
                               detail=f"{voiced_n}/{len(need_vo)} voiced"))
    if hint_levels:
        all_hints_voiced = all(r["has_vo"] for r in hint_rows)
        voiced_h = sum(1 for r in hint_rows if r["has_vo"])
        gates.append(_gate(f"Each hint voiced", all_hints_voiced,
                           detail=f"{voiced_h}/{len(hint_levels)} voiced"))
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
        "q_image_url": q_image_url,
        "q_vo": q_vo,
        "options": option_rows,
        "hints": hint_rows,
        "gates": gates,
        "complete": complete,
    }


def summary_row(q, image_state, review_state, airtable_images, presence=None):
    """Lightweight per-question row for the Final Stage list (counts only)."""
    a = assemble(q, image_state, review_state, airtable_images, presence=presence)
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
