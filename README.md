# Gemma QA Analysis

Automated quality assurance for customer-service calls. Give it a transcript and
it returns a full QA report: an overall score out of 100, an agent scorecard, a
plain-language summary, the answer-accuracy and compliance checks, the tense
moments of the call, and concrete suggestions for the agent.

Everything runs locally. No transcripts leave the machine, and there are no API
bills — the only language-model work is a small model served by Ollama on the
same host.

## How it works

The system leans on three components, each used only for what it is actually good
at:

- **RoBERTa** — [`cardiffnlp/twitter-roberta-base-sentiment-latest`](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest).
  Scores sentiment line by line and flags the tense moments. Fast, consistent,
  purpose-built for sentiment.
- **Gemma 3 1B** — run locally through [Ollama](https://ollama.com). Reads the
  whole call and makes the judgements a rule can't: the summary, the agent
  scorecard, and the suggestions.
- **Sentence embeddings** — [`all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
  via sentence-transformers. Powers the retrieval (RAG) step that checks the
  agent's answers against a knowledge base of ideal answers and compliance rules.
  Matches on meaning, not exact words, and costs no tokens.

```
transcript
  ├─ RoBERTa      sentiment per line → tense moments, conversation score
  ├─ Gemma        summary · agent scorecard (PASS/PARTIAL/FAIL) · suggestions
  ├─ embeddings   answer accuracy vs ideal answers · compliance rule checks
  └─ timestamps   agent response time (if the transcript is timed)
        → weighted final QA score (0–100)
```

The division of labour is deliberate. Gemma can read and reason over a full
conversation but is unreliable when asked to produce numbers, so it only *judges*
— PASS, PARTIAL, or FAIL against each parameter — and the surrounding Python does
the arithmetic. That keeps the scores stable and reproducible while still letting
a language model handle the parts that need genuine reading.

## Scoring

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
sum to one and the score stays fair.

The **agent scorecard** grades five parameters, defined in `qa_agent.py` and easy
to edit:

- **Compliance** — followed process, promised nothing that can't be delivered.
- **Tone and respect** — polite throughout; no scolding, blaming, or dismissing.
- **Responsiveness** — prompt and direct; no dodging or deflecting.
- **Ownership** — took responsibility instead of shifting blame.
- **Resolution** — actually resolved the issue and gave clear next steps.

## Requirements

- macOS (developed on Apple Silicon, CPU-only — no GPU required)
- Python 3.11
- [Ollama](https://ollama.com) with the Gemma model pulled:

  ```bash
  brew install ollama
  brew services start ollama
  ollama pull gemma3:1b
  ```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The first run downloads the RoBERTa and MiniLM models (~500 MB combined) and
caches them; subsequent runs are offline.

## Usage

Activate the virtual environment and make sure Ollama is running.

### Full report (one command)

```bash
python qa_report.py
```

Runs every stage and prints a single report for the call in `sample_call.py`,
including a per-call breakdown of how many Gemma tokens it used.

### Web app

```bash
python web_app.py
# open http://localhost:8000
```

Paste a transcript — one turn per line, each starting with `Agent:` or `Client:`
— and click **Analyze Call** for the same report as a styled page. **Load
sample** fills in an example to try it quickly.

### Your own call

Edit the `TRANSCRIPT` list in `sample_call.py`: one `("Agent", "...")` or
`("Client", "...")` tuple per turn, then re-run any script. Add leading
timestamps (`[00:15] Agent: ...`) if you want response-time scoring.

### Running stages individually

Each stage runs on its own, which is how the project was built and how token use
is kept low:

| Script               | Stage                                                    |
| -------------------- | -------------------------------------------------------- |
| `qa_intensity.py`    | RoBERTa sentiment and tense-moment flagging              |
| `qa_summary.py`      | Gemma call summary                                       |
| `qa_agent.py`        | Gemma agent scorecard plus the scoring maths             |
| `qa_suggestions.py`  | Gemma suggestions and follow-ups                         |
| `rag_accuracy.py`    | Answer accuracy against the knowledge base (token-free)  |
| `rag_compliance.py`  | Compliance checks against violation examples (token-free)|
| `response_time.py`   | Response-time scoring from timestamps                    |

## Knowledge base

`knowledge_base.py` holds the reference material the RAG step retrieves against:

- **QA pairs** — a known question, alternate phrasings, the must-say *key points*,
  and an ideal answer. Accuracy is scored as the share of key points the agent's
  reply actually covers, each point matched against the closest sentence of the
  reply.
- **Compliance rules** — each with example phrases of what breaking it sounds
  like. An agent line close enough in meaning to a violation example flags the
  rule, with the offending line kept as evidence.

Both are plain Python lists — extend them to fit a real call centre's answers and
policies.

## Research scripts

Background experiments that settled the design — why Gemma handles analysis while
the scoring stays in code:

- `gemma_demo.py` — a step-by-step comparison of a language model against a
  specialised model.
- `long_call_test.py` — both models scored line by line on a 17-turn call.
- `full_conversation_qa_test.py` — line-by-line versus whole-transcript scoring,
  and the token-volume ceiling that makes full-call judgement a job for the LLM.
