"""Full-conversation QA scoring test.

Goals (from the QA research brief):
  - Use a representative ~5-minute employee/client conversation as the benchmark.
  - Quantify its text volume (words / tokens) to establish input-size constraints.
  - Compare two scoring approaches:
      A) line-by-line sentiment averaging (what the live app does today)
      B) whole-transcript-at-once holistic QA scoring (what an LLM can do that
         a 512-token classifier like RoBERTa cannot do in a single pass)
"""

import re
import subprocess

from transformers import AutoTokenizer, pipeline

MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
classifier = pipeline(task="sentiment-analysis", model=MODEL, top_k=None)
tokenizer = AutoTokenizer.from_pretrained(MODEL)

CONFIDENCE_THRESHOLD = 0.6

# A representative ~5-minute support/account call between an employee (agent)
# and a client. Deliberately mixed for QA purposes: the agent does some things
# well (empathy, ownership, clear next steps) and some things poorly (a defensive
# moment, a policy dodge), so there is something real to score.
TRANSCRIPT = [
    ("Agent", "Good afternoon, thanks for calling, you're through to Daniel, how can I help today?"),
    ("Client", "Hi Daniel, yeah, I'm calling because I've been charged twice for my subscription this month."),
    ("Agent", "Okay, I'm sorry to hear that, let me take a look at your account and get this sorted for you."),
    ("Client", "Thanks, it's the second time this has happened actually, it happened back in March as well."),
    ("Agent", "I can see the two charges here, both went through on the third, so you're right, that's clearly a duplicate."),
    ("Client", "Right, so it's obviously a problem on your end, not something I did."),
    ("Agent", "I understand why you'd see it that way, though these things can sometimes come from the bank's side too."),
    ("Client", "No, come on, it's the second time, that's not my bank double-charging me for no reason."),
    ("Agent", "That's a fair point, and I apologise, you're right that a repeat like this points to something on our system."),
    ("Client", "Honestly it's really frustrating, I shouldn't have to call up every couple of months to fix this."),
    ("Agent", "You absolutely shouldn't, and I want to make sure this is the last time you have to, not just refund it and move on."),
    ("Client", "Okay, good, because last time they just refunded me and nobody actually looked into why it keeps happening."),
    ("Agent", "That's not good enough, and I'm sorry that was the experience last time, that should have been escalated then."),
    ("Client", "So what are you actually going to do differently this time?"),
    ("Agent", "Two things. First, I'm processing the refund for the duplicate charge right now while we talk."),
    ("Client", "Okay."),
    ("Agent", "Second, I'm raising a billing investigation ticket so an engineer looks at why your account is being double-billed."),
    ("Client", "And will I actually hear back about that, or does it just disappear into a queue somewhere?"),
    ("Agent", "You'll get an email with the ticket number today, and I'm adding a note to have someone update you within five working days."),
    ("Client", "Alright, that's better than last time at least."),
    ("Agent", "I'd also like to add a small credit to your account for the inconvenience of having to chase this again."),
    ("Client", "Oh, okay, I wasn't expecting that, thank you, that's decent of you."),
    ("Agent", "It's the least we can do, you've been a customer for three years and this shouldn't keep happening."),
    ("Client", "Yeah, I've mostly been happy with the service, this billing thing is really the only issue."),
    ("Agent", "That's good to hear, and I've made the refund now, so you'll see that back within three to five business days."),
    ("Client", "Great, and the credit?"),
    ("Agent", "The credit is applied immediately, you'll see it on your next invoice, which will be lower as a result."),
    ("Client", "Perfect, okay, I think that covers everything I called about."),
    ("Agent", "Wonderful, so just to recap, refund processed, credit applied, and a billing investigation raised with an update in five days."),
    ("Client", "Yep, that all sounds right."),
    ("Agent", "Is there anything else at all I can help you with while you're on the line?"),
    ("Client", "No, that's everything, thanks for actually taking it seriously this time."),
    ("Agent", "Of course, and again I'm sorry for the hassle, thanks for your patience and have a great rest of your day."),
    ("Client", "You too, bye."),
]

