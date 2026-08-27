# Multi-Tenant QA System with Vite Frontend, PostgreSQL & Vector RAG

This document summarizes the full implementation of the **Multi-Tenant Automated QA Service** featuring:
- **PostgreSQL Database** (`qa_database` on `localhost:5432` with username `postgres` / password `root`).
- **Lossless PDF-to-Markdown Converter** (`PyMuPDF`).
- **LLM Structured Separation Engine** (`gemma3:4b`).
- **Multi-Tenant Vector DB RAG** (`all-MiniLM-L6-v2`).
- **Real-Time Dynamic QA Evaluation & Auto-Fail Circuit Breaker**.
- **Modern Vite + React + TailwindCSS Frontend**.

---

## 📁 1. Project Directory Structure

```text
gemma-qa-analysis/
├── docs/                                  # 📄 Documentation, HTML Portal & Assets
│   ├── QA_Scoring_Documentation.docx
│   ├── api_samples.md
│   ├── qa_execution_flow.png              # 🖼️ Execution Flow Diagram
│   └── qa_system_architecture.html        # 🌐 Interactive Architecture Dashboard
│
├── frontend/                              # ⚡ Vite + React + TailwindCSS Frontend
│   ├── src/
│   │   ├── App.jsx                        # Complete Multi-Tenant UI Dashboard
│   │   └── index.css                      # Tailwind styling directives
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── vite.config.js
│
├── src/                                   # 💻 Backend Source Code
│   ├── api/                               # 🌐 FastAPI App & Endpoints
│   │   ├── job_queue.py
│   │   └── web_app.py
│   │
│   ├── db/                                # 🐘 PostgreSQL Database Layer
│   │   ├── database.py                    # Auto database creation & session manager
│   │   └── models.py                      # Tenant, Document, Criteria, Evaluation models
│   │
│   ├── rag/                               # 🔍 PDF Ingestion, Separation & Vector RAG
│   │   ├── pdf_parser.py                  # Lossless PDF to Markdown converter
│   │   ├── llm_separator.py               # Gemma 3 4B Criteria & Policy separator
│   │   ├── vector_store.py                # Multi-tenant MiniLM Vector DB store
│   │   ├── knowledge_base.py
│   │   ├── rag.py
│   │   ├── rag_accuracy.py
│   │   └── rag_compliance.py
│   │
│   ├── services/                          # 🧠 QA Analysis Services
│   │   ├── dynamic_evaluator.py           # Multi-tenant RAG + Gemma evaluation engine
│   │   ├── qa_agent.py
│   │   ├── qa_intensity.py
│   │   ├── qa_report.py
│   │   ├── qa_suggestions.py
│   │   ├── qa_summary.py
│   │   └── response_time.py
│   │
│   └── core/                              # ⚙️ Core Utilities
│       ├── gemma_client.py                # Ollama Gemma 3 4B client
│       ├── report_pdf.py
│       └── weights_config.py
│
├── tests/                                 # 🧪 Tests & Sample Calls
│   ├── test_integration.py                # PostgreSQL, Vector RAG & Evaluator integration test
│   ├── sample_call.py
│   ├── compare_models.py
│   └── weights_review.py
│
├── main.py                                # 🚀 Backend Entry Point Launcher
├── request.http                           # 📡 Full REST API Collection
├── README.md
└── requirements.txt
```

---

## 🚀 2. Complete Step-by-Step Guide to Run

### Step 1: Ensure PostgreSQL is Running
Ensure PostgreSQL 17 is running on `localhost:5432` with username `postgres` and password `root`.

### Step 2: Ensure Ollama is Running
In a terminal, run:
```powershell
ollama serve
```
Make sure `gemma3:4b` is installed:
```powershell
ollama pull gemma3:4b
```

### Step 3: Start the Backend FastAPI Server
In the project root directory, run:
```powershell
python main.py
```
*(Backend runs on `http://localhost:8000`)*

### Step 4: Start the Vite + React Frontend
In a new terminal window, run:
```powershell
cd frontend
npm run dev
```
*(Frontend runs on `http://localhost:5173`)*

---

## 🌐 3. Testing the Application via Frontend UI

1. Open **`http://localhost:5173`** in your browser.
2. **PDF Ingestion & Markdown Viewer Tab**:
   - Upload any company QA Form Guideline PDF.
   - The system losslessly converts the document into Markdown (`.md`) and displays the full text in the Markdown viewer.
3. **Criteria & Policies Inspector Tab**:
   - Inspect the extracted **Category Weights** (e.g. 25% Soft Skills, 50% Technical, 25% Process), **Line Items**, **Verbatim Spiels**, and **Auto-Fail Rules**.
   - Browse the **Vector DB Policy Chunks** indexed for RAG.
4. **Live QA Testing Tab**:
   - Select your channel (`Call`, `Email`, `Chat`).
   - Click **✓ Compliant Call** or **⚠ Auto-Fail Call** to load sample transcripts.
   - Click **Run Dynamic QA Analysis** to evaluate the interaction.
   - View the overall score, scorecard table (PASS/PARTIAL/FAIL), RoBERTa sentiment intensity, retrieved RAG policies, and coaching suggestions.
5. **History Tab**:
   - View past evaluation audits stored in PostgreSQL.
