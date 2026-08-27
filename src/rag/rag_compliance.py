"""Check the agent against the COMPLIANCE RULES, using the RAG (token-free)."""

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

VIOLATION_THRESHOLD = 0.45

def check_compliance(transcript):
    agent_lines = [text for speaker, text in transcript if speaker.lower() == "agent"]
    results = []
    for rule in COMPLIANCE_RULES:
        examples = rule["violations"]
        broken = False
        evidence = ""
        best = 0.0
        for line, (score, _idx) in zip(agent_lines, max_similarity(agent_lines, examples)):
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
