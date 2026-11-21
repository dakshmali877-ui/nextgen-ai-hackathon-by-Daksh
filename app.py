import os
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

from memory import (
    EXAM_PRESETS,
    add_custom_topic,
    load_learner_model,
    reset_learner_model,
)
from tools import (
    clear_tool_logs,
    generate_study_plan,
    get_learner_model,
    get_tool_logs,
    log_practice_attempt,
    resolve_misconception,
    schedule_revision_alert,
)

# Backup models: agar ek server busy ho toh automatically next fast model chalega
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]

st.set_page_config(
    page_title="AdaptIQ — Adaptive Exam-Prep Tutor",
    page_icon="🧠",
    layout="wide",
)

SYSTEM_PROMPT = """
You are AdaptIQ, an expert Adaptive Exam-Prep AI Tutor with a persistent Learner Model.

CRITICAL AGENTIC RULES (FOLLOW STRICTLY):
1. ALWAYS call `get_learner_model()` before recommending topics, generating a quiz question, or analyzing the student's performance.
2. When quizzing, ask ONE clear, exam-style question at a time matched to the student's `target_exam` and the topic's current difficulty (`Easy`, `Medium`, or `Hard`). If the topic has active `misconceptions`, design the question specifically to test and fix that exact misconception.
3. Wait for the student to answer before revealing the solution.
4. Immediately after the student submits an answer to a question:
   - Evaluate whether they are correct or incorrect.
   - ALWAYS call `log_practice_attempt(topic, is_correct, error_type, misconception_note)`.
   - Choose `error_type` accurately: 'None' (if correct), 'Conceptual Gap', 'Formula Mix-up', or 'Calculation Slip'.
   - If incorrect, write a crisp 5-10 word `misconception_note` describing the exact mistake.
   - If incorrect OR mastery drops below 50%, ALSO call `schedule_revision_alert(topic, reason, priority)`.
   - CLOSED-LOOP LEARNING: If the student answers CORRECTLY on a question that tested one of their active `misconceptions` for that topic, ALSO call `resolve_misconception(topic, misconception_text)` to mark that gap as FIXED!
5. When the student asks for a study schedule or plan, ALWAYS call `generate_study_plan(hours_available)` and present the exact minutes returned by the tool.
6. In your reply after grading an answer, clearly state:
   - Verdict (Correct / Incorrect) + exact diagnosis (error type).
   - A concise, crystal-clear explanation of the concept.
   - Updated mastery score & next difficulty level (using exact numbers from the tool).
   - If a misconception was fixed, celebrate it clearly!
   - Offer the next adapted question immediately.
"""


