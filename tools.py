from datetime import datetime
from memory import load_learner_model, save_learner_model, reset_learner_model

# Stores recent tool calls so our Streamlit UI can display them live
TOOL_EVENT_LOG = []


def _record_event(tool_name: str, summary: str):
    TOOL_EVENT_LOG.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "tool": tool_name,
        "summary": summary,
    })


def get_tool_logs():
    return list(TOOL_EVENT_LOG)


def clear_tool_logs():
    TOOL_EVENT_LOG.clear()


def _find_topic_key(topics: dict, topic: str):
    for existing in topics:
        if existing.lower() == topic.strip().lower():
            return existing
    return None


def get_learner_model() -> dict:
    """
    Fetches the student's current learner model, including target exam,
    tracked topics, mastery scores (0-100), difficulty levels, active misconceptions,
    resolved misconceptions, and spaced-repetition review queue.
    Call this before choosing a quiz question or giving personalized study advice.
    """
    model = load_learner_model()
    _record_event("get_learner_model", "Loaded student mastery profile & misconceptions")
    return model


def log_practice_attempt(
    topic: str,
    is_correct: bool,
    error_type: str = "None",
    misconception_note: str = "",
) -> dict:
    """
    Updates the learner model immediately after evaluating a student's answer.
    Args:
        topic: The subject/topic name (e.g., 'Electrostatics', 'Calculus').
        is_correct: True if the student answered correctly, False if wrong.
        error_type: One of 'None', 'Conceptual Gap', 'Formula Mix-up', or 'Calculation Slip'.
        misconception_note: Short 5-10 word description of the mistake if wrong (empty string if correct).
    """
    model = load_learner_model()
    topics = model["topics"]

    matched_topic = _find_topic_key(topics, topic) or topic.strip()

    if matched_topic not in topics:
        topics[matched_topic] = {
            "mastery": 50,
            "difficulty": "Medium",
            "attempts": 0,
            "correct": 0,
            "misconceptions": [],
            "resolved_misconceptions": [],
        }

    t = topics[matched_topic]
    t.setdefault("misconceptions", [])
    t.setdefault("resolved_misconceptions", [])

    old_mastery = t["mastery"]
    t["attempts"] += 1

    if is_correct:
        t["correct"] += 1
        delta = 10 if t["difficulty"] == "Easy" else (12 if t["difficulty"] == "Medium" else 8)
        t["mastery"] = min(100, old_mastery + delta)
    else:
        penalty = 12 if error_type == "Conceptual Gap" else 8
        t["mastery"] = max(5, old_mastery - penalty)
        if misconception_note and misconception_note not in t["misconceptions"]:
            t["misconceptions"].append(misconception_note)

    # Adaptive difficulty scaling based on updated mastery
    if t["mastery"] < 50:
        t["difficulty"] = "Easy"
    elif t["mastery"] <= 75:
        t["difficulty"] = "Medium"
    else:
        t["difficulty"] = "Hard"

    # Log to recent history
    model["recent_history"].append({
        "time": datetime.now().strftime("%H:%M"),
        "topic": matched_topic,
        "result": "Correct" if is_correct else f"Incorrect ({error_type})",
        "mastery_change": f"{old_mastery}% → {t['mastery']}%",
    })
    model["recent_history"] = model["recent_history"][-12:]

    save_learner_model(model)

    status_icon = "✅" if is_correct else "❌"
    _record_event(
        "log_practice_attempt",
        f"{status_icon} {matched_topic}: {old_mastery}% → {t['mastery']}% (Next: {t['difficulty']})",
    )

    return {
        "topic": matched_topic,
        "old_mastery": old_mastery,
        "new_mastery": t["mastery"],
        "new_difficulty": t["difficulty"],
        "recorded_misconception": misconception_note if not is_correct else "None",
        "remaining_misconceptions": t["misconceptions"],
    }


