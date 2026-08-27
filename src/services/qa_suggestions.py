"""PART (3rd output): Simple suggestions from the call.

One small Gemma request: what the client wanted, and a few follow-up
suggestions. Kept short on purpose.
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

def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)

def clean_suggestions(text):
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines:
        first = lines[0].strip().lower()
        is_bullet = first.startswith(("-", "*", "•"))
        filler = first.endswith(":") or first.startswith(
            ("here", "sure", "based on", "okay", "certainly", "of course")
        )
        if filler and not is_bullet:
            lines.pop(0)
    return "\n".join(lines).strip()

def load_suggestions_prompt():
    prompt_path = os.getenv("PROMPT_SUGGESTIONS_PATH", "resources/prompts/suggestions_prompt.txt")
    full_path = os.path.join(_ROOT, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

SUGGESTIONS_PROMPT = load_suggestions_prompt()
