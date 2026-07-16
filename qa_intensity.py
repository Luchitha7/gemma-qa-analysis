"""PART 3 (built first): RoBERTa flags the intense moments in a call.

RoBERTa scores each line's sentiment. We use that to find where the call got
tense/heated (strong negative emotion) so a later step can hand ONLY those
moments to Gemma instead of the whole transcript -- saving tokens.

    python qa_intensity.py
"""

import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import logging
import warnings

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

from transformers import pipeline

from sample_call import TRANSCRIPT

CONFIDENCE_THRESHOLD = 0.6
# A line counts as an "intense moment" when sentiment is strongly negative.
INTENSITY_THRESHOLD = -0.7

classifier = pipeline(
    task="sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    top_k=None,
)


def signed_sentiment(text):
    """Return a score from -1 (negative) to +1 (positive), 0 if unsure."""
    scores = {row["label"]: row["score"] for row in classifier(text)[0]}
    if max(scores.values()) < CONFIDENCE_THRESHOLD:
        return 0.0
    return scores["positive"] - scores["negative"]


def analyze(transcript):
    """Score every line and mark the intense (strongly negative) ones."""
    rows = []
    for i, (speaker, text) in enumerate(transcript, start=1):
        score = signed_sentiment(text)
        intense = score <= INTENSITY_THRESHOLD
        rows.append({
            "turn": i,
            "speaker": speaker,
            "text": text,
            "sentiment": round(score, 2),
            "intense": intense,
        })
    return rows


if __name__ == "__main__":
    rows = analyze(TRANSCRIPT)

    print("\n" + "=" * 84)
    print("FULL CALL  (RoBERTa sentiment per line, intense moments marked with >>)")
    print("=" * 84)
    print(f"{'':2} {'#':>2}  {'score':>6}  {'who':<7} line")
    print("-" * 84)
    for r in rows:
        flag = ">>" if r["intense"] else "  "
        print(f"{flag} {r['turn']:>2}  {r['sentiment']:>6.2f}  {r['speaker']:<7} {r['text'][:52]}")

    intense = [r for r in rows if r["intense"]]

    print("\n" + "=" * 84)
    print(f"INTENSE MOMENTS  ({len(intense)} of {len(rows)} lines)")
    print("=" * 84)
    if not intense:
        print("No strongly negative moments detected.")
    for r in intense:
        print(f"  Turn {r['turn']} ({r['speaker']}, sentiment {r['sentiment']:+.2f}): {r['text']}")

    print()
