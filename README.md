# 🚀 Multi-Tenant Automated QA Intelligence Platform

> **Production-grade AI-powered Quality Assurance platform for enterprise contact centers.**  
> Automatically ingests company guideline PDFs into lossless Markdown, dynamically extracts custom criteria weights and auto-fail rules, indexes operational policies into ChromaDB Vector RAG, and audits omni-channel customer interactions (Calls, Emails, Chats) using **Gemma 3 4B** and **RoBERTa Sentiment Analysis**.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Getting Started](#-getting-started)
- [Environment Configuration](#-environment-configuration)
- [API Overview](#-api-overview)
- [Documentation & Resources](#-documentation--resources)

---

## 📖 Overview

The **Multi-Tenant Automated QA Intelligence Platform** transforms unstructured contact center QA guidelines into dynamic, actionable audit rules. Instead of hardcoded rubrics, the platform parses guideline PDFs, extracts scoring categories, weights, verbatim spiels, and auto-fail conditions, and indexes operational policies for retrieval-augmented generation (RAG). 

Auditors and managers can audit interactions across channels with transparent mathematical scoring, sentiment intensity tracking, and full prompt preview capabilities.

---

## 🏗️ Architecture

The system follows a modular microservice architecture separating document processing, vector search, sentiment classification, dynamic prompt engineering, and deterministic scoring.

![Architectural Overview](resources/architectural-overview.png)

### End-to-End Workflow:
1. **Guideline Ingestion**: PyMuPDF converts PDF guidelines into lossless Markdown tables and sections.
2. **Criteria & Policy Extraction**: Gemma 3 4B parses weights, criteria categories, verbatim scripts, and auto-fail rules into structured JSON.
3. **Vector Indexing**: Operational policies are chunked and indexed into ChromaDB with `all-MiniLM-L6-v2` dense embeddings.
4. **Interaction Analysis**:
   - **RoBERTa** evaluates sentiment intensity and flags negative agent/customer spikes.
   - **ChromaDB RAG** fetches relevant policy context for the specific interaction scenario.
   - **Gemma 3 4B** evaluates agent compliance against extracted criteria and policy evidence.
5. **Deterministic Scorecard**: Final scores are calculated via strict weighted formulas with instant zero-tolerance auto-fail enforcement.

---

## ✨ Key Features

- **Multi-Tenant Architecture**: Complete data isolation per company/client (e.g., S-NET, BrightWave) with dedicated schemas in PostgreSQL.
- **Lossless PDF-to-Markdown Ingestion**: Ingests complex multi-page guidelines while preserving tables, percentages, and formatting.
- **Dynamic Rule Extraction (Zero Hardcoding)**: Automatically extracts scoring weights (e.g., 30%/45%/25%), line items, scripts, and auto-fail circuit breakers directly from guidelines.
- **Vector Policy Knowledge Base (ChromaDB)**: Performs semantic search over SLAs, hold policies, verification protocols, and CRM requirements.
- **RoBERTa Sentiment & Intensity Analysis**: Detects high-tension exchanges, customer frustration, and harsh agent responses to justify tone deductions.
- **Dynamic Prompt Builder & UI Preview**: Allows QA auditors to inspect, edit, or copy the generated LLM prompt before triggering evaluation.
- **Deterministic Mathematical Scorecard**:
  $$\text{Final Score} = \sum (\text{Category Score} \times \text{Weight})$$
  *(Automatically resets to 0/100 if any auto-fail condition is met)*.
- **Comprehensive Historical Audits**: Full audit logs with per-record review, detailed category breakdowns, and export capabilities.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Pydantic |
| **Frontend UI** | React, Vite, TailwindCSS, Lucide Icons |
| **LLM Inference** | Ollama (`gemma3:4b`) |
| **Sentiment Analysis** | Hugging Face Transformers (`cardiffnlp/twitter-roberta-base-sentiment-latest`), PyTorch |
| **Vector Database & RAG** | ChromaDB, Sentence-Transformers (`all-MiniLM-L6-v2`) |
| **Relational Database** | PostgreSQL 17, SQLAlchemy, Psycopg2 |
| **Document Processing** | PyMuPDF (fitz), PyPDF, ReportLab |

---

## 📂 Project Structure

```text
gemma-qa-analysis/
├── main.py                          # Server entry point for FastAPI backend
├── requirements.txt                 # Python dependencies
├── .env.example                     # Sample environment configuration
├── docs/                            # Guides, API samples, and documentation
│   ├── api_samples.md               # API request/response samples
│   ├── run_guide.md                 # Complete testing and execution guide
│   └── prompt-builder.md            # Prompt builder documentation
├── resources/                       # Architectural diagrams & prompt templates
│   ├── architectural-overview.png   # Architecture diagram
│   ├── prompt-builder-overview.png  # Prompt builder diagram
│   └── prompts/                     # System prompts for LLM tasks
├── frontend/                        # React + Vite frontend application
│   ├── src/                         # React components, pages, and hooks
│   └── package.json                 # Frontend dependencies
├── src/                             # Core Python backend package
│   ├── api/
│   │   └── web_app.py               # REST API routers & multi-tenant endpoints
│   ├── core/
│   │   └── gemma_client.py          # Ollama Gemma 3 4B integration wrapper
│   ├── db/
│   │   ├── database.py              # PostgreSQL connection & session manager
│   │   └── models.py                # SQLAlchemy ORM models
│   ├── rag/
│   │   ├── pdf_parser.py            # PDF to Markdown parser
│   │   ├── llm_separator.py         # Dynamic criteria & policy extractor
│   │   └── vector_store.py          # ChromaDB vector store client
│   └── services/
│       ├── dynamic_evaluator.py     # Evaluation orchestrator & scorecard calculator
│       ├── qa_intensity.py          # RoBERTa sentiment intensity analyzer
│       ├── qa_summary.py            # Interaction executive summarization
│       ├── qa_suggestions.py        # Coaching recommendations generator
│       └── response_time.py         # Transcript timestamp and latency analyzer
└── tests/                           # Integration and demo test scripts
```

---

## ⚡ Prerequisites

Before running the application, make sure you have the following installed:

1. **Python 3.11+**
2. **Node.js 18+** & **npm**
3. **PostgreSQL 17** (running on `localhost:5432`)
4. **Ollama** with the `gemma3:4b` model pulled:
   ```bash
   ollama pull gemma3:4b
   ```

---

## 🚀 Getting Started

### 1. Clone & Configure Environment

```bash
# Clone the repository
git clone https://github.com/Luchitha7/gemma-qa-analysis.git
cd gemma-qa-analysis

# Copy sample environment variables
cp .env.example .env
```

Edit `.env` to match your PostgreSQL credentials and settings.

### 2. Install Dependencies

**Backend:**
```bash
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 3. Run the Application

Start the services across 3 terminal windows:

#### 🔹 Terminal 1: Ollama LLM Server
```bash
ollama serve
```

#### 🔹 Terminal 2: FastAPI Backend Server
```bash
python main.py
```
> Backend API will be available at **`http://localhost:8000`** (Swagger docs at **`http://localhost:8000/docs`**).

#### 🔹 Terminal 3: Vite Frontend UI
```bash
cd frontend
npm run dev
```
> Frontend Web UI will be available at **`http://localhost:5173`**.

---

## ⚙️ Environment Configuration

Key configuration parameters in `.env`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DB_HOST` / `DB_PORT` | `localhost` / `5432` | PostgreSQL host and port |
| `DB_NAME` / `DB_USERNAME` | `qa_database` / `postgres` | Database credentials |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama service endpoint |
| `GEMMA_MODEL` | `gemma3:4b` | Gemma LLM model identifier |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-Transformers embedding model |
| `CHROMA_PERSIST_DIR` | `vector_data` | Directory for persistent vector storage |
| `SENTIMENT_MODEL` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | RoBERTa sentiment model |
| `SERVER_PORT` | `8000` | FastAPI server port |

---

## 🔌 API Overview

Interactive Swagger documentation is available at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/tenants` | List all registered tenant companies |
| `POST` | `/api/tenants` | Create a new tenant company namespace |
| `POST` | `/api/upload-guideline` | Upload guideline PDF, parse to Markdown, extract criteria & index RAG policies |
| `GET` | `/api/criteria/{company_id}` | Get extracted dynamic criteria and weights |
| `POST` | `/api/evaluate` | Run full automated QA audit on customer interaction transcript |
| `POST` | `/api/preview-prompt` | Preview synthesized LLM prompt before evaluation |
| `GET` | `/api/evaluations/{company_id}` | Fetch historical audit records and scores |

---

## 📚 Documentation & Resources

- 📖 [Complete Run & Testing Guide](docs/run_guide.md)
- 🔌 [API Samples & Payloads](docs/api_samples.md)
- 🧠 [Prompt Builder Architecture](docs/prompt-builder.md)
- 📊 [Postman Collection](resources/postman_collection.json)
