"""PART 3 (built first): RoBERTa flags the intense moments in a call.

RoBERTa scores each line's sentiment. We use that to find where the call got
tense/heated (strong negative emotion) so a later step can hand ONLY those
moments to Gemma instead of the whole transcript -- saving tokens.

    python qa_intensity.py
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import logging
import warnings
from dotenv import load_dotenv

load_dotenv()

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

from transformers import pipeline

from tests.sample_call import TRANSCRIPT

CONFIDENCE_THRESHOLD = float(os.getenv("SENTIMENT_CONFIDENCE_THRESHOLD", "0.6"))
INTENSITY_THRESHOLD = float(os.getenv("SENTIMENT_INTENSITY_THRESHOLD", "-0.7"))
SENTIMENT_MODEL = os.getenv("SENTIMENT_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")

classifier = pipeline(
    task="sentiment-analysis",
    model=SENTIMENT_MODEL,
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