def get_default_api_key() -> str:
    """Checks Streamlit Cloud secrets, then environment variable."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "👋 Welcome to **AdaptIQ**! I maintain a living **Learner Model** that tracks your mastery, "
                    "diagnoses *why* you miss questions (*Conceptual Gap*, *Formula Mix-up*, or *Calculation Slip*), "
                    "adapts difficulty in real time, and marks misconceptions **Fixed ✅** once you master them.\n\n"
                    "Click a **Quick Action** button above or type anything below to begin!"
                ),
            }
        ]
    if "genai_client" not in st.session_state:
        st.session_state.genai_client = None
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = None
    if "active_api_key" not in st.session_state:
        st.session_state.active_api_key = ""
    if "active_model" not in st.session_state:
        st.session_state.active_model = FALLBACK_MODELS[0]
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


def build_chat_history(messages):
    """Converts past Streamlit messages into Gemini chat history for smooth model switching."""
    history = []
    started = False
    for m in messages[:-1]:
        role = "user" if m["role"] == "user" else "model"
        if not started and role != "user":
            continue
        started = True
        history.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=m["content"])],
            )
        )
    return history


def create_chat_for_model(api_key: str, model_name: str, history=None):
    if st.session_state.genai_client is None or st.session_state.active_api_key != api_key:
        st.session_state.genai_client = genai.Client(api_key=api_key)
        st.session_state.active_api_key = api_key

    return st.session_state.genai_client.chats.create(
        model=model_name,
        history=history or [],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                get_learner_model,
                log_practice_attempt,
                resolve_misconception,
                schedule_revision_alert,
                generate_study_plan,
            ],
            temperature=0.4,
        ),
    )


def send_message_with_fallback(api_key: str, user_prompt: str):
    """Sends message and automatically switches to a backup model if one server is busy."""
    models_to_try = [st.session_state.active_model] + [
        m for m in FALLBACK_MODELS if m != st.session_state.active_model
    ]
    last_error = None

    for idx, model_name in enumerate(models_to_try):
        try:
            if (
                idx == 0
                and st.session_state.chat_session is not None
                and st.session_state.active_api_key == api_key
            ):
                chat = st.session_state.chat_session
            else:
                history = build_chat_history(st.session_state.messages)
                chat = create_chat_for_model(api_key, model_name, history=history)

            response = chat.send_message(user_prompt)
            st.session_state.chat_session = chat
            st.session_state.active_model = model_name
            return response.text or "✅ Learner model updated!"

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "closed" in err_str:
                st.session_state.genai_client = None
            if any(
                k in err_str
                for k in ["503", "unavailable", "429", "resource_exhausted", "500", "closed", "404"]
            ):
                st.session_state.chat_session = None
                continue
            raise e

    raise last_error


def difficulty_badge(level: str) -> str:
    if level == "Hard":
        return "🟢 Hard"
    if level == "Medium":
        return "🟡 Medium"
    return "🔴 Easy"


init_session_state()
current_model = load_learner_model()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("⚙️ AdaptIQ Controls")

    api_key = st.text_input(
        "Google Gemini API Key",
        value=get_default_api_key(),
        type="password",
        placeholder="Paste your API key here...",
    )
    st.caption(f"⚡ Active Brain: `{st.session_state.active_model}`")

    st.divider()
    st.subheader("🎓 Exam Profile")
    preset_list = list(EXAM_PRESETS.keys())
    current_exam = current_model.get("target_exam", preset_list[0])
    default_idx = preset_list.index(current_exam) if current_exam in preset_list else 0

    selected_exam = st.selectbox("Select Target Exam", preset_list, index=default_idx)
    if st.button("🔄 Load / Reset Exam Profile", use_container_width=True):
        reset_learner_model(selected_exam)
        clear_tool_logs()
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    f"🔄 Loaded **{selected_exam}** learner profile! "
                    "Click **🎯 Quiz Weakest** to watch live adaptation."
                ),
            }
        ]
        st.session_state.chat_session = None
        st.rerun()

    st.divider()
    st.subheader("➕ Add Custom Topic")
    with st.form("add_topic_form", clear_on_submit=True):
        new_topic = st.text_input("Topic Name", placeholder="e.g., Thermodynamics")
        start_mastery = st.slider("Starting Confidence (%)", 10, 90, 45)
        submitted = st.form_submit_button("Add to Learner Model", use_container_width=True)
        if submitted and new_topic.strip():
            add_custom_topic(new_topic, start_mastery)
            st.success(f"Added **{new_topic.strip()}**!")
            st.rerun()

    st.divider()
    st.subheader("🧠 Agentic Architecture")
    st.markdown(
        "- **Persistent Memory:** `learner_model.json`\n"
        "- **5 Autonomous Tools:**\n"
        "  1. `get_learner_model`\n"
        "  2. `log_practice_attempt`\n"
        "  3. `resolve_misconception`\n"
        "  4. `schedule_revision_alert`\n"
        "  5. `generate_study_plan`\n"
        "- **Closed Loop:** Diagnose → Adapt → Retest → Mark Fixed ✅"
    )

# ==================== HEADER ====================
st.title("🧠 AdaptIQ — Adaptive Exam-Prep Tutor")
st.caption(
    f"Target Exam: **{current_model.get('target_exam', 'JEE / Engineering STEM')}** · "
    "Living Learner Model · Misconception Memory · Closed-Loop Mastery"
)

# ==================== MAIN 2-COLUMN LAYOUT ====================
left_col, right_col = st.columns([1.3, 1.0], gap="large")

# -------------------- LEFT COLUMN: TUTOR CHAT --------------------
with left_col:
    st.subheader("💬 Adaptive Tutor Session")

    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("🎯 Quiz Weakest", use_container_width=True):
            st.session_state.pending_prompt = (
                "Check my learner model and give me 1 targeted question on my weakest topic."
            )
    with q2:
        if st.button("📅 2-Hr Plan", use_container_width=True):
            st.session_state.pending_prompt = (
                "Generate an adaptive 2-hour study plan for me today based on my learner model."
            )
    with q3:
        if st.button("🔍 Diagnose Me", use_container_width=True):
            st.session_state.pending_prompt = (
                "Inspect my learner model and summarize my weakest topics, active misconceptions, and study priorities."
            )

    chat_container = st.container(height=480)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    typed_prompt = st.chat_input("Type your answer or ask to practice any topic...")

    user_prompt = typed_prompt or st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    should_rerun = False

    if user_prompt:
        if not api_key:
            st.warning("⚠️ Please paste your Google Gemini API key in the left sidebar first!")
        else:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_prompt)

                with st.chat_message("assistant"):
                    with st.spinner("🧠 AdaptIQ is reading your learner model & reasoning..."):
                        try:
                            reply_text = send_message_with_fallback(api_key, user_prompt)
                            st.markdown(reply_text)
                            st.session_state.messages.append(
                                {"role": "assistant", "content": reply_text}
                            )
                            should_rerun = True
                        except Exception as e:
                            st.session_state.messages.pop()
                            st.error(f"⚠️ Temporary API issue: {e}")

# -------------------- RIGHT COLUMN: LIVE LEARNER MODEL DASHBOARD --------------------
with right_col:
    st.subheader("📊 Live Learner Model")

    model_data = load_learner_model()
    topics = model_data["topics"]

    avg_mastery = round(sum(t["mastery"] for t in topics.values()) / max(1, len(topics)))
    active_gaps = sum(len(t.get("misconceptions", [])) for t in topics.values())
    fixed_gaps = sum(len(t.get("resolved_misconceptions", [])) for t in topics.values())
    weakest_name, weakest_info = min(topics.items(), key=lambda x: x[1]["mastery"])

    # Clean, non-truncating numeric KPIs
    m1, m2, m3 = st.columns(3)
    m1.metric("Exam Readiness", f"{avg_mastery}%")
    m2.metric("Active Gaps", active_gaps)
    m3.metric("Fixed Gaps ✅", fixed_gaps)

    st.info(
        f"🎯 **Top Focus Area:** {weakest_name} "
        f"({weakest_info['mastery']}% mastery · {weakest_info['difficulty']})"
    )

    # Topic Mastery Progress Bars
    st.markdown("**📚 Topic Mastery & Adaptive Difficulty**")
    sorted_topics = sorted(topics.items(), key=lambda x: x[1]["mastery"])
    for topic_name, info in sorted_topics:
        c_name, c_meta = st.columns([1.4, 1])
        c_name.markdown(f"**{topic_name}**")
        c_meta.markdown(
            f"<div style='text-align:right;'>{difficulty_badge(info['difficulty'])} · <b>{info['mastery']}%</b></div>",
            unsafe_allow_html=True,
        )
        st.progress(info["mastery"] / 100)

    # Compact 4-tab view (fits cleanly without horizontal overflow)
    tab_gaps, tab_chart, tab_queue, tab_logs = st.tabs(
        ["⚠️ Gaps", "📈 Chart", "🔔 Queue", "🔧 Logs"]
    )

    with tab_gaps:
        has_active = False
        for topic_name, info in sorted_topics:
            for note in info.get("misconceptions", []):
                has_active = True
                st.warning(f"**{topic_name}:** {note}")
        if not has_active:
            st.success("🎉 Zero active misconceptions! Ready for harder drills.")

        has_fixed = False
        for topic_name, info in sorted_topics:
            for fixed in info.get("resolved_misconceptions", []):
                if not has_fixed:
                    st.markdown("**✅ Recently Fixed Misconceptions**")
                    has_fixed = True
                st.success(f"**{topic_name}:** {fixed}")

    with tab_chart:
        chart_df = pd.DataFrame(
            [{"Topic": name, "Mastery (%)": info["mastery"]} for name, info in sorted_topics]
        ).set_index("Topic")
        st.bar_chart(chart_df, height=210)

        history = model_data.get("recent_history", [])
        if history:
            st.markdown("**🕒 Recent Activity**")
            hist_df = pd.DataFrame(reversed(history[-6:]))
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        else:
            st.caption("Answer a question to see live mastery transitions here.")

    with tab_queue:
        queue = model_data.get("review_queue", [])
        if queue:
            for item in queue:
                badge = (
                    "🔴"
                    if item["priority"] == "High"
                    else ("🟡" if item["priority"] == "Medium" else "🟢")
                )
                st.info(f"{badge} **{item['topic']}** ({item['priority']}) — {item['reason']}")
        else:
            st.success("Your spaced-repetition review queue is clear!")

    with tab_logs:
        logs = get_tool_logs()
        if logs:
            for entry in reversed(logs[-8:]):
                st.code(
                    f"[{entry['time']}] {entry['tool']}()\n↳ {entry['summary']}",
                    language="text",
                )
        else:
            st.caption("Interact with the tutor to watch Gemini call tools live here!")

        with st.expander("📄 Inspect Raw learner_model.json"):
            st.json(model_data)

if should_rerun:
    st.rerun()