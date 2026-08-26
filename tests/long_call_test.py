import os
import re
import subprocess

import env_loader

from transformers import pipeline

MODEL = os.environ.get("ROBERTA_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")

classifier = pipeline(
    task="sentiment-analysis",
    model=MODEL,
    top_k=None,
)

CONFIDENCE_THRESHOLD = 0.6

# Same placeholder weights used in app.py / call_score_test.py
KEYWORD_WEIGHTS = {
    "cancel": -0.7,
    "complaint": -0.6,
    "refund": -0.5,
    "angry": -0.5,
    "frustrated": -0.4,
    "upset": -0.4,
    "manager": -0.3,
    "urgent": -0.2,
    "sad": -0.2,
    "happy": 0.5,
}
KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in KEYWORD_WEIGHTS) + r")\b",
    re.IGNORECASE,
)

GEMMA_PROMPT_TEMPLATE = """You are a sentiment scoring engine. Respond with ONLY a single number between -1 and 1.
Examples:
"I love this, its wonderful!" -> 0.9
"This is terrible and I hate it." -> -0.9
"The meeting is at 3pm." -> 0.0

Sentence: "{line}\""""

# A longer fake call transcript, roughly the length/shape of a real support
# call: friendly opening, a problem surfaces, frustration builds, then a
# resolution and friendly close.
CALL = [
    "Hi, thanks for calling support, how can I help you today?",
    "Hey, I'm having trouble with my recent order, it hasn't arrived yet.",
    "I'm sorry to hear that, let me pull up your order details.",
    "Thanks, I ordered it two weeks ago and it was supposed to arrive last Friday.",
    "I can see the delay here, it looks like it's stuck at the shipping depot.",
    "This is really frustrating, I needed it for an event that already happened.",
    "I completely understand, that's not the experience we want for you.",
    "Can you just refund me at this point? I don't even want it anymore.",
    "I've already emailed twice this week and nobody got back to me.",
    "I want to cancel this order and speak to a manager if possible.",
    "I'm going to escalate this and process a full refund right now.",
    "Okay, I'm going to go ahead and issue that refund for you.",
    "You'll see it back in your account within three to five business days.",
    "Okay, thank you, I appreciate you sorting this out quickly.",
    "I'm sorry again for the trouble, is there anything else I can help with?",
    "No that's all, thanks for your help.",
    "Have a great day, and thanks for your patience.",
]


def roberta_score(text):
    scores = {row["label"]: row["score"] for row in classifier(text)[0]}
    if max(scores.values()) < CONFIDENCE_THRESHOLD:
        return 0.0
    return scores["positive"] - scores["negative"]


def gemma_score(text):
    gemma_model = os.environ.get("GEMMA_MODEL", "gemma3:4b")
    prompt = GEMMA_PROMPT_TEMPLATE.format(line=text)
    result = subprocess.run(
        ["ollama", "run", gemma_model, prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    raw = result.stdout.strip()
    first_line = raw.splitlines()[0].strip() if raw else ""
    try:
        return float(first_line), raw
    except ValueError:
        return None, raw


def keyword_impact_for(text):
    return sum(
        KEYWORD_WEIGHTS[match.lower()] for match in KEYWORD_PATTERN.findall(text)
    )


print(f"{'#':<3} {'RoBERTa':>8} {'Gemma':>8}   Line")
print("-" * 90)

roberta_scores = []
gemma_scores = []
total_keyword_impact = 0.0

for i, line in enumerate(CALL, start=1):
    r_score = roberta_score(line)
    g_score, g_raw = gemma_score(line)
    total_keyword_impact += keyword_impact_for(line)

    roberta_scores.append(r_score)
    if g_score is not None:
        gemma_scores.append(g_score)

    g_display = f"{g_score:.2f}" if g_score is not None else f"?({g_raw[:20]})"
    print(f"{i:<3} {r_score:>8.2f} {g_display:>8}   {line}")

roberta_avg = sum(roberta_scores) / len(roberta_scores)
gemma_avg = sum(gemma_scores) / len(gemma_scores) if gemma_scores else float("nan")

roberta_combined = max(-1.0, min(1.0, roberta_avg + total_keyword_impact))

print("-" * 90)
print(f"RoBERTa avg sentiment (filtered):        {roberta_avg:.3f}")
print(f"Keyword impact:                          {total_keyword_impact:.3f}")
print(f"RoBERTa overall call score (w/ keywords): {roberta_combined * 100:.1f}%")
print()
print(f"Gemma avg sentiment ({len(gemma_scores)}/{len(CALL)} lines parsed): {gemma_avg:.3f}")
