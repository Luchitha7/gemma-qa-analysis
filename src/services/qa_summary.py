"""PART 2: Gemma writes a plain summary of the whole call.

One small Gemma request -- just the summary, nothing else (keeps tokens low).
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.core.gemma_client import gemma

def load_summary_prompt():
    prompt_path = os.getenv("PROMPT_SUMMARY_PATH", "resources/prompts/summary_prompt.txt")
    full_path = os.path.join(_ROOT, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)

SUMMARY_PROMPT = load_summary_prompt()
