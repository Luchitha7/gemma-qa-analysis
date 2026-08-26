"""Experiment: can Gemma replace RoBERTa for the sentiment side?

RoBERTa currently drives four things in the pipeline:
  1. the conversation sub-score (average client sentiment),
  2. the "intense moment" flags (lines <= INTENSITY_THRESHOLD),
  3. the agent's harsh lines (used in the scorecard prompt),
  4. the tone-penalty safety net (downgrades a lenient Gemma Tone PASS).

To drop RoBERTa, Gemma has to produce per-line sentiment that agrees with
RoBERTa closely enough to drive those same four things. This script measures
that agreement instead of guessing.

What it does:
  - Runs RoBERTa on each transcript (the current source of truth).
  - Asks Gemma for a sentiment score per line on the SAME -1..+1 scale, in one
    call, and parses it back.
  - Feeds BOTH score sets through the same downstream functions and compares:
      * per-line scores (mean abs error, correlation),
      * the conversation sub-score,
      * which lines are flagged "intense" (agreement / precision / recall),
      * which agent lines are flagged "harsh".

    python sentiment_compare.py

Read the verdict block at the end. High agreement => Gemma can likely take over.
Low agreement (especially on intense / harsh detection) => keep RoBERTa.
"""

import re

from qa_intensity import analyze, INTENSITY_THRESHOLD, CONFIDENCE_THRESHOLD
from qa_agent import conversation_score, agent_harsh_lines
from gemma_client import gemma
from sample_call import TRANSCRIPT


# A couple of short, deliberately tense calls so the negative side is exercised
# (the main sample is mostly civil). A rude agent and an angry client.
RUDE_AGENT = [
    ("Client", "Hi, I was charged twice and I'd like it refunded please."),
    ("Agent", "Well that's probably your bank's fault, not ours."),
    ("Client", "It's clearly a double charge on your side, look at the account."),
    ("Agent", "I don't have time to argue about this, it is what it is."),
    ("Client", "That is incredibly rude, I just want it fixed."),
    ("Agent", "Fine. Whatever. I'll refund it, but stop wasting my time."),
    ("Client", "Unbelievable. I want to speak to a supervisor."),
    ("Agent", "There's no supervisor available. Anything else or are we done?"),
]

ANGRY_CLIENT = [
    ("Agent", "Good morning, thanks for calling support, how can I help?"),
    ("Client", "This is the fourth time I've called about the same broken router!"),
    ("Agent", "I'm really sorry, let me pull up your account and take a look."),
    ("Client", "I am sick of this, absolutely furious, nothing ever gets fixed."),
    ("Agent", "I completely understand, and I'm going to get this sorted today."),
    ("Client", "You people always say that and then nothing happens."),
    ("Agent", "I've booked an engineer for tomorrow morning and added a credit."),
    ("Client", "Fine. That's something at least. Thank you."),
]

TRANSCRIPTS = [
    ("main sample (mixed, mostly civil)", TRANSCRIPT),
    ("rude agent", RUDE_AGENT),
    ("angry client", ANGRY_CLIENT),
]


SENTIMENT_PROMPT = """You are a sentiment rater. For each numbered line of a
customer-support call, rate the SPEAKER's emotional sentiment in that line on a
scale from -1.0 to 1.0, where:
  -1.0 = very negative / angry / rude / upset
   0.0 = neutral / factual
   1.0 = very positive / warm / satisfied

Reply with EXACTLY one line per input line and NOTHING else, in the form:
<number>: <score>
For example:
1: 0.2
2: -0.8

Lines to rate:
{lines}
"""


def gemma_sentiment(transcript):
    """Ask Gemma for a -1..+1 sentiment per line; return rows like analyze()."""
    numbered = "\n".join(
        f"{i}. {speaker}: {text}" for i, (speaker, text) in enumerate(transcript, 1)
    )
    reply = gemma(SENTIMENT_PROMPT.format(lines=numbered),
                  num_predict=600, label="sentiment")

    scores = {}
    for line in reply.splitlines():
        m = re.match(r"\s*(\d+)\s*[:.)-]\s*(-?\d+(?:\.\d+)?)", line)
        if m:
            n = int(m.group(1))
            val = max(-1.0, min(1.0, float(m.group(2))))
            scores[n] = val

    rows = []
    for i, (speaker, text) in enumerate(transcript, 1):
        score = round(scores.get(i, 0.0), 2)
        rows.append({
            "turn": i, "speaker": speaker, "text": text,
            "sentiment": score, "intense": score <= INTENSITY_THRESHOLD,
        })
    return rows, len(scores)


def pearson(xs, ys):
    """Correlation coefficient, computed by hand to avoid a numpy dependency."""
    n = len(xs)
    if n == 0:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def prf(reference_set, predicted_set):
    """Precision/recall/F1 of predicted vs reference (both are sets of turns)."""
    tp = len(reference_set & predicted_set)
    fp = len(predicted_set - reference_set)
    fn = len(reference_set - predicted_set)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return precision, recall, f1, tp, fp, fn


