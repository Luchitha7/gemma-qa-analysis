"""Check the agent against the COMPLIANCE RULES, using the RAG (token-free).

For every rule in the knowledge base we have example phrases of what breaking
that rule sounds like. We embed the agent's lines and the violation examples,
and if any agent line is close enough in meaning to a violation example, the
rule is flagged as BROKEN -- with the exact line as evidence.

This uses local embeddings only, so it costs NO LLM tokens.

    python rag_compliance.py
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
_TESTS = os.path.join(_ROOT, "tests")
for _path in [_ROOT, _SRC, _TESTS]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.rag.rag import max_similarity
from src.rag.knowledge_base import COMPLIANCE_RULES
from tests.sample_call import TRANSCRIPT

# An agent line counts as breaking a rule if it's at least this close in meaning
# to one of that rule's violation examples.
VIOLATION_THRESHOLD = 0.45


def check_compliance(transcript):
    """Return (per-rule results, compliance score 0-100)."""
    agent_lines = [text for speaker, text in transcript
                   if speaker.lower() == "agent"]

    results = []
    for rule in COMPLIANCE_RULES:
        examples = rule["violations"]
        broken = False
        evidence = ""
        best = 0.0
        # best match of each agent line against this rule's violation examples
        for line, (score, _idx) in zip(agent_lines,
                                       max_similarity(agent_lines, examples)):
            if score > best:
                best, evidence_line = score, line
            if score >= VIOLATION_THRESHOLD:
                broken = True
        if broken:
            evidence = evidence_line
        results.append({
            "rule": rule["rule"],
            "status": "BROKEN" if broken else "OK",
            "evidence": evidence,
            "closeness": round(best, 3),
        })

    kept = sum(1 for r in results if r["status"] == "OK")
    score = round(kept / len(results) * 100, 1) if results else 100.0
    return results, score


if __name__ == "__main__":
    results, score = check_compliance(TRANSCRIPT)

    print("\n" + "=" * 78)
    print("COMPLIANCE CHECK  (agent lines vs the rules, token-free)")
    print("=" * 78)
    print(f"\nCOMPLIANCE SCORE: {score} / 100\n")
    for r in results:
        mark = "OK " if r["status"] == "OK" else "!! "
        print(f"  {mark} {r['rule']}")
        if r["status"] == "BROKEN":
            print(f"        evidence: \"{r['evidence']}\"")
    print()
