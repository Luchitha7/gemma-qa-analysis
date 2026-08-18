# SignalQA Sample API Data

Static sample data for building and testing the frontend. It does not need any model
running. The field names and structure are real and taken from the backend, so you can
swap in a real response later without changing your UI. The values are placeholder
examples, not a real result.

Base URL for local development: `http://localhost:8000`

There are three endpoints.

**POST `/analyze`** sends a call transcript and returns all the scores.

**GET `/weights`** returns the scoring weights currently in effect.

**POST `/weights`** saves new scoring weights.

## POST /analyze

### Request payload

```json
{
  "transcript": "[00:00] Agent: Thank you for calling HomeNet support, how can I help you today?\n[00:06] Client: I was charged twice for my subscription this month and I want it fixed.\n[00:09] Agent: I'm sorry to hear that. Let me pull up your account and take a look.\n[00:14] Client: This is the second time this has happened, it's really frustrating.\n[00:31] Agent: I completely understand, that's not acceptable. I can see the duplicate charge now.\n[00:36] Client: Okay, so what happens now?\n[00:39] Agent: I've refunded the extra charge and it will show up in 3 to 5 business days.\n[00:43] Client: Alright, thank you.\n[01:09] Agent: Of course. Is there anything else I can help you with?"
}
```

The whole transcript is one string, with each line separated by `\n`.

### Response

```json
{
  "final": 78.4,
  "agent": 82.0,
  "conversation": 71.0,
  "band": "Good",
  "parsed": { "turns": 9, "agent": 5, "client": 4 },
  "token_usage": { "input": 512, "output": 138, "total": 650 },
  "warning": "",
  "summary": "Client reported a duplicate subscription charge and was frustrated it had happened twice. The agent apologized, confirmed the duplicate charge, and issued a refund expected within 3 to 5 business days.",
  "ratings": [
    {
      "name": "Empathy",
      "rating": "PASS",
      "reason": "Agent acknowledged the client's frustration and apologized sincerely."
    },
    {
      "name": "Resolution",
      "rating": "PASS",
      "reason": "The duplicate charge was identified and refunded within the call."
    },
    {
      "name": "Professionalism",
      "rating": "PARTIAL",
      "reason": "Tone was professional, but the agent did not confirm the client's identity before making account changes."
    }
  ],
  "intense": [
    {
      "turn": 4,
      "speaker": "Client",
      "sentiment": "negative",
      "text": "This is the second time this has happened, it's really frustrating."
    }
  ],
  "suggestions": [
    "Verify customer identity before discussing or modifying account details.",
    "Offer a goodwill gesture when an issue is a repeat occurrence."
  ],
  "compliance_score": 75.0,
  "compliance": [
    {
      "rule": "Greeting with company name",
      "met": true,
      "evidence": "Thank you for calling HomeNet support, how can I help you today?"
    },
    {
      "rule": "Identity verification",
      "met": false,
      "evidence": ""
    },
    {
      "rule": "Closing and anything else",
      "met": true,
      "evidence": "Is there anything else I can help you with?"
    }
  ],
  "response_time_score": 88.0,
  "response_times": [
    {
      "agent_turn": 5,
      "delay": 17,
      "slow": true,
      "client_text": "This is the second time this has happened, it's really frustrating."
    }
  ],
  "accuracy_overall": 80.0,
  "accuracy": [
    {
      "client_question": "I was charged twice, I want it fixed.",
      "matched_question": "How do I get a refund for a duplicate charge?",
      "confidence": 0.91,
      "agent_answer": "I've refunded the extra charge and it will show up in 3 to 5 business days.",
      "ideal_answer": "Confirm the duplicate charge, issue a refund, and state the 3 to 5 business day timeline.",
      "covered": ["refund issued", "3 to 5 business day timeline"],
      "missed": ["confirm which card was refunded"],
      "accuracy": 80.0
    }
  ]
}
```

### Field meanings

`final` is the final weighted score, from 0 to 100.

`agent` is the average of the LLM rating checks, from 0 to 100.

`conversation` is the overall conversation sentiment score, from 0 to 100.

`band` is a text label for the final score, for example "Good".

`parsed` shows how many turns, agent lines, and client lines were read.

`token_usage` shows the LLM tokens used, as input, output, and total.

`warning` is only filled in when the transcript looked wrong in some way.

`summary` is a short plain English summary of the call.

`ratings` is an array of LLM judge checks, each marked PASS, PARTIAL, FAIL, or UNRATED.

`intense` is an array of the turns with strong, usually negative, sentiment.

`suggestions` is an array of coaching tips for the agent.

`compliance_score` is a number from 0 to 100.

`compliance` is an array of compliance rules and whether each was met.

`response_time_score` is a number from 0 to 100, for how promptly the agent replied.

`response_times` is an array of per reply delays. The `slow` flag is true when a gap was long.

`accuracy_overall` is a number from 0 to 100.

`accuracy` is an array comparing each client question against the ideal answer.

## GET /weights

### Request payload

None. It is a GET, so you just call the URL.

### Response

```json
{
  "agent": 0.45,
  "accuracy": 0.20,
  "compliance": 0.20,
  "conversation": 0.10,
  "response_time": 0.05
}
```

The values are fractions and add up to 1.0. In the UI they are usually shown as
percentages, so multiply each by 100 to get 45, 20, 20, 10, and 5.

## POST /weights

### Request payload

```json
{
  "agent": 0.50,
  "accuracy": 0.20,
  "compliance": 0.15,
  "conversation": 0.10,
  "response_time": 0.05
}
```

Send fractions, so divide each percent box by 100 before sending. Any unknown or non
numeric keys are ignored by the backend.

### Response

```json
{
  "status": "saved",
  "weights": {
    "agent": 0.50,
    "accuracy": 0.20,
    "compliance": 0.15,
    "conversation": 0.10,
    "response_time": 0.05
  }
}
```

The `weights` object is exactly what was stored, so the frontend can use it to confirm
the save and refresh its boxes.