def compare_one(name, transcript):
    print("\n" + "=" * 84)
    print(f"TRANSCRIPT: {name}   ({len(transcript)} lines)")
    print("=" * 84)

    rob = analyze(transcript)
    gem, parsed = gemma_sentiment(transcript)
    if parsed < len(transcript):
        print(f"  ! Gemma returned {parsed}/{len(transcript)} scored lines; "
              f"missing ones treated as 0.0")

    # ---- per-line table ----
    print(f"\n{'#':>2} {'who':<7} {'RoB':>6} {'Gem':>6} {'diff':>6}  line")
    print("-" * 84)
    abs_errs = []
    for r, g in zip(rob, gem):
        diff = abs(r["sentiment"] - g["sentiment"])
        abs_errs.append(diff)
        flag = ""
        if r["intense"] != g["intense"]:
            flag = "  <-- intense disagreement"
        print(f"{r['turn']:>2} {r['speaker']:<7} {r['sentiment']:>6.2f} "
              f"{g['sentiment']:>6.2f} {diff:>6.2f}  {r['text'][:40]}{flag}")

    # ---- metrics ----
    mae = sum(abs_errs) / len(abs_errs)
    corr = pearson([r["sentiment"] for r in rob], [g["sentiment"] for g in gem])

    conv_rob = conversation_score(rob)
    conv_gem = conversation_score(gem)

    rob_intense = {r["turn"] for r in rob if r["intense"]}
    gem_intense = {g["turn"] for g in gem if g["intense"]}
    p, rc, f1, tp, fp, fn = prf(rob_intense, gem_intense)

    rob_harsh = {r["turn"] for r in agent_harsh_lines(rob)}
    gem_harsh = {g["turn"] for g in agent_harsh_lines(gem)}
    hp, hr, hf1, htp, hfp, hfn = prf(rob_harsh, gem_harsh)

    print("-" * 84)
    print(f"  Per-line mean abs error : {mae:.2f}   (0 = identical, 2 = opposite ends)")
    print(f"  Per-line correlation    : {corr:+.2f}  (+1 = perfect agreement)")
    print(f"  Conversation sub-score  : RoBERTa {conv_rob:.1f}  vs  Gemma {conv_gem:.1f}"
          f"   (diff {abs(conv_rob - conv_gem):.1f})")
    print(f"  Intense moments         : RoBERTa {sorted(rob_intense)}  "
          f"vs Gemma {sorted(gem_intense)}")
    print(f"                            precision {p:.2f} recall {rc:.2f} F1 {f1:.2f}"
          f"  (tp {tp} fp {fp} fn {fn})")
    print(f"  Harsh AGENT lines       : RoBERTa {sorted(rob_harsh)}  "
          f"vs Gemma {sorted(gem_harsh)}")
    print(f"                            precision {hp:.2f} recall {hr:.2f} F1 {hf1:.2f}"
          f"  (tp {htp} fp {hfp} fn {hfn})")

    return {
        "name": name, "mae": mae, "corr": corr,
        "conv_diff": abs(conv_rob - conv_gem),
        "intense_f1": f1, "harsh_f1": hf1,
        "rob_intense": len(rob_intense), "gem_intense": len(gem_intense),
        "rob_harsh": len(rob_harsh), "gem_harsh": len(gem_harsh),
    }


def main():
    print("Comparing RoBERTa vs Gemma for per-line sentiment.")
    print(f"(intense threshold = {INTENSITY_THRESHOLD}, "
          f"RoBERTa confidence floor = {CONFIDENCE_THRESHOLD})")

    results = [compare_one(name, t) for name, t in TRANSCRIPTS]

    print("\n" + "=" * 84)
    print("SUMMARY  (averaged where it makes sense)")
    print("=" * 84)
    print(f"{'transcript':<34} {'MAE':>5} {'corr':>6} {'convΔ':>6} "
          f"{'intF1':>6} {'harshF1':>8}")
    print("-" * 84)
    for r in results:
        print(f"{r['name']:<34} {r['mae']:>5.2f} {r['corr']:>+6.2f} "
              f"{r['conv_diff']:>6.1f} {r['intense_f1']:>6.2f} {r['harsh_f1']:>8.2f}")

    avg_mae = sum(r["mae"] for r in results) / len(results)
    avg_corr = sum(r["corr"] for r in results) / len(results)
    avg_conv = sum(r["conv_diff"] for r in results) / len(results)
    avg_intf1 = sum(r["intense_f1"] for r in results) / len(results)
    avg_harshf1 = sum(r["harsh_f1"] for r in results) / len(results)
    print("-" * 84)
    print(f"{'AVERAGE':<34} {avg_mae:>5.2f} {avg_corr:>+6.2f} "
          f"{avg_conv:>6.1f} {avg_intf1:>6.2f} {avg_harshf1:>8.2f}")

    print("\nHow to read this:")
    print("  - convΔ is on a 0-100 scale; under ~5 means the sub-score barely moves.")
    print("  - intF1 / harshF1 are the ones that matter most: they show whether")
    print("    Gemma flags the SAME tense/harsh lines RoBERTa does. Low F1 here")
    print("    means the tone-penalty safety net would fire differently.")
    print("  - A 1B model is small; treat correlation and F1, not one nice line, as")
    print("    the signal.")


if __name__ == "__main__":
    main()