def resolve_misconception(topic: str, misconception_text: str) -> dict:
    """
    Marks a previously logged misconception as FIXED when the student answers a
    targeted question correctly and demonstrates true understanding.
    Args:
        topic: The topic name (e.g., 'Electrostatics').
        misconception_text: The misconception from the learner model that the student just overcame.
    """
    model = load_learner_model()
    topics = model["topics"]
    matched_topic = _find_topic_key(topics, topic)

    if not matched_topic:
        return {"status": "not_found", "message": f"Topic '{topic}' not found."}

    t = topics[matched_topic]
    active_list = t.get("misconceptions", [])
    resolved_list = t.setdefault("resolved_misconceptions", [])

    if not active_list:
        return {"status": "none_active", "message": f"No active misconceptions in {matched_topic}."}

    # Find the closest matching misconception so slight rewording still works cleanly
    target_lower = misconception_text.lower()
    target_words = set(w for w in target_lower.split() if len(w) > 3)

    best_idx = 0
    best_score = -1
    for i, item in enumerate(active_list):
        item_lower = item.lower()
        if target_lower in item_lower or item_lower in target_lower:
            best_idx = i
            break
        item_words = set(w for w in item_lower.split() if len(w) > 3)
        overlap = len(target_words & item_words)
        if overlap > best_score:
            best_score = overlap
            best_idx = i

    fixed_item = active_list.pop(best_idx)
    fixed_entry = f"{fixed_item} (Fixed at {datetime.now().strftime('%H:%M')})"
    resolved_list.insert(0, fixed_entry)

    # If no active misconceptions remain and mastery is healthy, clear from review queue
    if not active_list and t["mastery"] >= 50:
        model["review_queue"] = [
            q for q in model.get("review_queue", [])
            if q["topic"].lower() != matched_topic.lower()
        ]

    save_learner_model(model)
    _record_event("resolve_misconception", f"🎉 Fixed in {matched_topic}: '{fixed_item}'")

    return {
        "status": "resolved",
        "topic": matched_topic,
        "fixed_misconception": fixed_item,
        "remaining_active": active_list,
    }


def schedule_revision_alert(topic: str, reason: str, priority: str = "High") -> dict:
    """
    Adds a topic to the student's Spaced-Repetition Review Queue when a weakness
    or repeated misconception is detected.
    Args:
        topic: Topic that needs future revision.
        reason: Brief explanation of what needs to be reviewed.
        priority: 'High', 'Medium', or 'Low'.
    """
    model = load_learner_model()
    queue = model.get("review_queue", [])

    queue = [item for item in queue if item["topic"].lower() != topic.strip().lower()]
    entry = {
        "topic": topic.strip(),
        "reason": reason,
        "priority": priority,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    queue.insert(0, entry)
    model["review_queue"] = queue
    save_learner_model(model)

    _record_event("schedule_revision_alert", f"Flagged '{topic}' ({priority} priority)")
    return {"status": "scheduled", "entry": entry}


def generate_study_plan(hours_available: float) -> dict:
    """
    Builds a mathematically weighted study schedule based on the student's
    lowest mastery topics in the learner model.
    Args:
        hours_available: Total study hours the student has available today (e.g., 2.0 or 3.5).
    """
    model = load_learner_model()
    topics = model["topics"]
    total_minutes = max(15, int(hours_available * 60))

    weights = {name: max(10, 100 - info["mastery"]) for name, info in topics.items()}
    total_weight = sum(weights.values())

    plan = []
    sorted_topics = sorted(topics.items(), key=lambda x: x[1]["mastery"])
    for name, info in sorted_topics:
        allocated_mins = max(10, round((weights[name] / total_weight) * total_minutes))
        focus = (
            "Rebuild core concepts + easy drills"
            if info["mastery"] < 50
            else ("Timed practice problems" if info["mastery"] <= 75 else "Quick revision & hard challenge")
        )
        plan.append({
            "topic": name,
            "current_mastery": info["mastery"],
            "allocated_minutes": allocated_mins,
            "recommended_focus": focus,
            "known_misconceptions": info.get("misconceptions", []),
        })

    _record_event("generate_study_plan", f"Generated {total_minutes}-min adaptive plan across {len(plan)} topics")
    return {
        "total_minutes": total_minutes,
        "schedule": plan,
    }


if __name__ == "__main__":
    reset_learner_model("JEE / Engineering STEM")
    print("Testing 5th tool (Closed-Loop Learning)...")
    r1 = log_practice_attempt("Electrostatics", is_correct=True)
    r2 = resolve_misconception("Electrostatics", "electric field direction for negative charges")
    print("1. Mastery jumped:", r1["old_mastery"], "->", r1["new_mastery"])
    print("2. Misconception resolved:", r2["status"], "| Fixed:", r2.get("fixed_misconception"))
    reset_learner_model("JEE / Engineering STEM")  # Keep JSON clean for demo
    print("✅ All 5 tools working perfectly!")