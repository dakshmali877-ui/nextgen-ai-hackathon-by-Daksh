import json
import os
from datetime import datetime

MEMORY_FILE = "learner_model.json"

EXAM_PRESETS = {
    "JEE / Engineering STEM": {
        "Kinematics": {
            "mastery": 72,
            "difficulty": "Medium",
            "attempts": 5,
            "correct": 4,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
        "Electrostatics": {
            "mastery": 35,
            "difficulty": "Easy",
            "attempts": 4,
            "correct": 1,
            "misconceptions": ["Confuses electric field direction for negative charges"],
            "resolved_misconceptions": [],
        },
        "Calculus": {
            "mastery": 48,
            "difficulty": "Easy",
            "attempts": 4,
            "correct": 2,
            "misconceptions": ["Forgets chain rule on nested functions"],
            "resolved_misconceptions": [],
        },
        "Probability": {
            "mastery": 62,
            "difficulty": "Medium",
            "attempts": 3,
            "correct": 2,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
        "Circuits": {
            "mastery": 80,
            "difficulty": "Hard",
            "attempts": 5,
            "correct": 4,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
    },
    "Class 10-12 Boards (Math & Science)": {
        "Trigonometry": {
            "mastery": 40,
            "difficulty": "Easy",
            "attempts": 4,
            "correct": 1,
            "misconceptions": ["Mixes up sin and cos ratios in right triangles"],
            "resolved_misconceptions": [],
        },
        "Quadratic Equations": {
            "mastery": 65,
            "difficulty": "Medium",
            "attempts": 4,
            "correct": 3,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
        "Electricity": {
            "mastery": 38,
            "difficulty": "Easy",
            "attempts": 3,
            "correct": 1,
            "misconceptions": ["Adds resistances in parallel directly instead of reciprocals"],
            "resolved_misconceptions": [],
        },
        "Optics": {
            "mastery": 55,
            "difficulty": "Medium",
            "attempts": 3,
            "correct": 2,
            "misconceptions": ["Sign convention confusion for concave mirrors"],
            "resolved_misconceptions": [],
        },
        "Chemical Reactions": {
            "mastery": 78,
            "difficulty": "Hard",
            "attempts": 5,
            "correct": 4,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
    },
    "GATE (ECE & CS)": {
        "Digital Logic": {
            "mastery": 76,
            "difficulty": "Hard",
            "attempts": 5,
            "correct": 4,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
        "Signals & Systems": {
            "mastery": 36,
            "difficulty": "Easy",
            "attempts": 4,
            "correct": 1,
            "misconceptions": ["Confuses time-shifting and time-scaling order"],
            "resolved_misconceptions": [],
        },
        "Control Systems": {
            "mastery": 52,
            "difficulty": "Medium",
            "attempts": 3,
            "correct": 2,
            "misconceptions": ["Miscounts poles in Routh-Hurwitz array"],
            "resolved_misconceptions": [],
        },
        "Network Theory": {
            "mastery": 68,
            "difficulty": "Medium",
            "attempts": 4,
            "correct": 3,
            "misconceptions": [],
            "resolved_misconceptions": [],
        },
        "Analog Circuits": {
            "mastery": 42,
            "difficulty": "Easy",
            "attempts": 4,
            "correct": 1,
            "misconceptions": ["Assumes ideal op-amp virtual short without negative feedback"],
            "resolved_misconceptions": [],
        },
    },
}


def get_default_profile(preset_name: str = "JEE / Engineering STEM"):
    """Creates a realistic starting student profile for the selected exam preset."""
    if preset_name not in EXAM_PRESETS:
        preset_name = "JEE / Engineering STEM"

    # Deep copy via json so modifying state never mutates the preset template
    topics = json.loads(json.dumps(EXAM_PRESETS[preset_name]))
    weakest = min(topics.items(), key=lambda x: x[1]["mastery"])

    return {
        "student_name": "Student",
        "target_exam": preset_name,
        "topics": topics,
        "review_queue": [
            {
                "topic": weakest[0],
                "reason": f"Low mastery ({weakest[1]['mastery']}%) - needs conceptual rebuild",
                "priority": "High",
                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        ],
        "recent_history": [],
    }


def load_learner_model():
    """Loads the learner model from JSON and ensures all required fields exist."""
    if not os.path.exists(MEMORY_FILE):
        data = get_default_profile()
        save_learner_model(data)
        return data

    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backward-compatibility safety check
    for topic_info in data.get("topics", {}).values():
        topic_info.setdefault("misconceptions", [])
        topic_info.setdefault("resolved_misconceptions", [])
    data.setdefault("review_queue", [])
    data.setdefault("recent_history", [])
    data.setdefault("target_exam", "JEE / Engineering STEM")
    return data


def save_learner_model(data):
    """Saves updated learner state back to disk."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def reset_learner_model(preset_name: str = "JEE / Engineering STEM"):
    """Resets the student profile to the chosen exam preset."""
    data = get_default_profile(preset_name)
    save_learner_model(data)
    return data


def add_custom_topic(topic_name: str, initial_mastery: int = 50):
    """Adds a brand-new topic to the student's learner model."""
    clean_name = topic_name.strip()
    if not clean_name:
        return None

    model = load_learner_model()
    for existing in model["topics"]:
        if existing.lower() == clean_name.lower():
            return model  # Already exists

    difficulty = "Easy" if initial_mastery < 50 else ("Medium" if initial_mastery <= 75 else "Hard")
    model["topics"][clean_name] = {
        "mastery": int(initial_mastery),
        "difficulty": difficulty,
        "attempts": 0,
        "correct": 0,
        "misconceptions": [],
        "resolved_misconceptions": [],
    }
    save_learner_model(model)
    return model


if __name__ == "__main__":
    m = reset_learner_model("JEE / Engineering STEM")
    print("✅ Upgraded Learner Model ready! Exam:", m["target_exam"])
    print("Available Exam Presets:", list(EXAM_PRESETS.keys()))