"""PART 2: Gemma writes a plain summary of the whole call.

One small Gemma request -- just the summary, nothing else (keeps tokens low).

    python qa_summary.py
"""

from gemma_client import gemma
from sample_call import TRANSCRIPT


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


SUMMARY_PROMPT = """You are a call quality analyst. Read this customer service call transcript and write a short, plain summary of what happened. Keep it to 3-4 sentences. Cover: why the client called, what the agent did, and how it ended. Do not add opinions or scores.

Transcript:
{transcript}
"""


if __name__ == "__main__":
    transcript = format_transcript(TRANSCRIPT)

    print("\n" + "=" * 78)
    print("PART 2  —  CALL SUMMARY (Gemma)")
    print("=" * 78)
    print("\nAsking Gemma to summarize the call...\n")

    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript))
    print(summary)
    print()
