# 🧠 AdaptIQ — Adaptive Exam-Prep AI Tutor

> **NextGen AI Hackathon (Problem #2):** An Agentic AI Tutor powered by a persistent **Living Learner Model**, misconception memory, adaptive difficulty scaling, and closed-loop mastery verification.

## 🚀 The Problem
Generic AI chatbots suffer from **amnesia** during exam preparation. When a student gets a Physics or Math question wrong, the bot prints a solution—and forgets *why* the student failed five minutes later.

## 💡 The Solution: AdaptIQ
AdaptIQ is an autonomous, tool-calling AI tutor built with **Python, Streamlit, and the Google Gemini API** (`google-genai`). It maintains a persistent `learner_model.json` profile per student and runs a **Closed-Loop Adaptive Engine**:

1. **Inspects Memory:** Reads topic mastery scores, active misconceptions, and difficulty levels before asking any question.
2. **Targets Weaknesses:** Generates exam-style questions matched to the student's target exam (**JEE / Engineering STEM**, **Class 10–12 Boards**, or **GATE**) and specifically tests logged misconceptions.
3. **Diagnoses Root Cause:** Classifies mistakes into *Conceptual Gap*, *Formula Mix-up*, or *Calculation Slip*.
4. **Adapts in Real Time:** Dynamically updates mastery scores, scales difficulty (`Easy` / `Medium` / `Hard`), and schedules spaced-repetition review alerts.
5. **Closed-Loop Mastery:** When the student later answers a targeted question correctly, the agent autonomously marks the misconception as **Fixed ✅**.

## 🛠️ 5 Autonomous Agent Tools (`tools.py`)
| Tool | Purpose |
| :--- | :--- |
| `get_learner_model()` | Loads mastery scores, difficulty levels, active/resolved gaps, and review queue |
| `log_practice_attempt()` | Updates mastery, diagnoses error type, scales difficulty, and records activity history |
| `resolve_misconception()` | Marks a previously logged misconception as **Fixed ✅** upon demonstrated mastery |
| `schedule_revision_alert()` | Adds weak or repeatedly missed topics to the spaced-repetition review queue |
| `generate_study_plan()` | Mathematically allocates study minutes weighted by missing mastery `(100 - mastery)` |

## ✨ Key Features
- **Live Learner Model Dashboard:** Real-time Exam Readiness KPI, Active vs. Fixed Gaps counter, topic progress bars, bar chart analytics, and raw JSON memory inspector.
- **Multi-Model Failover:** Automatically switches across fast Gemini models (`gemini-3.5-flash-lite` primary) if a server experiences transient load.
- **Exam Presets & Custom Topics:** Switch between JEE, Boards, and GATE profiles or add any custom syllabus topic on the fly.
- **Live Agent Tool Log:** Transparent real-time view of every autonomous tool call executed by the agent.

## 💻 Run Locally
```bash
git clone <your-repo-url>
cd adaptiq-tutor
pip install -r requirements.txt
streamlit run app.py