"""PART (3rd output): Simple suggestions from the call.

One small Gemma request: what the client wanted, and a few follow-up
suggestions. Kept short on purpose.

    python qa_suggestions.py
"""

from gemma_client import gemma
from sample_call import TRANSCRIPT


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


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

    output = gemma(SUGGESTIONS_PROMPT.format(transcript=transcript))
    print(output)
    print()
