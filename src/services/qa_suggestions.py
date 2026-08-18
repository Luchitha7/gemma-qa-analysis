"""PART (3rd output): Simple suggestions from the call.

One small Gemma request: what the client wanted, and a few follow-up
suggestions. Kept short on purpose.

    python qa_suggestions.py
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
from tests.sample_call import TRANSCRIPT


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def clean_suggestions(text):
    """Drop Gemma's opening filler line (e.g. "Here's a short output...").

    Gemma often starts with a throat-clearing sentence before the real bullets.
    If the first non-empty line looks like that filler (and isn't a bullet or a
    heading), we remove it so the report starts at the useful content.
    """
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


SUGGESTIONS_PROMPT = """You are a call quality analyst. Read this customer service call and give a short, simple output with two parts:

What the client wanted:
- (one or two short bullet points)

Suggestions / follow-ups:
- (two or three short, practical bullet points, for example what to check, what to improve, or what to do next)

Keep it short and plain. No scores, no long paragraphs.

Transcript:
{transcript}
"""


if __name__ == "__main__":
    transcript = format_transcript(TRANSCRIPT)

    print("\n" + "=" * 78)
    print("SUGGESTIONS FROM THE CALL (Gemma)")
    print("=" * 78)
    print("\nAsking Gemma...\n")

    output = clean_suggestions(gemma(SUGGESTIONS_PROMPT.format(transcript=transcript)))
    print(output)
    print()
