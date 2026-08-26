"""Benchmark one or more local models on the SAME prompt.

Measures wall-clock response time and token throughput so a newer model
(e.g. gemma4:1b, once it's available in Ollama) can be compared against the
current gemma3:1b on a like-for-like basis.

Only models already pulled in Ollama are run. Anything missing is reported and
skipped, so this never invents numbers for a model that isn't installed.

    python compare_models.py                      # default list
    python compare_models.py gemma3:1b gemma4:1b  # explicit list
"""

import json
import os
import sys
import time
import urllib.request

import env_loader

from gemma_client import gemma, reset_token_usage, get_token_usage
from qa_summary import SUMMARY_PROMPT
from sample_call import TRANSCRIPT

DEFAULT_MODELS = [os.environ.get("GEMMA_MODEL", "gemma3:4b")]
RUNS = 3
TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", "http://localhost:11434/api/tags")

def installed_models():
    """Names of models currently pulled in Ollama (empty on any failure)."""
    try:
        with urllib.request.urlopen(TAGS_URL, timeout=10) as resp:
            data = json.loads(resp.read())
        return {m["name"] for m in data.get("models", [])}
    except Exception:
        return set()

def benchmark(model, prompt):
    """Run the prompt RUNS times; return average timing/token stats."""
    times, in_toks, out_toks, sample = [], 0, 0, ""
    for i in range(RUNS):
        reset_token_usage()
        start = time.perf_counter()
        text = gemma(prompt, model=model, label="bench")
        elapsed = time.perf_counter() - start
        usage = get_token_usage()
        times.append(elapsed)
        in_toks += usage["input"]
        out_toks += usage["output"]
        if i == 0:
            sample = text
    avg_time = sum(times) / len(times)
    avg_out = out_toks / RUNS
    return {
        "avg_time": avg_time,
        "avg_in": in_toks / RUNS,
        "avg_out": avg_out,
        "tokens_per_sec": (avg_out / avg_time) if avg_time else 0.0,
        "sample": sample,
    }

if __name__ == "__main__":
    models = sys.argv[1:] or DEFAULT_MODELS
    prompt = SUMMARY_PROMPT.format(
        transcript="\n".join(f"{s}: {t}" for s, t in TRANSCRIPT))

    have = installed_models()
    print(f"\nBenchmarking on the sample call, {RUNS} runs each.")
    print(f"Installed models: {', '.join(sorted(have)) or '(could not read Ollama)'}\n")

    results = {}
    for model in models:
        if have and model not in have:
            print(f"  {model:<14} SKIPPED — not installed "
                  f"(pull it with `ollama pull {model}`)")
            continue
        print(f"  {model:<14} running…", flush=True)
        results[model] = benchmark(model, prompt)

    if not results:
        print("\nNothing to compare — none of the requested models are installed.")
        sys.exit(0)

    print("\n" + "=" * 66)
    print(f"{'MODEL':<14}{'AVG TIME':>10}{'OUT TOKENS':>12}{'TOKENS/SEC':>12}")
    print("-" * 66)
    for model, r in results.items():
        print(f"{model:<14}{r['avg_time']:>9.2f}s{r['avg_out']:>12.0f}"
              f"{r['tokens_per_sec']:>12.1f}")
    print("=" * 66)

    for model, r in results.items():
        print(f"\n--- {model} sample output ---")
        print(r["sample"][:300])
    print()
