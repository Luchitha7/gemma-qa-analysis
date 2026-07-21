"""Small helper to talk to Gemma via the Ollama HTTP API.

Using the API (instead of the `ollama run` command) returns clean plain text
with no terminal/streaming junk. Used by all the QA analysis parts.
"""

import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:1b"


def gemma(prompt, model=MODEL, timeout=180, temperature=0.0, num_predict=320):
    # num_predict caps how many tokens Gemma may generate, so it can't ramble
    # on and waste tokens. Our outputs (summary, scorecard, suggestions) all fit
    # comfortably under this. Lower it to save more; raise it if output is cut.
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
    return data.get("response", "").strip()
