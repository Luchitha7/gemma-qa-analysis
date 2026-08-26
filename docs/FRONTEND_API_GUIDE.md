# SignalQA API Reference for the UI

This is the data contract for the SignalQA scoring backend. It lists the
endpoints the UI uses, the exact request and response shapes, and what every
field means, including its type, value range, and the enum values it can take.

It is deliberately about the data only. How the UI looks, what is emphasised,
what layout, colours, or components to use, is entirely your call. This just
tells you what comes back so nothing surprises you.

Field names and structures are taken straight from the backend code, so they
are real. The example values are placeholders.

Base URL for local development: `http://localhost:8000`

For ready-to-use sample payloads you can hard-code while the backend is not
running, see `api_samples.md`.

---

## 1. The shape of it

The backend scores a call transcript and returns one **result object**
(Section 4) with everything about that call: a final score, five sub-scores, a
summary, a compliance check, an agent scorecard, response times, an accuracy
breakdown, suggestions, and flagged tense moments.

The flow:

1. Send a transcript to `POST /analyze`.
2. It returns the full result object (this takes several seconds while the
   models run).
3. Optionally read or save the scoring weights (`/weights`), or get a PDF of a
   result (`/report`).

---

## 2. Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/analyze` | Score a transcript, return the full result |
| GET | `/weights` | Read the scoring weights in effect |
| POST | `/weights` | Save new scoring weights |
| POST | `/report` | Generate a PDF report for a result |

All request and response bodies are JSON, except `/report` which returns PDF
bytes.

---

## 3. Scoring a call — `POST /analyze`

Request body:

```json
{ "transcript": "Agent: Hi, how can I help?\nClient: I was double charged." }
```

The transcript is one string, one turn per line. Speaker labels are flexible:
`Agent:` / `Client:` but also `AI:` / `Customer:` / `Caller:` etc., and leading
timestamps like `[00:15]` are understood and used for response-time scoring.

Response: the full **result object** (Section 4), HTTP 200. Scoring runs several
models, so expect a few seconds before it returns.

Validation: if no transcript lines are found, the response is
`{ "error": "No transcript lines found. Use 'Agent: ...' and 'Client: ...' on separate lines." }`
still with HTTP 200. **Check for an `error` key** before using the result.

---

## 4. The result object (the field dictionary)

`/analyze` returns this shape. Fields marked *nullable* can be `null` when a
section could not be computed. Arrays can be empty when there was nothing to
report for that section.

### 4.1 Top-level scores

| Field | Type | Range | Meaning |
|---|---|---|---|
| `final` | number | 0–100 | The overall QA score. |
| `agent` | number | 0–100 | Agent handling sub-score. |
| `conversation` | number | 0–100 | Customer sentiment / conversation sub-score. |
| `accuracy_overall` | number \| null | 0–100 | Answer accuracy sub-score. |
| `compliance_score` | number \| null | 0–100 | Compliance sub-score. |
| `response_time_score` | number \| null | 0–100 | Response-time sub-score. |
| `band` | string | enum | Overall band for `final`. |

**`band` values** (derived from `final`):

| Value | Condition |
|---|---|
| `GOOD` | `final` ≥ 80 |
| `OKAY` | 60 ≤ `final` < 80 |
| `NEEDS IMPROVEMENT` | `final` < 60 |

### 4.2 Meta

| Field | Type | Meaning |
|---|---|---|
| `parsed` | object | How the transcript was read: `{ "turns": int, "agent": int, "client": int }`. |
| `warning` | string | Non-empty when the parse is suspect (e.g. no client lines detected). Empty string means no warning. |
| `token_usage` | object | Gemma token cost: `{ "input": int, "output": int, "total": int, "calls": [ { "label": str, "input": int, "output": int } ] }`. Only Gemma uses tokens; sentiment and rule/accuracy checks are token-free. |

### 4.3 Summary and suggestions

| Field | Type | Meaning |
|---|---|---|
| `summary` | string | A short paragraph summarising the call. |
| `suggestions` | string | Coaching suggestions. Pre-formatted text that may contain newlines. |

### 4.4 `ratings` — the agent scorecard

Array of criteria the agent was judged on:

```json
{ "name": "Empathy", "rating": "PASS", "reason": "Acknowledged the frustration and apologised." }
```

| Field | Type | Meaning |
|---|---|---|
| `name` | string | The criterion, e.g. "Empathy", "Resolution". |
| `rating` | string enum | `PASS` \| `PARTIAL` \| `FAIL` \| `UNRATED`. |
| `reason` | string | One-line justification. |

(For reference, internally PASS = 100, PARTIAL = 50, FAIL = 0.)

### 4.5 `compliance` — the compliance check

Array of rules checked against the call:

```json
{ "rule": "Verify identity before account changes", "status": "OK", "evidence": "" }
```

| Field | Type | Meaning |
|---|---|---|
| `rule` | string | The compliance rule. |
| `status` | string enum | `OK` \| `BROKEN`. |
| `evidence` | string | For `BROKEN`, the exact line that broke it. Empty when `OK`. |

### 4.6 `response_times` — reply speed

Array, one entry per agent reply that followed a client turn. Empty when the
transcript has no timestamps.

```json
{ "agent_turn": 3, "delay": 4.0, "slow": false, "client_text": "So what happens now?" }
```

| Field | Type | Meaning |
|---|---|---|
| `agent_turn` | int | Which agent turn this reply was. |
| `delay` | number | Seconds the agent took to reply. |
| `slow` | boolean | `true` if flagged slow. |
| `client_text` | string | The client line the agent was replying to. |

Empty array means there were no timestamps to measure.

### 4.7 `accuracy` — answer accuracy vs a knowledge base

Array, one entry per client question that matched the knowledge base. Empty
when nothing matched.

```json
{
  "client_question": "How long until the refund shows up?",
  "matched_question": "Refund processing time",
  "confidence": "high",
  "agent_answer": "It will show up in 3 to 5 business days.",
  "ideal_answer": "Refunds appear within 3 to 5 business days.",
  "covered": ["3 to 5 business days"],
  "missed": [],
  "accuracy": 100.0
}
```

| Field | Type | Meaning |
|---|---|---|
| `client_question` | string | What the client asked. |
| `matched_question` | string | The knowledge-base entry it matched. |
| `confidence` | string | Match confidence label. |
| `agent_answer` | string | What the agent actually said. |
| `ideal_answer` | string | The reference answer. |
| `covered` | string[] | Key points the agent covered. |
| `missed` | string[] | Key points the agent missed. |
| `accuracy` | number | 0–100 for this question. |

### 4.8 `intense` — tense moments

Array of turns flagged as emotionally intense by sentiment analysis. Empty when
the call stayed calm.

```json
{ "turn": 4, "speaker": "Client", "sentiment": -0.82, "text": "This is the second time!" }
```

| Field | Type | Meaning |
|---|---|---|
| `turn` | int | Turn number in the transcript. |
| `speaker` | string | `Agent` or `Client`. |
| `sentiment` | number | Sentiment score; negative is more negative. |
| `text` | string | The line. |

---

## 5. Scoring weights

The final score is a weighted blend of the five sub-scores, and the weights are
editable.

### `GET /weights`

Returns the weights in effect, as fractions that add up to about 1.0:

```json
{ "agent": 0.45, "accuracy": 0.20, "compliance": 0.20, "conversation": 0.10, "response_time": 0.05 }
```

### `POST /weights`

Send the same shape to save. The scorer rescales, so they do not need to total
exactly 1.0. Response:

```json
{ "status": "saved", "weights": { "agent": 0.45, "…": 0.05 } }
```

The five keys map to the five sub-scores: `agent` → Agent, `accuracy` →
Accuracy, `compliance` → Compliance, `conversation` → Customer sentiment,
`response_time` → Response time. Whatever is saved is used by every future
`/analyze`.

---

## 6. PDF report — `POST /report`

Generates a one-call PDF. Send it the result object you already have (so the
call is not scored twice); it also accepts a raw `{ "transcript": "…" }` and
will score first.

- Request: a full result object (Section 4) **or** `{ "transcript": "…" }`.
- Response: PDF **bytes**, `Content-Type: application/pdf`, with
  `Content-Disposition: attachment; filename=call_qa_report.pdf`.

---

## 7. Enum and nullability quick-reference

Facts about the data that are easy to miss:

| Enum | Values | Where |
|---|---|---|
| Band | `GOOD`, `OKAY`, `NEEDS IMPROVEMENT` | `band` |
| Rating | `PASS`, `PARTIAL`, `FAIL`, `UNRATED` | `ratings[].rating` |
| Compliance | `OK`, `BROKEN` | `compliance[].status` |

- Nullable sub-scores: `accuracy_overall`, `compliance_score`,
  `response_time_score` can be `null`.
- Arrays that can be empty: `ratings`, `compliance`, `response_times`,
  `accuracy`, `intense`.
- `warning` is `""` when there is nothing to warn about.
- `/analyze` returns an `{ "error": "…" }` object for an unparseable transcript.

---

## 8. Reference material

- `api_samples.md` — copy-paste sample payloads, no backend needed.
- A running instance to see live-shaped responses.
- The current UI as one example of these fields rendered. It is only a
  reference point, not a template to follow.
- `README.md` and `QA_Scoring_Documentation.docx` for how the scores are
  produced.
