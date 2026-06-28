# 🎓 AI Study Buddy

An agentic AI app that **plans, researches, quizzes, and tracks** your learning on any topic — powered by the Mistral API (cloud, no local GPU needed).

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗺️ **Planner Agent** | Generates a structured multi-day study plan as JSON |
| 📚 **Researcher Agent** | Fetches web content via Tavily and writes study notes |
| ❓ **Quiz Agent** | Auto-generates 5 MCQs from your notes |
| 📊 **Evaluator Agent** | Scores answers; re-routes to Researcher if score < 60% |
| 💬 **Chat Agent** | Q&A with short-term history + long-term semantic memory |
| 📁 **File Upload** | Upload PDF / DOCX / TXT / Images — content is extracted and used by all agents |
| 🧠 **ChromaDB Memory** | Persistent vector store of all study notes |
| 🔄 **Feedback Loop** | Automatic re-study loop (up to 2 retries) when quiz score is low |
| 🖥️ **Streamlit UI** | Full browser interface with progress tracking |

---

## 🏗️ Architecture

```
app.py (Streamlit UI)
    │
    ├── graph.py (LangGraph StateGraph)
    │       ├── node: planner    → agents/planner_agent.py
    │       ├── node: researcher → agents/researcher_agent.py
    │       ├── node: quiz       → agents/quiz_agent.py
    │       ├── node: evaluator  → agents/evaluator_agent.py
    │       └── node: advance    (next subtopic)
    │
    ├── agents/
    │       ├── planner_agent.py    — JSON study plan from Mistral
    │       ├── researcher_agent.py — Web search + notes summarisation
    │       ├── quiz_agent.py       — MCQ generation + scoring
    │       ├── evaluator_agent.py  — Score check + re-study loop
    │       └── chat_agent.py       — Conversational Q&A
    │
    ├── tools/
    │       └── search_tool.py      — Tavily web search wrapper
    │
    ├── memory/
    │       └── vector_store.py     — ChromaDB persistent notes
    │
    └── utils/
            ├── llm_client.py       — Mistral REST API client
            └── file_extractor.py   — PDF / DOCX / Image text extraction
```

### LangGraph Flow

```
START → Planner → Researcher → Quiz → Evaluator
                     ↑                    │
                     │    score < 60%     │
                     └────────────────────┘
                        (max 2 retries)
                                          │
                            score ≥ 60%   │
                                          ↓
                                      Advance → next subtopic → END
```

---

## 🚀 Setup

### 1. Clone / unzip the project

```bash
unzip ai_study_buddy.zip
cd ai_study_buddy
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For image OCR support (optional):
```bash
pip install pillow pytesseract
# macOS:  brew install tesseract
# Ubuntu: sudo apt install tesseract-ocr
```

### 4. Configure API keys

```bash
cp .env.example .env
```

Edit `.env`:
```
MISTRAL_API_KEY=your_mistral_key_here      # https://console.mistral.ai
TAVILY_API_KEY=your_tavily_key_here        # https://tavily.com (free tier)
MISTRAL_MODEL=mistral-medium-latest
```

### 5. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## 🎯 How to Use

### Study Plan
1. Go to **🗺️ Study Plan** tab
2. Enter a topic (e.g. "Python decorators") and number of days
3. Click **Generate Study Plan**
4. Click **Research this** on any day to dive deeper

### Research
1. Go to **📚 Research** tab  
2. Enter a subtopic and click **Research Now**
3. Notes are saved to ChromaDB automatically
4. Click **Generate Quiz** to test yourself

### Upload Documents
1. Use the **sidebar** to upload PDF, DOCX, TXT, or images
2. All agents will automatically incorporate the content
3. Chat with your buddy about the uploaded material

### Quiz & Feedback Loop
1. Go to **❓ Quiz** tab
2. Select a researched topic and generate a quiz
3. Answer all 5 MCQs and submit
4. If score < 60%: notes are updated and you get another chance (max 2 retries)
5. If score ≥ 60%: 🎉 balloons!

### Chat
1. Go to **💬 Chat** tab
2. Ask anything — the buddy uses your uploaded docs + stored notes

---

## 📁 Project Structure

```
ai_study_buddy/
├── app.py                  # Streamlit UI entry point
├── graph.py                # LangGraph state machine
├── config.py               # Central configuration
├── requirements.txt
├── .env.example
├── README.md
├── agents/
│   ├── __init__.py
│   ├── planner_agent.py
│   ├── researcher_agent.py
│   ├── quiz_agent.py
│   ├── evaluator_agent.py
│   └── chat_agent.py
├── tools/
│   ├── __init__.py
│   └── search_tool.py
├── memory/
│   ├── __init__.py
│   └── vector_store.py
├── utils/
│   ├── __init__.py
│   ├── llm_client.py
│   └── file_extractor.py
├── uploads/                # Uploaded files stored here
└── chroma_db/              # ChromaDB persistent storage (auto-created)
```

---

## 🧪 Evaluation Checklist (Day 15)

| Criterion | Implementation |
|---|---|
| Agent Separation (SRP) | `agents/` — 5 separate files, each one role |
| Tool Use | Tavily search + file I/O via `tools/` and `utils/` |
| LangGraph State Machine | `graph.py` — StateGraph with conditional edges |
| Memory | ChromaDB (`memory/`) + short-term history in session state |
| Feedback Loop | Evaluator re-routes to Researcher if score < 60% (max 2x) |
| Mistral API | `utils/llm_client.py` — REST calls, no Ollama needed |
| Code Quality | Modular structure, typed dicts, no hardcoded secrets |
| Documentation | This README + inline comments throughout |

---

## 📝 Sample Output

```
Topic: Machine Learning
Duration: 3 days

Day 1 — Introduction to ML
  Objectives: Understand supervised vs unsupervised learning...
  Key Concepts: Features, Labels, Training set, Test set...

Day 2 — Linear Regression
  ...

Day 3 — Neural Networks
  ...

[Quiz generated — 5 MCQs]
Score: 3/5 (60%) ✅ PASSED
```

---

## 🤝 Contributing / Submission

- Zip the entire folder and submit the GitHub repo link
- Include a 5-minute screen recording of the app in action
- Make sure `README.md` and `requirements.txt` are in the repo root
