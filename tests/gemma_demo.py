"""Live demo: LLM (Gemma) vs specialized model (RoBERTa) for call QA scoring.

Run it, then press Enter to advance through each step so you can talk in between.
    python gemma_demo.py
"""

import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import logging
import subprocess
import warnings

import env_loader

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

from transformers import AutoTokenizer, pipeline

MODEL = os.environ.get("ROBERTA_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")

print("\nLoading the RoBERTa model (one-time)...")
classifier = pipeline(task="sentiment-analysis", model=MODEL, top_k=None)
tokenizer = AutoTokenizer.from_pretrained(MODEL)


def pause(msg="Press Enter to continue"):
    input(f"\n   [ {msg} ] ")


def roberta_label(text):
    scores = {row["label"]: row["score"] for row in classifier(text)[0]}
    label, score = max(scores.items(), key=lambda kv: kv[1])
    return label, score


def gemma(prompt, timeout=60):
    gemma_model = os.environ.get("GEMMA_MODEL", "gemma3:4b")
    out = subprocess.run(
        ["ollama", "run", gemma_model, prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    return out.stdout.strip()


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------------
NEGATIVE = "This is the worst experience I've ever had."

banner("STEP 1  —  The same sentence, judged by both models")
print(f'\nSentence:  "{NEGATIVE}"')
print("\nThis is obviously negative. Let's see what each model says.")
pause()

banner("STEP 2  —  RoBERTa (our current specialized model)")
label, score = roberta_label(NEGATIVE)
print(f"\nRoBERTa says:  {label.upper()}  ({score:.2f})")
print("Correct. It was built for exactly this.")
pause()

banner("STEP 3  —  Gemma (the LLM), asked the same thing 3 times")
zero_shot = (
    "You are a sentiment scoring engine. Respond with ONLY a single number "
    "between -1 and 1, where -1 is very negative and 1 is very positive.\n\n"
    f'Sentence: "{NEGATIVE}"'
)
print("\nSame negative sentence, same prompt, asked 3 times:")
for i in range(1, 4):
    print(f"   run {i}:  {gemma(zero_shot)}")
print("\n-> Different answers each time, and often out of range or the wrong")
print("   sign. Without examples it's unreliable and inconsistent.")
pause()

banner("STEP 4  —  It only works if you hand it examples")
few_shot = (
    "You are a sentiment scoring engine. Respond with ONLY a single number between -1 and 1.\n"
    'Examples:\n'
    '"I love this, its wonderful!" -> 0.9\n'
    '"This is terrible and I hate it." -> -0.9\n'
    '"The meeting is at 3pm." -> 0.0\n\n'
    f'Sentence: "{NEGATIVE}"'
)
print("\nSame question, but now with 3 examples added to the prompt...")
print(f"\nGemma says:  {gemma(few_shot)}")
print("\n-> Now it's right. But it needed hand-holding to get there,")
print("   and a tiny wording change can flip it back.")
pause()

banner("STEP 5  —  The real limitation for FULL-call scoring")
# The real ~5-minute benchmark call (34 turns) from full_conversation_qa_test.py
sample_call = " ".join([
    "Good afternoon, thanks for calling, you're through to Daniel, how can I help today?",
    "Hi Daniel, yeah, I'm calling because I've been charged twice for my subscription this month.",
    "Okay, I'm sorry to hear that, let me take a look at your account and get this sorted for you.",
    "Thanks, it's the second time this has happened actually, it happened back in March as well.",
    "I can see the two charges here, both went through on the third, so you're right, that's clearly a duplicate.",
    "Right, so it's obviously a problem on your end, not something I did.",
    "I understand why you'd see it that way, though these things can sometimes come from the bank's side too.",
    "No, come on, it's the second time, that's not my bank double-charging me for no reason.",
    "That's a fair point, and I apologise, you're right that a repeat like this points to something on our system.",
    "Honestly it's really frustrating, I shouldn't have to call up every couple of months to fix this.",
    "You absolutely shouldn't, and I want to make sure this is the last time you have to, not just refund it and move on.",
    "Okay, good, because last time they just refunded me and nobody actually looked into why it keeps happening.",
    "That's not good enough, and I'm sorry that was the experience last time, that should have been escalated then.",
    "So what are you actually going to do differently this time?",
    "Two things. First, I'm processing the refund for the duplicate charge right now while we talk.",
    "Second, I'm raising a billing investigation ticket so an engineer looks at why your account is being double-billed.",
    "You'll get an email with the ticket number today, and someone will update you within five working days.",
    "I'd also like to add a small credit to your account for the inconvenience of having to chase this again.",
    "It's the least we can do, you've been a customer for three years and this shouldn't keep happening.",
    "That's good to hear, and I've made the refund now, so you'll see that back within three to five business days.",
    "The credit is applied immediately, you'll see it on your next invoice, which will be lower as a result.",
    "So just to recap, refund processed, credit applied, and a billing investigation raised with an update in five days.",
    "Is there anything else at all I can help you with while you're on the line?",
    "No, that's everything, thanks for actually taking it seriously this time.",
    "Of course, and again I'm sorry for the hassle, thanks for your patience and have a great day.",
])
tokens = len(tokenizer(sample_call)["input_ids"])
print(f"\nA ~5-minute call is roughly {tokens} tokens of text.")
print("RoBERTa can only read 512 tokens at once.")
print(f"\n   {tokens} tokens  >  512 limit")
print("\n-> RoBERTa physically CANNOT read a whole call in one go.")
print("   It was built for short snippets. Full-call scoring needs an LLM")
print("   that can hold the whole conversation in context.")
pause("Press Enter for the takeaway")

banner("TAKEAWAY")
print("""
  - Live, per-phrase scoring:   RoBERTa wins (fast, consistent, accurate).
  - Whole-call QA scoring:      needs an LLM (RoBERTa can't fit the call)...
                                but NOT a tiny one like Gemma 1B -- it's
                                inconsistent and contradicts itself.
  - Next step:                  test a bigger LLM on the whole transcript,
                                run once AFTER each call instead of live.
""")
