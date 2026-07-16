"""ONE-COMMAND FULL QA REPORT.

Runs every part and prints a single report for a call:
  - RoBERTa: sentiment + tense moments  (qa_intensity)
  - Gemma:   summary                    (qa_summary)
  - Gemma:   agent scorecard            (qa_agent)
  - Gemma:   suggestions                (qa_suggestions)
  - Scores:  agent + conversation + final QA

    python qa_report.py
"""

from gemma_client import gemma
from qa_intensity import analyze
from qa_agent import (
    AGENT_WEIGHT, CONVERSATION_WEIGHT, PARAMETERS, RATING_SCORES,
    build_prompt, conversation_score, parse_ratings,
)
from qa_summary import SUMMARY_PROMPT
from qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions
from sample_call import TRANSCRIPT


def format_transcript(transcript):
    return "\n".join(f"{speaker}: {text}" for speaker, text in transcript)


def band(score):
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "OKAY"
    return "NEEDS IMPROVEMENT"


def rule(char="="):
    print(char * 78)


if __name__ == "__main__":
    transcript_text = format_transcript(TRANSCRIPT)

    print("\nGenerating QA report (RoBERTa + Gemma)...\n")

    # --- RoBERTa: sentiment + tense moments ---
    rows = analyze(TRANSCRIPT)
    intense = [r for r in rows if r["intense"]]

    # --- Gemma: three separate small calls ---
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text))
    ratings = parse_ratings(gemma(build_prompt(transcript_text, intense)))
    suggestions = clean_suggestions(gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text)))

    # --- Scores ---
    rated = [RATING_SCORES[r["rating"]] for r in ratings if r["rating"]]
    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = round(agent * AGENT_WEIGHT + conv * CONVERSATION_WEIGHT, 1)

    # ================= REPORT =================
    print()
    rule()
    print("                      CALL QA REPORT")
    rule()

    print(f"\n  FINAL QA SCORE:  {final} / 100   ({band(final)})")
    print(f"    Agent score .......... {agent} / 100")
    print(f"    Conversation score ... {conv} / 100")

    print("\n")
    rule("-")
    print("  SUMMARY")
    rule("-")
    print(f"  {summary}")

    print("\n")
    rule("-")
    print("  AGENT SCORECARD")
    rule("-")
    for r in ratings:
        rating = r["rating"] or "UNRATED"
        print(f"  {r['name']:<18} {rating:<8}  {r['reason'][:44]}")

    print("\n")
    rule("-")
    print(f"  TENSE MOMENTS  ({len(intense)} flagged by RoBERTa)")
    rule("-")
    if not intense:
        print("  None - the call stayed calm.")
    for r in intense:
        print(f"  Turn {r['turn']} ({r['speaker']}, {r['sentiment']:+.2f}): {r['text']}")

    print("\n")
    rule("-")
    print("  SUGGESTIONS")
    rule("-")
    print(f"  {suggestions}")
    print()
    rule()
    print()
