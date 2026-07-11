# 🎓 AI Study Buddy

An agentic AI app that **plans, researches, quizzes, and tracks** your learning on any topic — powered by the Mistral API (cloud, no local GPU needed).

---

# ✨ Features

| Feature | Description |
|---------|-------------|
| 🛡️ **Security Guardrails** | Prompt injection defence, PII redaction, strict academic-only filter, tool schema enforcement, and output validation protect every interaction. |
| 🗺️ **Planner Agent** | Generates a structured multi-day study plan (up to 90+ days) with detailed daily breakdowns, objectives, key concepts, resources, and practice tasks. |
| 📚 **Researcher Agent** | Fetches web content via Tavily and/or uses uploaded documents to write structured study notes. |
| ❓ **Quiz Agent** | Auto-generates MCQs from your notes, with flexible question count (3–10). |
| 📊 **Evaluator Agent** | Scores answers; re-routes to Researcher if score < 60% (feedback loop, max 2 retries). |
| 💬 **Chat Agent** | Q&A with short-term history + long-term semantic memory (ChromaDB). |
| 📁 **File Upload** | Upload PDF, DOCX, TXT, and images – text extracted via Mistral Pixtral or fallback OCR. |
| 🧠 **ChromaDB Memory** | Persistent vector store of study notes, quiz results, and research notes. |
| 🔄 **Feedback Loop** | Automatic re-study loop (up to 2 retries) when quiz score is low. |
| 📥 **Export Options** | Download plans, research notes, quiz results, or chats as **JSON** or **PDF**. |
| 🖥️ **Streamlit UI** | Browser interface with progress tracking, history management, and exports. |
| 🔍 **Source Selection** | Choose Mistral web search, uploaded documents, or both. |
| 🖼️ **Vision-enabled Upload** | Upload images analyzed using Mistral Pixtral (no Tesseract required). |
| 🧹 **Cleanup** | Delete chats, quizzes, plans, research history, and corresponding ChromaDB entries. |

---

# 🛡️ Security Guardrails

All user inputs and outputs pass through **utils/guardrails.py**.

## 1. Prompt Injection Defence

- Detects attempts such as:
  - Ignore previous instructions
  - Act as system/admin
  - Jailbreak prompts
- Protects every agent using `guard_request()`.

## 2. PII Redaction

Automatically removes:

- Email addresses
- Phone numbers
- Credit card numbers
- SSNs
- Other sensitive personal information

Applied to:

- User prompts
- Uploaded documents
- System prompts

---

## 3. Strict Academic-only Filter

Uses regex whole-word matching (`\b`) against an expandable academic keyword list.

Examples:

✅ "Explain Python decorators"

✅ "Teach me Machine Learning"

❌ "Tell me a joke"

❌ "Who won yesterday's football match?"

---

## 4. Output Validation

Optional `guard_response()` checks for:

- API keys
- System prompts
- Internal paths
- Sensitive data leakage

---

## 5. Tool Schema Enforcement

Every Tavily and researcher tool call is validated using Pydantic schemas.

---

## 6. Persistent Error Handling

Blocked inputs:

- show a persistent red warning
- are excluded from future conversation history
- never influence future responses

---

# 🏗️ Architecture

```
app.py (Streamlit UI)
│
├── graph.py (LangGraph StateGraph)
│   ├── Planner
│   ├── Researcher
│   ├── Quiz
│   ├── Evaluator
│   └── Advance
│
├── agents/
│   ├── planner_agent.py
│   ├── researcher_agent.py
│   ├── quiz_agent.py
│   ├── evaluator_agent.py
│   └── chat_agent.py
│
├── tools/
│   └── search_tool.py
│
├── memory/
│   └── vector_store.py
│
├── utils/
│   ├── llm_client.py
│   ├── file_extractor.py
│   ├── pdf_generator.py
│   └── guardrails.py
│
├── uploads/
└── chroma_db/
```

---

# 🔄 LangGraph Workflow

```
START
   │
   ▼
Planner
   │
   ▼
Researcher
   │
   ▼
Quiz
   │
   ▼
Evaluator
   │
   ├──────────── score < 60%
   │             │
   │             ▼
   │        Researcher
   │             │
   └─────────────┘
      (max 2 retries)

score ≥ 60%
      │
      ▼
 Advance
      │
      ▼
     END
```