GEMMA_LINE_PROMPT = """You are a sentiment scoring engine. Respond with ONLY a single number between -1 and 1.
Examples:
"I love this, its wonderful!" -> 0.9
"This is terrible and I hate it." -> -0.9
"The meeting is at 3pm." -> 0.0

Sentence: "{line}\""""


def roberta_score(text):
    scores = {row["label"]: row["score"] for row in classifier(text)[0]}
    if max(scores.values()) < CONFIDENCE_THRESHOLD:
        return 0.0
    return scores["positive"] - scores["negative"]


def gemma(prompt, timeout=120):
    result = subprocess.run(
        ["ollama", "run", "gemma3:4b", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def gemma_line_score(text):
    raw = gemma(GEMMA_LINE_PROMPT.format(line=text))
    first = raw.splitlines()[0].strip() if raw else ""
    m = re.search(r"-?\d+\.?\d*", first)
    return (float(m.group()), raw) if m else (None, raw)


# ---------------------------------------------------------------------------
# 1. Quantify text volume
# ---------------------------------------------------------------------------
full_text = "\n".join(f"{speaker}: {line}" for speaker, line in TRANSCRIPT)
words = full_text.split()
word_count = len(words)
char_count = len(full_text)
token_ids = tokenizer(full_text)["input_ids"]
token_count = len(token_ids)

# ~130 words/min is a normal conversational speaking pace
est_minutes = word_count / 130

print("=" * 78)
print("TEXT VOLUME")
print("=" * 78)
print(f"Turns:                       {len(TRANSCRIPT)}")
print(f"Words:                       {word_count}")
print(f"Characters:                  {char_count}")
print(f"Tokens (RoBERTa tokenizer):  {token_count}")
print(f"Estimated spoken duration:   ~{est_minutes:.1f} min (at ~130 wpm)")
print(f"RoBERTa max input:           512 tokens  ->  transcript "
      f"{'EXCEEDS' if token_count > 512 else 'fits within'} it")
print()

# ---------------------------------------------------------------------------
# 2. Approach A: line-by-line
# ---------------------------------------------------------------------------
print("=" * 78)
print("APPROACH A: LINE-BY-LINE")
print("=" * 78)
print(f"{'#':<3} {'RoBERTa':>8} {'Gemma':>8}   Speaker  Line")
print("-" * 78)

roberta_scores, gemma_scores = [], []
for i, (speaker, line) in enumerate(TRANSCRIPT, start=1):
    r = roberta_score(line)
    g, _ = gemma_line_score(line)
    roberta_scores.append(r)
    if g is not None:
        gemma_scores.append(g)
    g_disp = f"{g:.2f}" if g is not None else "  ?"
    print(f"{i:<3} {r:>8.2f} {g_disp:>8}   {speaker:<7}  {line[:60]}")

roberta_avg = sum(roberta_scores) / len(roberta_scores)
gemma_avg = sum(gemma_scores) / len(gemma_scores) if gemma_scores else float("nan")
print("-" * 78)
print(f"RoBERTa line-by-line avg sentiment: {roberta_avg:+.3f}")
print(f"Gemma   line-by-line avg sentiment: {gemma_avg:+.3f} "
      f"({len(gemma_scores)}/{len(TRANSCRIPT)} parsed)")
print()

# ---------------------------------------------------------------------------
# 3. Approach B: whole transcript at once (only the LLM can do this in one pass)
# ---------------------------------------------------------------------------
print("=" * 78)
print("APPROACH B: WHOLE TRANSCRIPT AT ONCE (Gemma)")
print("=" * 78)

holistic_prompt = f"""You are a call quality analyst. Read this entire customer service call transcript and rate the overall sentiment/quality of the interaction on a scale from -1 (very negative call) to +1 (very positive call). Respond with the number on the first line, then one short sentence explaining why.

Transcript:
{full_text}
"""
holistic = gemma(holistic_prompt, timeout=180)
print(holistic)
print()
print("Note: RoBERTa cannot produce a single whole-call score in one pass — the")
print(f"transcript is {token_count} tokens and RoBERTa truncates at 512, so a")
print("specialized classifier must chunk + average, it can't reason over the whole call.")
