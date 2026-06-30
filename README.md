# 🎓 AI Study Buddy

An agentic AI app that **plans, researches, quizzes, and tracks** your learning on any topic — powered by the Mistral API (cloud, no local GPU needed).

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🗺️ **Planner Agent** | Generates a structured multi‑day study plan (up to 90+ days) with detailed daily breakdowns, objectives, key concepts, resources, and practice tasks. |
| 📚 **Researcher Agent** | Fetches web content via Tavily **and/or** uses uploaded documents to write structured study notes. |
| ❓ **Quiz Agent** | Auto‑generates MCQs from your notes, with flexible question count (3–10). |
| 📊 **Evaluator Agent** | Scores answers; re‑routes to Researcher if score < 60% (feedback loop, max 2 retries). |
| 💬 **Chat Agent** | Q&A with short‑term history + long‑term semantic memory (ChromaDB). |
| 📁 **File Upload** | Upload PDF, DOCX, TXT, and **images** – text extracted via Mistral’s vision model (Pixtral) or fallback OCR. |
| 🧠 **ChromaDB Memory** | Persistent vector store of all study notes, quiz results, and research notes. |
| 🔄 **Feedback Loop** | Automatic re‑study loop (up to 2 retries) when quiz score is low. |
| 📥 **Export Options** | Download any plan, research note, quiz result, or chat conversation as **JSON** or **PDF**. |
| 🖥️ **Streamlit UI** | Full browser interface with progress tracking, history management, and one‑click exports. |
| 🔍 **Source Selection** | Choose whether to use Mistral (web search), uploaded documents, or both for each agent. |
| 🖼️ **Vision‑enabled Upload** | Upload images – the app reads and describes them using Mistral Pixtral (no Tesseract needed). |
| 🧹 **Cleanup** | Delete chats, research, quizzes, and planner entries – **physical files and ChromaDB records** are removed. |

---

## 🏗️ Architecture
app.py (Streamlit UI)
│
├── graph.py (LangGraph StateGraph)
│ ├── node: planner → agents/planner_agent.py
│ ├── node: researcher → agents/researcher_agent.py
│ ├── node: quiz → agents/quiz_agent.py
│ ├── node: evaluator → agents/evaluator_agent.py
│ └── node: advance (next subtopic)
│
├── agents/
│ ├── planner_agent.py — JSON study plan from Mistral (supports 100+ days)
│ ├── researcher_agent.py — Web search + document summarisation
│ ├── quiz_agent.py — MCQ generation + scoring
│ ├── evaluator_agent.py — Score check + re‑study loop
│ └── chat_agent.py — Conversational Q&A
│
├── tools/
│ └── search_tool.py — Tavily web search wrapper
│
├── memory/
│ └── vector_store.py — ChromaDB persistent notes, quiz, and research history
│
└── utils/
├── llm_client.py — Mistral REST API (text + vision)
├── file_extractor.py — PDF, DOCX, TXT, and image extraction
└── pdf_generator.py — Convert Markdown to PDF (reportlab)

text

### LangGraph Flow
START → Planner → Researcher → Quiz → Evaluator
↑ │
│ score < 60% │
└────────────────────┘
(max 2 retries)
│
score ≥ 60% │
↓
Advance → next subtopic → END

text

---

## 🚀 Setup

### 1. Clone / unzip the project

