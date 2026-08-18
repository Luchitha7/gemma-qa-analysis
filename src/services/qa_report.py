"""ONE-COMMAND FULL QA REPORT.

Runs every part and prints a single report for a call:
  - RoBERTa: sentiment + tense moments  (qa_intensity)
  - Gemma:   summary                    (qa_summary)
  - Gemma:   agent scorecard            (qa_agent)
  - Gemma:   suggestions                (qa_suggestions)
  - Scores:  agent + conversation + final QA

    python qa_report.py
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.core.gemma_client import gemma, reset_token_usage, get_token_usage
from src.services.qa_intensity import analyze
from src.services.qa_agent import (
    PARAMETERS, RATING_SCORES, agent_harsh_lines, apply_tone_penalty,
    build_prompt, conversation_score, final_qa_score, parse_ratings,
)
from src.services.qa_summary import SUMMARY_PROMPT
from src.services.qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions
from src.rag.rag_accuracy import check_accuracy
from src.rag.rag_compliance import check_compliance
from tests.sample_call import TRANSCRIPT


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

    # --- Gemma: three separate small calls (with token tracking) ---
    reset_token_usage()
    harsh = agent_harsh_lines(rows)
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text),
                    label="summary")
    ratings = apply_tone_penalty(
        parse_ratings(gemma(build_prompt(transcript_text, intense, harsh),
                            label="scorecard")), harsh)
    suggestions = clean_suggestions(
        gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text),
              label="suggestions"))
    token_usage = get_token_usage()

    # --- RAG (token-free): answer accuracy + compliance ---
    accuracy_results, accuracy_overall = check_accuracy(TRANSCRIPT)
    compliance_results, compliance_score = check_compliance(TRANSCRIPT)

    # --- Scores ---
    rated = [RATING_SCORES[r["rating"]] for r in ratings if r["rating"]]
    agent = round(sum(rated) / len(rated), 1) if rated else 0.0
    conv = conversation_score(rows)
    final = final_qa_score(agent, conv, accuracy_overall,
                           compliance_score, response_time=None)

    # ================= REPORT =================
    print()
    rule()
    print("                      CALL QA REPORT")
    rule()

    print(f"\n  FINAL QA SCORE:  {final} / 100   ({band(final)})")
    print(f"    Agent score .......... {agent} / 100")
    print(f"    Conversation score ... {conv} / 100")
    acc_txt = "n/a" if accuracy_overall is None else f"{accuracy_overall} / 100"
    print(f"    Answer accuracy ...... {acc_txt}   (RAG, token-free)")
    print(f"    Compliance score ..... {compliance_score} / 100   (RAG, token-free)")

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
    print("  COMPLIANCE CHECK  (RAG, token-free)")
    rule("-")
    for r in compliance_results:
        mark = "OK " if r["status"] == "OK" else "!! "
        print(f"  {mark} {r['rule']}")
        if r["status"] == "BROKEN":
            print(f"        heard: \"{r['evidence'][:52]}\"")

    print("\n")
    rule("-")
    print(f"  ANSWER ACCURACY  ({acc_txt}, RAG, token-free)")
    rule("-")
    if not accuracy_results:
        print("  No client questions matched the knowledge base.")
    for r in accuracy_results:
        print(f"  [{round(r['accuracy']*100)}/100] {r['client_question']}")
        if r["missed"]:
            print(f"        missed: {', '.join(r['missed'])}")

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

    print("\n")
    rule("-")
    print("  GEMMA TOKEN COST  (from Ollama; RoBERTa + RAG steps are token-free)")
    rule("-")
    for c in token_usage["calls"]:
        print(f"  {c['label']:<12} {c['input']:>6} in  {c['output']:>5} out  "
              f"{c['input'] + c['output']:>6} total")
    print(f"  {'TOTAL':<12} {token_usage['input']:>6} in  "
          f"{token_usage['output']:>5} out  {token_usage['total']:>6} total")

    print()
    rule()
    print()
