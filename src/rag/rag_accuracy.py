"""Check how ACCURATE the agent's answers were, using the RAG.

For each thing the client says:
  1. Use the RAG to find the closest known question in the knowledge base.
  2. If the match is reliable, take that entry's KEY POINTS (the must-say facts).
  3. Find the agent's next reply and check how many key points it actually covers.

Accuracy for a question = (key points covered / total key points) x 100.
This is more dependable and explainable than comparing whole answers: we can
show exactly which points the agent covered and which they missed.

    python rag_accuracy.py
"""

import os
import sys
import re

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.rag.rag import retrieve, max_similarity
from tests.sample_call import TRANSCRIPT

# A client line must match a known question at least this well to be judged.
RETRIEVAL_THRESHOLD = 0.35
# A key point counts as "covered" if the agent's reply is at least this close
# to it in meaning. We compare each key point against the closest SENTENCE of
# the reply (not the whole reply), so a single point isn't diluted by a long
# answer — this lines the scores up much better with how a human reads them.
KEY_POINT_THRESHOLD = 0.35


def _sentences(text):
    """Split a reply into sentences for point-by-point matching."""
    return [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]


def next_agent_reply(transcript, start):
    """The agent's next line(s) after position `start`, joined (or None).

    We join consecutive agent lines so a two-part answer is judged as a whole.
    """
    parts = []
    for speaker, text in transcript[start + 1:]:
        if speaker.lower() == "agent":
            parts.append(text)
        elif parts:
            break
    return " ".join(parts) if parts else None


def check_accuracy(transcript):
    """Return (per-question results, overall accuracy 0-100 or None)."""
    results = []
    for i, (speaker, text) in enumerate(transcript):
        if speaker.lower() != "client":
            continue

        match = retrieve(text, k=1)[0]
        if match["score"] < RETRIEVAL_THRESHOLD or not match["key_points"]:
            continue  # not a question we have a reliable reference for

        reply = next_agent_reply(transcript, i)
        if reply is None:
            continue

        sentences = _sentences(reply) or [reply]
        covered, missed = [], []
        for point, (score, _idx) in zip(
                match["key_points"],
                max_similarity(match["key_points"], sentences)):
            if score >= KEY_POINT_THRESHOLD:
                covered.append(point)
            else:
                missed.append(point)

        total = len(match["key_points"])
        accuracy = round(len(covered) / total, 3) if total else 0.0
        results.append({
            "client_question": text,
            "matched_question": match["question"],
            "confidence": match["confidence"],
            "ideal_answer": match["ideal_answer"],
            "agent_answer": reply,
            "covered": covered,
            "missed": missed,
            "accuracy": accuracy,          # 0..1
        })

    if not results:
        return results, None
    overall = round(sum(r["accuracy"] for r in results) / len(results) * 100, 1)
    return results, overall