```bash
unzip ai_study_buddy.zip
cd ai_study_buddy
2. Create a virtual environment
bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
3. Install dependencies
bash
pip install -r requirements.txt
For PDF export (optional but recommended):

bash
pip install reportlab
For image OCR fallback (optional, not required if you use Mistral vision):

bash
pip install pillow pytesseract
# macOS:  brew install tesseract
# Ubuntu: sudo apt install tesseract-ocr
4. Configure API keys
bash
cp .env.example .env
Edit .env:

text
MISTRAL_API_KEY=your_mistral_key_here      # https://console.mistral.ai
TAVILY_API_KEY=your_tavily_key_here        # https://tavily.com (free tier)
MISTRAL_MODEL=mistral-medium-latest        # or mistral-large-latest
5. Run the app
bash
streamlit run app.py
Open http://localhost:8501 in your browser.

🎯 How to Use
Study Plan (Planner)
Go to 🗺️ Study Plan tab.

Enter a topic (e.g., "Python decorators"), number of days (up to 90+), and difficulty.

Tick "Include uploaded documents" if you want the plan to leverage your uploaded files.

Click Generate Study Plan – the app will produce a detailed day‑by‑day plan.

Once generated, use the row of buttons:

Quiz on this topic – jumps to the Quiz tab with the plan as context.

JSON – download the plan as JSON.

PDF – download a beautifully formatted PDF.

Research
Go to 📚 Research tab.

Choose your sources:

Use web search (Mistral) – fetches live content via Tavily.

Use uploaded documents – uses your uploaded files.
(You can tick both or one independently.)

Enter a topic and optional focus.

Click Run Researcher – notes are generated and saved to ChromaDB.

After the notes appear, you can:

Quiz on this topic – jump to the Quiz tab with the research as context.

JSON / PDF – download the notes.

Upload Documents
Use the sidebar to upload PDF, DOCX, TXT, or images.

Images are analysed via Mistral Pixtral – no Tesseract required.

All agents will automatically incorporate the uploaded content.

Chat with your buddy about the uploaded material.

Quiz & Feedback Loop
Go to ❓ Quiz tab.

Choose whether to include uploaded documents as context.

Enter a topic and the number of questions (3–10).

Click Start Quiz – MCQs are generated.

Answer all questions and submit.

If score < 60%: the app triggers the Researcher Agent to re‑study the weak topics (max 2 retries).

If score ≥ 60%: 🎉 balloons and you can download the result as JSON or PDF.

Chat
Go to 💬 Chat tab.

Upload files via the ➕ button to add context.

Ask anything – the buddy uses your uploaded docs + stored notes.

Export any chat conversation as JSON or PDF using the buttons at the top.

History & Cleanup
Go to 📜 History tab.

Browse your past Chats, Quizzes, Research, and Plans.

For each entry, use the side‑by‑side buttons:

🗑️ DELETE – removes the item and its associated ChromaDB records (if any).

⬇️ PDF – downloads a PDF.

⬇️ JSON – downloads JSON.

Use Export All (JSON) to back up everything.

📁 Project Structure
text
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
│   ├── llm_client.py          # Mistral REST + vision
│   ├── file_extractor.py
│   └── pdf_generator.py
├── uploads/                # Uploaded files stored here
└── chroma_db/              # ChromaDB persistent storage (auto-created)
🧪 Evaluation Checklist
Criterion	Implementation
Agent Separation (SRP)	agents/ — 5 separate files, each one role.
Tool Use	Tavily search + file I/O via tools/ and utils/.
LangGraph State Machine	graph.py — StateGraph with conditional edges.
Memory	ChromaDB (memory/) + short‑term history in session state.
Feedback Loop	Evaluator re‑routes to Researcher if score < 60% (max 2x).
Mistral API	utils/llm_client.py — REST calls, no Ollama needed.
Vision Support	Images processed via Mistral Pixtral (fallback to Tesseract if installed).
Export	JSON + PDF download for plans, research, quizzes, and chats.
Data Cleanup	Deletion removes physical files and ChromaDB entries.
Code Quality	Modular structure, typed dicts, no hardcoded secrets.
Documentation	This README + inline comments throughout.
📝 Sample Output – Study Plan
text
Topic: Machine Learning
Duration: 15 days

Day 1 — Introduction and Setup
  Overview: This day covers the fundamentals...
  Learning Objectives:
    - Understand the history of ML
    - Set up Python environment
  Key Concepts:
    - Supervised vs Unsupervised learning
    - Features and labels
  Practice Tasks:
    - Install Jupyter and numpy
    - Load a dataset and explore
  Resources:
    - "Hands‑On ML" – Chapter 1
    - Scikit‑learn documentation

... (days 2–15)

[Quiz generated — 5 MCQs]
Score: 4/5 (80%) ✅ PASSED