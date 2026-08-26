"""Small helper to talk to Gemma via the Ollama HTTP API.

Using the API (instead of the `ollama run` command) returns clean plain text
with no terminal/streaming junk. Used by all the QA analysis parts.

Token cost tracking
-------------------
Ollama returns exact token counts on every response: `prompt_eval_count` (the
input tokens it read) and `eval_count` (the output tokens it generated). We
accumulate those here so a caller can measure how many tokens a whole QA report
used. `gemma()` still returns a plain string, so nothing else has to change:
    reset_token_usage()          # before a report
    ... run the Gemma calls ...
    usage = get_token_usage()    # {'input':..., 'output':..., 'total':..., 'calls':[...]}
"""

import json
import os
import urllib.error
import urllib.request

import env_loader  # noqa: F401  (loads .env into os.environ on import)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("GEMMA_MODEL", "gemma3:1b")

# Running tally of tokens used since the last reset.
_usage = {"input": 0, "output": 0, "calls": []}


def reset_token_usage():
    """Clear the token tally (call this before analysing a call)."""
    _usage["input"] = 0
    _usage["output"] = 0
    _usage["calls"] = []


def get_token_usage():
    """Return tokens used since the last reset, with a per-call breakdown."""
    return {
        "input": _usage["input"],
        "output": _usage["output"],
        "total": _usage["input"] + _usage["output"],
        "calls": list(_usage["calls"]),
    }


def gemma(prompt, model=None, timeout=None, temperature=None, num_predict=None,
          label=None):
    # Config comes from the environment (see .env.example) with the same
    # defaults the code used before. An explicit argument still wins, so
    # callers can override per-call.
    # num_predict caps how many tokens Gemma may generate, so it can't ramble
    # on and waste tokens. Our outputs (summary, scorecard, suggestions) all fit
    # comfortably under this. Lower it to save more; raise it if output is cut.
    # `label` is an optional name for this call (e.g. "summary") so the token
    # tally can show which step used what.
    if model is None:
        model = os.environ.get("GEMMA_MODEL", MODEL)
    if timeout is None:
        timeout = int(os.environ.get("GEMMA_TIMEOUT", "180"))
    if temperature is None:
        temperature = float(os.environ.get("GEMMA_TEMPERATURE", "0.0"))
    if num_predict is None:
        num_predict = int(os.environ.get("GEMMA_NUM_PREDICT", "320"))

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        raise SystemExit(
            "Could not reach Ollama. Make sure it's running "
            "('brew services start ollama').\n"
            f"Details: {exc}"
        )

    # Record the exact token counts Ollama reports for this call.
    in_tokens = data.get("prompt_eval_count", 0) or 0
    out_tokens = data.get("eval_count", 0) or 0
    _usage["input"] += in_tokens
    _usage["output"] += out_tokens
    _usage["calls"].append({
        "label": label or "gemma",
        "input": in_tokens,
        "output": out_tokens,
    })

    return data.get("response", "").strip()
