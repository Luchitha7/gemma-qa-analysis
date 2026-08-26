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

import env_loader

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("GEMMA_MODEL", "gemma3:4b")

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
    except urllib.error.HTTPError as exc:
        err_msg = f"Ollama HTTP error ({exc.code}): {exc.reason}."
        if exc.code == 404:
            err_msg += f" Model '{model}' not found in Ollama. Pull it with: `ollama pull {model}`."
        raise RuntimeError(err_msg)
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {OLLAMA_URL}. Make sure Ollama is running.\n"
            f"Details: {exc}"
        )

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
