"""PART 1: Agent handling analysis + QA scores."""

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
from src.services.qa_intensity import analyze, INTENSITY_THRESHOLD

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

def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)

def agent_harsh_lines(rows):
    return [r for r in rows
            if r["speaker"].lower() == "agent"
            and r["sentiment"] <= INTENSITY_THRESHOLD]

def load_scorecard_prompt():
    prompt_path = os.getenv("PROMPT_SCORECARD_PATH", "resources/prompts/scorecard_prompt.txt")
    full_path = os.path.join(_ROOT, prompt_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

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
    
    prompt_template = load_scorecard_prompt()
    return prompt_template.format(
        parameter_count=len(PARAMETERS),
        example=example,
        criteria=criteria,
        moments=moments,
        harsh=harsh,
        transcript_text=transcript_text
    )

def apply_tone_penalty(ratings, harsh_lines):
    if not harsh_lines:
        return ratings
    note = f"RoBERTa flagged {len(harsh_lines)} harsh agent line(s)"
    for r in ratings:
        if r["name"] == "Tone and respect" and r["rating"] == "PASS":
            r["rating"] = "FAIL" if len(harsh_lines) >= 2 else "PARTIAL"
            r["reason"] = f"{r['reason']} [{note}]".strip() if r["reason"] else note
    return ratings

def parse_ratings(reply):
    results = []
    for name, _ in PARAMETERS:
        rating, reason = None, ""
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
    client = [r["sentiment"] for r in rows if r["speaker"].lower() == "client"]
    if not client:
        return 50.0
    avg = sum(client) / len(client)
    return round((avg + 1) / 2 * 100, 1)

def final_qa_score(agent, conversation, accuracy=None, compliance=None, response_time=None, weights=None):
    if weights is None:
        weights = {"agent": 0.45, "accuracy": 0.20, "compliance": 0.20, "conversation": 0.10, "response_time": 0.05}
    parts = {
        "agent": agent, "accuracy": accuracy, "compliance": compliance,
        "conversation": conversation, "response_time": response_time,
    }
    available = {k: v for k, v in parts.items() if v is not None}
    total_weight = sum(weights[k] for k in available)
    if not total_weight:
        return 0.0
    blended = sum(v * weights[k] for k, v in available.items())
    return round(blended / total_weight, 1)
