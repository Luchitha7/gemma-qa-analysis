# Gemma QA Analysis (SignalQA)

Automated quality assurance for customer-service calls. Give it a call
transcript and it returns a full QA report: an overall score out of 100, an
agent scorecard, a plain-language summary, answer-accuracy and compliance
checks, the tense moments of the call, agent response times, and concrete
coaching suggestions.

Everything runs **locally**. No transcripts leave the machine and there are no
API bills — the only language-model work is a small model served by Ollama on
the same host, and the rest is local embeddings and Python.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Scoring model](#scoring-model)
3. [Project structure](#project-structure)
4. [Dependencies](#dependencies)
5. [Requirements and setup](#requirements-and-setup)
6. [Running it](#running-it)
7. [REST API reference](#rest-api-reference)
8. [The job queue (handling load)](#the-job-queue-handling-load)
9. [Knowledge base](#knowledge-base)
10. [Configuration](#configuration)
11. [Testing and research scripts](#testing-and-research-scripts)

---

## How it works

The system leans on three components, each used only for what it is actually
good at:

- **RoBERTa** — [`cardiffnlp/twitter-roberta-base-sentiment-latest`](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest).
  Scores sentiment line by line and flags the tense moments. Fast, consistent,
  purpose-built for sentiment.
- **Gemma 3 1B** — run locally through [Ollama](https://ollama.com). Reads the
  whole call and makes the judgements a rule cannot: the summary, the agent
  scorecard, and the suggestions.
- **Sentence embeddings** — [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
  via sentence-transformers. Powers the retrieval (RAG) step that checks the
  agent's answers against a knowledge base of ideal answers and compliance
  rules. Matches on meaning, not exact words, and costs no tokens.

```
transcript
  ├─ RoBERTa      sentiment per line → tense moments, conversation score
  ├─ Gemma        summary · agent scorecard (PASS/PARTIAL/FAIL) · suggestions
  ├─ embeddings   answer accuracy vs ideal answers · compliance rule checks
  └─ timestamps   agent response time (if the transcript is timed)
        → weighted final QA score (0–100)
```

The division of labour is deliberate. Gemma can read and reason over a full
conversation but is unreliable when asked to produce numbers, so it only
*judges* — PASS, PARTIAL, or FAIL against each parameter — and the surrounding
Python does the arithmetic. That keeps the scores stable and reproducible while
still letting a language model handle the parts that need genuine reading.

The whole pipeline is assembled in `run_pipeline()` in `web_app.py`, which every
entry point (the web UI, the REST API, and the queue workers) calls.

---

## Scoring model

Each part produces a sub-score out of 100, and the final score is a weighted
blend:

| Sub-score          | Weight | Source                                   |
| ------------------ | -----: | ---------------------------------------- |
| Agent handling     |   0.45 | Gemma scorecard (5 parameters)           |
| Answer accuracy    |   0.20 | Embeddings vs ideal answers (RAG)        |
| Compliance         |   0.20 | Embeddings vs violation examples (RAG)   |
| Conversation tone  |   0.10 | RoBERTa sentiment across the call        |
| Response time      |   0.05 | Transcript timestamps                    |

Accuracy and response time can be absent — a call may raise no question that
matches the knowledge base, or carry no timestamps. When a part is missing its
weight is dropped and the rest are re-balanced, so the remaining weights still
sum to one and the score stays fair. The weights live in `FINAL_WEIGHTS` in
`qa_agent.py` and can be overridden per request (see [Configuration](#configuration)).

The **agent scorecard** grades five parameters, defined in `qa_agent.py` and
easy to edit:

- **Compliance** — followed process, promised nothing that cannot be delivered.
- **Tone and respect** — polite throughout; no scolding, blaming, or dismissing.
- **Responsiveness** — prompt and direct; no dodging or deflecting.
- **Ownership** — took responsibility instead of shifting blame.
- **Resolution** — actually resolved the issue and gave clear next steps.

A data-based safety net (`apply_tone_penalty`) caps the Tone rating: if the
sentiment pass shows the agent's own lines were harsh, Tone cannot come back as
a clean PASS.

---

## Project structure

### Pipeline stages (the scoring engine)

| File | What it does |
| ---- | ------------ |
| `qa_intensity.py` | RoBERTa per-line sentiment; flags the tense moments and the harsh agent lines. |
| `qa_summary.py` | One Gemma call: a short plain-language summary of the call. |
| `qa_agent.py` | The Gemma agent scorecard (PASS/PARTIAL/FAIL per parameter) **and** the scoring maths — `final_qa_score`, `conversation_score`, `FINAL_WEIGHTS`. |
| `qa_suggestions.py` | One Gemma call: coaching suggestions and follow-ups. Returns them as a clean list. |
| `rag.py` | The retrieval core: turns text into embeddings and finds the closest known question (cosine similarity, in memory). |
| `rag_accuracy.py` | Answer accuracy — did the agent cover the must-say key points for what the client asked. Token-free. |
| `rag_compliance.py` | Compliance — flags an agent line that is close in meaning to a known violation example. Token-free. |
| `response_time.py` | Agent response time from transcript timestamps (token-free). |
| `knowledge_base.py` | The reference data the RAG steps look things up in: `QA_PAIRS` and `COMPLIANCE_RULES`. Plain Python data, no logic. |

### Application layer

| File | What it does |
| ---- | ------------ |
| `web_app.py` | The FastAPI app: the web UI, the REST API, and `run_pipeline()` that ties every stage together. |
| `job_queue.py` | A small in-process work queue with backpressure — accepts up to a capacity, scores a couple at a time, turns the rest away. |
| `gemma_client.py` | Talks to Ollama's HTTP API; also tracks token usage per call. |
| `report_pdf.py` | Renders a scored result as a downloadable PDF (uses reportlab). |
| `weights_config.py` | Loads and saves the scoring weights (the file the `/weights` endpoints read and write). |
| `qa_report.py` | One-command CLI: runs every stage and prints a full report for the sample call. |
| `sample_call.py` | A representative ~5-minute support call used as the default/demo transcript. |

### Research and testing scripts

| File | What it does |
| ---- | ------------ |
| `gemma_demo.py` | Step-by-step comparison of a language model against a specialised model. |
| `long_call_test.py` | Both models scored line by line on a 17-turn call. |
| `full_conversation_qa_test.py` | Line-by-line versus whole-transcript scoring, and the token ceiling behind the design. |
| `compare_models.py` | Measures wall-clock latency and token throughput to compare models. |
| `weights_review.py` | Tries different weight sets against realistic scores (no model needed). |
| `locustfile.py` | Load test — many simulated users hammering the API. |

### Other files

| File | What it does |
| ---- | ------------ |
| `requirements.txt` | Python dependencies (see below). |
| `api_samples.md` | Example API requests and responses. |
| `QA_Scoring_Documentation.docx` | Written documentation of the scoring approach. |

---

## Dependencies

### Python packages (`requirements.txt`)

| Package | Why it is here |
| ------- | -------------- |
| `transformers` | Runs the RoBERTa sentiment model (and is a dependency of sentence-transformers). |
| `torch` | The tensor backend that `transformers` and `sentence-transformers` run on. CPU-only is fine. |
| `sentence-transformers` | The MiniLM embedding model used for the RAG accuracy and compliance checks. |
| `fastapi` | The web framework — serves the UI and the REST API. |
| `uvicorn` | The ASGI server that actually runs the FastAPI app. |
| `pydantic` | Validates request bodies (e.g. the `transcript` field). |
| `reportlab` | Generates the downloadable PDF report. |

### External services and models (not pip)

- **[Ollama](https://ollama.com)** serving **`gemma3:1b`** — the local LLM used
  for the summary, scorecard, and suggestions. Must be running for scoring.
- **RoBERTa** and **MiniLM** model weights (~500 MB combined) download on first
  run from Hugging Face and are cached locally; after that the app works offline.

---

## Requirements and setup

- macOS (developed on Apple Silicon, CPU-only — no GPU required)
- Python 3.11
- [Ollama](https://ollama.com)

```bash
# 1. Install Ollama and pull the language model (one-time)
brew install ollama
brew services start ollama
ollama pull gemma3:1b

# 2. Create the virtual environment and install dependencies (one-time)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The first analysis also downloads the RoBERTa and MiniLM models (~500 MB) and
caches them; after that it works offline.

---

## Running it

Activate the environment and make sure Ollama is running first.

### Web app

```bash
source venv/bin/activate
python web_app.py
# open http://localhost:8000
```

Paste a transcript — one turn per line, each starting with `Agent:` or
`Client:` — and click **Analyze Call**. **Load Sample** fills in an example. Add
leading timestamps (`[00:15] Agent: ...`) to get response-time scoring.

### Full report (one command, CLI)

```bash
python qa_report.py
```

Runs every stage and prints a single report for the call in `sample_call.py`,
including a per-call breakdown of how many Gemma tokens it used.

### Running stages individually

Each stage runs on its own, which is how the project was built and how token use
is kept low — e.g. `python qa_intensity.py`, `python rag_compliance.py`.

---

## REST API reference

Base URL (local): `http://localhost:8000`. All requests and responses are JSON
unless noted. The scoring request body is a single `transcript` string with
`Agent:` / `Client:` lines and optional `[MM:SS]` timestamps.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/analyze` | Score one call now; returns the full result. |
| `POST` | `/jobs` | Queue a call for scoring; returns a job id immediately (or 503 if at capacity). |
| `GET`  | `/jobs/{id}` | Fetch a queued job — its status, and the result once done. |
| `GET`  | `/jobs` | The whole queue at a glance (counts + every job). |
| `GET`  | `/queue` | A live HTML dashboard for demos. |
| `GET`  | `/weights` | The scoring weights currently in effect. |
| `POST` | `/weights` | Save a new set of weights. |
| `POST` | `/report` | Return a scored result as a downloadable PDF. |
| `GET`  | `/` | The web UI (HTML). |

### Request body (scoring)

```json
{ "transcript": "[00:00] Agent: Thank you for calling...\n[00:06] Client: ..." }
```

### Result shape (`/analyze`, and inside a finished job's `result`)

| Field | Meaning |
| ----- | ------- |
| `final` | Overall score 0–100. |
| `agent` | Agent scorecard score. |
| `conversation` | How the customer sounded overall (sentiment). |
| `band` | `GOOD` / `OKAY` / `NEEDS IMPROVEMENT`. |
| `summary` | Short written summary. |
| `ratings[]` | Agent scorecard: `name`, `rating` (PASS/PARTIAL/FAIL/UNRATED), `reason`. |
| `compliance_score`, `compliance[]` | Per-rule check: `name`, `rule`, `status` (OK/BROKEN), `evidence`. |
| `accuracy_overall`, `accuracy[]` | Per-question detail: `client_question`, `matched_question`, `ideal_answer`, `covered`, `missed`. Can be null/empty. |
| `response_time_score`, `response_times[]` | Per reply: `delay`, `slow`, `agent_text`, `client_text`. Empty if no timestamps. |
| `suggestions[]` | Coaching points, as a list of strings. |
| `intense[]` | Tense moments (strong negative sentiment). |
| `token_usage` | Gemma token cost, per step and total. |

More examples are in [`api_samples.md`](api_samples.md).

---

## The job queue (handling load)

Scoring a call runs the local model several times, so the machine can only do a
few at once. `/analyze` scores immediately, which is fine for one call at a time
— but under a burst of traffic that would overload the host. The `/jobs`
endpoints add **backpressure**:

- The system accepts up to **`CAPACITY`** jobs (default **5**).
- **`MAX_CONCURRENT`** workers (default **2**) score jobs a couple at a time; the
  rest wait in line.
- If a new request arrives when the system is already full, it is turned away
  with **HTTP 503** and a `Retry-After` header instead of being queued — so the
  backlog can never grow without bound.

Submit with `POST /jobs`, then poll `GET /jobs/{id}` for the result. `GET /jobs`
shows the whole queue. Both `/analyze` and the queued path return the **same**
result shape, because both call `run_pipeline()`.

---

## Knowledge base

`knowledge_base.py` holds the reference material the RAG step retrieves against:

- **`QA_PAIRS`** — a known question, alternate phrasings (`variants`), the
  must-say `key_points`, and an `ideal_answer`. Accuracy is scored as the share
  of key points the agent's reply actually covers, each point matched against
  the closest sentence of the reply.
- **`COMPLIANCE_RULES`** — each with a short `name`, the `rule`, and example
  phrases of what breaking it sounds like (`violations`). An agent line close
  enough in meaning to a violation example flags the rule, with the offending
  line kept as evidence.

Both are plain Python lists — extend them to fit a real call centre's answers
and policies.

---

## Configuration

### Scoring weights

The defaults live in `FINAL_WEIGHTS` (`qa_agent.py`). `GET /weights` returns the
weights in effect; `POST /weights` saves a new set (persisted via
`weights_config.py`), and every later `/analyze` uses them. Only known numeric
keys are kept, so a bad payload cannot corrupt the file.

### Environment variables (queue tuning)

| Variable | Default | Meaning |
| -------- | ------: | ------- |
| `QA_CAPACITY` | `5` | Most jobs the queue will hold before returning 503. |
| `QA_MAX_CONCURRENT` | `2` | How many jobs are scored at the same time. |
| `QA_RETRY_AFTER` | `10` | Seconds sent in the `Retry-After` header when busy. |

---

## Testing and research scripts

- **Load testing** — `locust -f locustfile.py` fires many simulated users at the
  API so you can watch the queue fill and drain (pair it with the `/queue`
  dashboard).
- **Research scripts** (`gemma_demo.py`, `long_call_test.py`,
  `full_conversation_qa_test.py`, `compare_models.py`) are the experiments that
  settled the design — why Gemma handles the reading while the scoring stays in
  code.
- **Weights review** — `weights_review.py` tries different weight sets against
  realistic sub-scores without needing any model running.
