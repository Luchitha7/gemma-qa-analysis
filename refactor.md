# Codebase Refactoring & Multi-Tenant QA System Architecture

This document provides a comprehensive summary of the codebase refactoring, architectural design changes, directory reorganization, and step-by-step setup guides for the **Automated QA Service**.

---

## 🚀 1. What Was Newly Done

### A. Enterprise Multi-Tenant QA System Architecture
- **Per-Company Custom Criteria**: Transitioned from a single-tenant hardcoded system to a flexible multi-tenant architecture where each company configures its own evaluation criteria, category weights, SLA thresholds, verbatim spiels, and auto-fail rules.
- **Lossless PDF-to-Markdown Parser**: Integrated layout-aware PDF conversion using `PyMuPDF (fitz)` / `Marker-PDF` to extract structured Markdown tables, percentages, SLAs, and spiels without text corruption or structural loss.
- **LLM Structured Separation Engine**: Introduced a zero-shot LLM extraction pipeline using Pydantic / JSON schemas to split unified company PDF Markdown into:
  1. **Criteria JSON**: Weights (e.g. Soft Skills 25%, Technical 50%, Process 25%), SLA limits (3m hold, 20s dead air, 10m email reply, 30s chat reply), verbatim greeting/closing/survey spiels, and channel overrides.
  2. **Company Details & SOPs**: Procedural guidelines, escalation protocols, verification rules, and troubleshooting manuals.
- **Multi-Tenant Vector DB RAG**: Integrated metadata filtering (`tenant_id`) using `sentence-transformers/all-MiniLM-L6-v2` embeddings in vector collections (ChromaDB / Qdrant / Pgvector) for instant policy lookups.
- **Hybrid Evaluation Engine & Circuit Breaker**: Combined RoBERTa sentiment analysis (line-by-line tone & tense moments), Vector RAG policy checks, and Gemma LLM scorecard judgments with an **Auto-Fail Circuit Breaker** (instant 0 score on discourtesy, call avoidance, fraud, or non-FCR).

### B. Upgraded Language Model
- Switched default model configuration in `src/core/gemma_client.py` and test scripts to **`gemma3:4b`** (3.3 GB model) for higher reasoning quality and stricter adherence to scorecard formats.

### C. Architecture Documentation & Visual Assets
- Created **`qa_system_architecture.html`**: An interactive, dark-themed HTML documentation dashboard featuring Mermaid.js flowcharts, sequence diagrams, ER database schemas, and case study breakdowns.
- Generated **`qa_execution_flow.png`**: High-resolution execution flow diagram highlighting the 4-step processing pipeline.

---

## 📁 2. Clean Modular Folder Structure

The project has been reorganized from a flat root layout into an industry-standard modular Python package structure:

```text
gemma-qa-analysis/
├── docs/                                  # 📄 System Documentation & Assets
│   ├── QA_Scoring_Documentation.docx
│   ├── api_samples.md
│   ├── qa_execution_flow.png              # 🖼️ Step-by-Step System Flow Diagram
│   └── qa_system_architecture.html        # 🌐 Interactive Architecture Dashboard
│
├── src/                                   # 💻 Core Source Code
│   ├── __init__.py
│   ├── api/                               # 🌐 FastAPI Web Application & Queue
│   │   ├── __init__.py
│   │   ├── job_queue.py                   # Background job queue manager
│   │   └── web_app.py                     # FastAPI REST API endpoints
│   │
│   ├── core/                              # ⚙️ Core Utilities & Clients
│   │   ├── __init__.py
│   │   ├── gemma_client.py                # Ollama Gemma HTTP API client
│   │   ├── report_pdf.py                  # PDF report generation module
│   │   └── weights_config.py              # Dynamic weights loader/saver
│   │
│   ├── rag/                               # 🔍 Vector Search & Knowledge Base
│   │   ├── __init__.py
│   │   ├── knowledge_base.py              # Reference QA pairs & compliance rules
│   │   ├── pdf_to_kb.py                   # PDF text extractor
│   │   ├── rag.py                         # MiniLM embedding retrieval engine
│   │   ├── rag_accuracy.py                # Answer key-point accuracy checker
│   │   └── rag_compliance.py              # Policy violation checker
│   │
│   └── services/                          # 🧠 QA Analysis Engine
│       ├── __init__.py
│       ├── qa_agent.py                    # Agent scorecard & scoring math
│       ├── qa_intensity.py                # RoBERTa sentiment & intensity model
│       ├── qa_report.py                   # Full QA report orchestrator
│       ├── qa_suggestions.py              # Agent improvement suggestions
│       ├── qa_summary.py                  # Call summary generator
│       └── response_time.py               # Response time calculator
│
├── tests/                                 # 🧪 Research, Benchmarks & Sample Calls
│   ├── compare_models.py                  # Model performance benchmark script
│   ├── full_conversation_qa_test.py
│   ├── gemma_demo.py
│   ├── locustfile.py                      # Load testing suite
│   ├── long_call_test.py
│   ├── sample_call.py                     # Sample transcript
│   └── weights_review.py
│
├── .gitignore
├── main.py                                # 🚀 Central Root Launcher
├── README.md
├── refactor.md                            # 📖 Refactoring & Setup Guide
├── request.http                           # 📡 HTTP REST API Client Requests
└── requirements.txt
```

---

## 🛠️ 3. Guide to Setup and Run

Follow these steps to set up the environment and start the QA Analysis application:

### Step 1: Create Python Virtual Environment (One-time)
Open PowerShell in the project folder and run:
```powershell
python -m venv venv
```

### Step 2: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```
*(If restricted by PowerShell execution policy, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first)*

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Start Ollama & Pull `gemma3:4b` Model
Make sure Ollama is installed and running, then pull the model:
```powershell
ollama pull gemma3:4b
```

### Step 5: Start the Server
Run the root launcher:
```powershell
python main.py
```

Open your browser at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 📡 4. Testing HTTP Endpoints
Use the provided [`request.http`](file:///c:/Users/Lenovo/Desktop/qa-analysis-2/gemma-qa-analysis/request.http) file in VS Code (with REST Client extension) or IntelliJ HTTP Client to test all REST endpoints.
