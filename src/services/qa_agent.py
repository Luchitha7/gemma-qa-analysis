"""PART 1: Agent handling analysis + QA scores.

How it works (and why it's built this way):
  - RoBERTa (from qa_intensity) scores sentiment and flags the tense moments.
    Those tense moments are handed to Gemma so it focuses on the heated parts.
  - Gemma judges the AGENT against each QA parameter as PASS / PARTIAL / FAIL
    with a short reason. We only ask it to judge (which it's good at), not to
    output numbers (which it's bad at).
  - Python turns those judgments into scores (PASS=100, PARTIAL=50, FAIL=0),
    so the maths is reliable and repeatable.

Produces three scores (0-100): agent score, conversation score, final QA score.

    python qa_agent.py
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

from src.core.gemma_client import gemma
from src.services.qa_intensity import analyze, INTENSITY_THRESHOLD  # RoBERTa sentiment + intensity
from tests.sample_call import TRANSCRIPT

# ---- The QA parameters (edit these freely) --------------------------------
PARAMETERS = [
    ("Compliance",
     "Did the agent follow proper process and rules, and avoid promising "
     "anything they cannot deliver?"),
    ("Tone and respect",
     "Was the agent polite and respectful throughout, with no scolding, "
     "blaming, or dismissing the client?"),
    ("Responsiveness",
     "Did the agent respond promptly and directly, without dodging questions "
     "or deflecting?"),
    ("Ownership",
     "Did the agent take responsibility for the company's mistake instead of "
     "shifting blame (for example, blaming the client's bank)?"),
    ("Resolution",
     "Did the agent actually resolve the issue and give clear next steps?"),
]

RATING_SCORES = {"PASS": 100, "PARTIAL": 50, "FAIL": 0}

# How the final QA score is weighted between the two sub-scores.
# (Kept for the older agent-only view; the full call score uses FINAL_WEIGHTS.)
AGENT_WEIGHT = 0.7
CONVERSATION_WEIGHT = 0.3

# The full call score blends everything we measure. Answer accuracy and response
# time can be missing (no matched question / no timestamps); when a part is
# missing its weight is dropped and the rest are re-balanced so they still
# add up. Weights sum to 1.0 when everything is present.
FINAL_WEIGHTS = {
    "agent": 0.45,          # how the agent handled the call (Gemma scorecard)
    "accuracy": 0.20,       # did the agent give correct answers (RAG)
    "compliance": 0.20,     # did the agent break any rules (RAG)
    "conversation": 0.10,   # how the customer sounded overall (RoBERTa)
    "response_time": 0.05,  # how fast the agent replied (timestamps)
}


def final_qa_score(agent, conversation, accuracy=None,
                   compliance=None, response_time=None, weights=None):
    """Blend every available sub-score into one 0-100 number.

    Parts that are None (e.g. no timed replies, or no client question matched
    the knowledge base) are left out and the remaining weights re-balanced.

    `weights` lets a caller pass a custom set (e.g. loaded from the frontend
    weights file). When it's None we use FINAL_WEIGHTS, so the behaviour is
    unchanged for any caller that doesn't supply weights.
    """
    weights = weights if weights is not None else FINAL_WEIGHTS
    parts = {
        "agent": agent,
        "accuracy": accuracy,
        "compliance": compliance,
        "conversation": conversation,
        "response_time": response_time,
    }
    available = {k: v for k, v in parts.items() if v is not None}
    total_weight = sum(weights[k] for k in available)
    if not total_weight:
        return 0.0
    blended = sum(v * weights[k] for k, v in available.items())
    return round(blended / total_weight, 1)


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def agent_harsh_lines(rows):
    """Agent's OWN lines that RoBERTa scored as harsh/negative (rude tone)."""
    return [r for r in rows
            if r["speaker"].lower() == "agent"
            and r["sentiment"] <= INTENSITY_THRESHOLD]


