"""PART (3rd output): Simple suggestions from the call.

One small Gemma request: what the client wanted, and a few follow-up
suggestions. Kept short on purpose.

    python qa_suggestions.py
"""

import re

from gemma_client import gemma
from sample_call import TRANSCRIPT


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


def suggestions_to_list(text):
    """Turn the cleaned suggestions text into a flat list of point strings.

    The frontend shows suggestions as separate numbered items, so we split the
    text into individual points: heading lines (ending in ':') are dropped, and
    bullet/number markers are stripped off the front of each point.
    """
    items = []
    for line in text.splitlines():
        s = line.replace("**", "").replace("__", "").strip()   # drop markdown bold
        s = s.lstrip("-*•").strip()          # bullet marker
        s = re.sub(r"^\d+[.)]\s*", "", s)    # leading "1." / "1)"
        if not s or s.endswith(":"):         # blank line or a heading
            continue
        items.append(s)
    return items


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
