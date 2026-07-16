# Gemma QA Analysis

Automated quality-assurance (QA) analysis of a customer service call. It reads a
call transcript and produces a full QA report: a summary, an agent scorecard, the
tense moments of the call, suggestions, and scores out of 100.

Two models work together, each doing what it's good at:

- **RoBERTa** ([cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest))
  scores sentiment line by line and flags the **tense moments** of the call.
- **Gemma 3 1B** (run locally via [Ollama](https://ollama.com)) does the
  **analysis**: the summary, the agent scorecard, and the suggestions.

```
transcript
   -> RoBERTa  : sentiment per line + tense moments
   -> Gemma    : summary, agent scorecard, suggestions
   -> scoring  : agent + conversation + final QA score (0-100)
```

Everything runs locally.

## Why the work is split between two models

RoBERTa is fast, consistent, and purpose-built for sentiment, but it can't reason
over a whole call. Gemma can read and analyse a whole conversation but is
unreliable at producing numbers. So Gemma only *judges* (PASS / PARTIAL / FAIL per
parameter) and the code does the *maths*, which keeps the scores reliable.

## Requirements

- macOS (developed on Apple Silicon, CPU-only)
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

## Usage

Make sure the virtual environment is active and Ollama is running.

### Full QA report (one command)

```bash
python qa_report.py
```

Runs everything and prints one report for the call in `sample_call.py`.

### Individual parts

Each part runs on its own (built part by part to keep token usage low):

- `qa_intensity.py` — RoBERTa scores sentiment and flags the tense moments.
- `qa_summary.py` — Gemma writes a plain summary of the call.
- `qa_agent.py` — Gemma judges the agent against the QA parameters, plus scores.
- `qa_suggestions.py` — Gemma lists what the client wanted and follow-ups.

### Using your own call

Edit the `TRANSCRIPT` list in `sample_call.py` (one `("Agent", "...")` or
`("Client", "...")` tuple per line), then re-run any script above.

### Research / comparison scripts

Background tests comparing Gemma against RoBERTa for scoring, which is why this
project uses Gemma for analysis rather than scoring:

- `gemma_demo.py` — a guided, step-by-step demo of LLM vs specialized model.
- `long_call_test.py` — both models scored line by line on a 17-line call.
- `full_conversation_qa_test.py` — line-by-line vs whole-transcript-at-once,
  plus the token-volume limit that makes full-call scoring an LLM job.

## The QA parameters

Defined in `qa_agent.py` (`PARAMETERS`) and easy to edit:

- **Compliance** — followed proper process, no promises they can't keep.
- **Tone and respect** — polite, no scolding or blaming the client.
- **Responsiveness** — prompt and direct, no dodging.
- **Ownership** — took responsibility instead of shifting blame.
- **Resolution** — actually solved the issue with clear next steps.