def build_prompt(transcript_text, intense_moments, harsh_lines):
    criteria = "\n".join(f"- {name}: {desc}" for name, desc in PARAMETERS)
    moments = "\n".join(
        f"- Turn {m['turn']} ({m['speaker']}): {m['text']}" for m in intense_moments
    ) or "- (none flagged)"
    harsh = "\n".join(
        f"- Turn {m['turn']}: {m['text']}" for m in harsh_lines
    ) or "- (none)"
    example = "\n".join(
        f"{name}: PASS - short reason here" for name, _ in PARAMETERS
    )
    return f"""You are a STRICT call quality auditor. Your job is to catch problems, not to be nice to the agent. Judge ONLY the agent's performance.

How to rate each criterion:
- FAIL if the agent is rude, dismissive, blames the customer, shifts blame, refuses a reasonable request (like a supervisor), pushes an unfair charge, ignores what the customer says, or does not resolve the issue.
- PARTIAL if the agent is mostly okay but slips up, or only partly helps.
- PASS only if the agent is clearly professional AND genuinely helpful AND the issue is resolved.
When in doubt, do NOT give PASS.

Reply with EXACTLY {len(PARAMETERS)} lines, one per criterion, and NOTHING else.
Each line MUST start with the criterion name, then a colon, then one of the
words PASS, PARTIAL, or FAIL in capitals, then a dash and a short reason.

The format must look exactly like this (but with your own rating and reason):
{example}

Criteria to judge:
{criteria}

These moments were flagged as the tense parts of the call - pay special attention to how the agent handled them:
{moments}

These are the agent's OWN lines that sounded harsh or negative - weigh these heavily for Tone and Ownership:
{harsh}

Transcript:
{transcript_text}
"""


def apply_tone_penalty(ratings, harsh_lines):
    """Data-based safety net: if RoBERTa shows the agent's own lines were harsh,
    the Tone rating cannot be a PASS (Gemma alone is too lenient)."""
    if not harsh_lines:
        return ratings
    note = f"RoBERTa flagged {len(harsh_lines)} harsh agent line(s)"
    for r in ratings:
        if r["name"] == "Tone and respect" and r["rating"] == "PASS":
            r["rating"] = "FAIL" if len(harsh_lines) >= 2 else "PARTIAL"
            r["reason"] = f"{r['reason']} [{note}]".strip() if r["reason"] else note
    return ratings


def parse_ratings(reply):
    """Pull a PASS/PARTIAL/FAIL rating + reason for each parameter."""
    results = []
    for name, _ in PARAMETERS:
        rating, reason = None, ""
        # find the line that mentions this criterion
        for line in reply.splitlines():
            if name.lower() in line.lower():
                found = re.search(r"\b(PASS|PARTIAL|FAIL)\b", line, re.IGNORECASE)
                if found:
                    rating = found.group(1).upper()
                    after = line.split(found.group(0), 1)[-1]
                    reason = after.lstrip(" -:").strip()
                    break
        results.append({"name": name, "rating": rating, "reason": reason})
    return results


def conversation_score(rows):
    """0-100 from how the CLIENT sounded overall (RoBERTa sentiment)."""
    client = [r["sentiment"] for r in rows if r["speaker"].lower() == "client"]
    if not client:
        return 50.0
    avg = sum(client) / len(client)          # -1 .. +1
    return round((avg + 1) / 2 * 100, 1)     # 0 .. 100


if __name__ == "__main__":
    transcript_text = format_transcript(TRANSCRIPT)

    print("\nRunning RoBERTa to score sentiment and flag tense moments...")
    rows = analyze(TRANSCRIPT)
    intense = [r for r in rows if r["intense"]]

    harsh = agent_harsh_lines(rows)
    print("Asking Gemma to judge the agent against the QA parameters...\n")
    reply = gemma(build_prompt(transcript_text, intense, harsh))
    ratings = apply_tone_penalty(parse_ratings(reply), harsh)

    print("=" * 78)
    print("PART 1  —  AGENT HANDLING ANALYSIS")
    print("=" * 78)
    print(f"\nTense moments RoBERTa flagged for Gemma: {len(intense)}")
    print("\nAgent scorecard:")
    print("-" * 78)

    rated = []
    for r in ratings:
        rating = r["rating"] or "UNRATED"
        score = RATING_SCORES.get(r["rating"])
        if score is not None:
            rated.append(score)
        shown = f"{score:>3}" if score is not None else "  ?"
        print(f"  {r['name']:<18} {rating:<8} {shown}   {r['reason'][:40]}")

    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = round(agent * AGENT_WEIGHT + conv * CONVERSATION_WEIGHT, 1)

    print("-" * 78)
    print("\nSCORES (0-100):")
    print(f"  Agent score         {agent:>6}   (how well the agent performed)")
    print(f"  Conversation score  {conv:>6}   (how the client sounded overall)")
    print(f"  FINAL QA SCORE      {final:>6}   "
          f"(agent {int(AGENT_WEIGHT*100)}% + conversation {int(CONVERSATION_WEIGHT*100)}%)")
    print()

    print("Gemma's raw reply (for reference):")
    print("-" * 78)
    print(reply)
    print()