---

# 🚀 Installation

## 1. Clone Project

```bash
git clone <repository-url>
cd ai_study_buddy
```

or

```bash
unzip ai_study_buddy.zip
cd ai_study_buddy
```

---

## 2. Create Virtual Environment

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Optional PDF export

```bash
pip install reportlab
```

Optional OCR

```bash
pip install pillow pytesseract
```

Ubuntu

```bash
sudo apt install tesseract-ocr
```

macOS

```bash
brew install tesseract
```

---

## 4. Configure API Keys

Copy

```bash
cp .env.example .env
```

Edit

```text
MISTRAL_API_KEY=your_mistral_key_here
TAVILY_API_KEY=your_tavily_key_here
MISTRAL_MODEL=mistral-medium-latest
```

---

## 5. Run

```bash
streamlit run app.py
```

Open

```
http://localhost:8501
```

---

# 🎯 Usage

## 🗺️ Planner

- Enter study topic
- Select duration (up to 90+ days)
- Choose difficulty
- Optionally include uploaded documents
- Generate plan
- Export JSON or PDF

---

## 📚 Research

Choose sources

- Web Search
- Uploaded Documents
- Both

Generate structured study notes.

---

## 📁 Upload Files

Supported formats

- PDF
- DOCX
- TXT
- Images

Images are processed using **Mistral Pixtral**.

---

## ❓ Quiz

- Select topic
- Choose 3–10 MCQs
- Submit answers

If score < 60%

```
Researcher
     ↓
New Notes
     ↓
Quiz Again
```

(maximum 2 retries)

---

## 💬 Chat

Supports

- Uploaded documents
- ChromaDB memory
- Semantic search
- Study-only conversations

Non-academic questions are blocked automatically.

---

## 📜 History

Manage

- Plans
- Research
- Chats
- Quizzes

Available actions

- Delete
- Export JSON
- Export PDF

---

# 📂 Project Structure

```text
ai_study_buddy/
│
├── app.py
├── graph.py
├── config.py
├── requirements.txt
├── README.md
├── .env.example
│
├── agents/
│   ├── planner_agent.py
│   ├── researcher_agent.py
│   ├── quiz_agent.py
│   ├── evaluator_agent.py
│   └── chat_agent.py
│
├── tools/
│   └── search_tool.py
│
├── memory/
│   └── vector_store.py
│
├── utils/
│   ├── llm_client.py
│   ├── file_extractor.py
│   ├── pdf_generator.py
│   └── guardrails.py
│
├── uploads/
└── chroma_db/
```

---

# 🧪 Evaluation Checklist

| Criterion | Implementation |
|-----------|----------------|
| Agent Separation | Five dedicated agents |
| Tool Use | Tavily + File Processing |
| LangGraph | StateGraph workflow |
| Memory | ChromaDB + Session History |
| Feedback Loop | Automatic retry when score < 60% |
| Mistral API | REST API |
| Vision Support | Pixtral |
| Export | JSON + PDF |
| Cleanup | Removes files + ChromaDB |
| Security | Prompt Injection + PII + Output Validation |
| Code Quality | Modular architecture |
| Documentation | README + inline comments |

---

# 📝 Sample Output

## Study Plan

```
Topic: Machine Learning

Duration: 15 Days

Day 1
Introduction and Setup

Objectives
- Understand Machine Learning
- Install required tools

Concepts
- Supervised Learning
- Unsupervised Learning

Practice
- Install Python
- Load a dataset

Resources
- Hands-On Machine Learning
- Scikit-learn Documentation
```

...

```
Quiz Generated

5 Questions

Score

4 / 5

80%

✅ PASSED
```

---

# 🛠️ Technologies Used

- Python
- Streamlit
- LangGraph
- LangChain
- Mistral AI
- Mistral Pixtral
- Tavily Search
- ChromaDB
- ReportLab
- Pydantic
- Pillow
- Tesseract OCR (optional)

---

# 📜 License

This project is intended for educational purposes.

---

# 👨‍💻 Author

Developed as an **Agentic AI Study Assistant** using **LangGraph**, **Mistral AI**, **ChromaDB**, and **Streamlit**.