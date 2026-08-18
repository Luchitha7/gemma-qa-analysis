"""STEP 4 + 5 of the PDF -> knowledge base feature: build the whole file.

Ties the earlier steps together into one command:

  1. read the PDF and split it into chunks        (pdf_to_kb)
  2. extract each chunk into rules + Q&A          (pdf_extract)
  3. MERGE the chunks and drop duplicates         (this file, step 4)
  4. WRITE a company knowledge base data file     (this file, step 5)

The file we write contains ONLY data: an AGENT_INFO string, a COMPLIANCE_RULES
list, and a QA_PAIRS list, exactly like knowledge_base.py. It has no logic, so
it is safe to open, read, and review before anything loads it. We never write
code that the app would run blindly.

    python build_kb.py path/to/playbook.pdf
    python build_kb.py path/to/playbook.pdf acme_knowledge_base.py
"""

import json
import re
import sys

from pdf_extract import extract_from_chunk
from pdf_to_kb import chunk_pages, extract_pages


# Smart quotes/apostrophes Gemma emits, mapped to plain ASCII so that two lines
# that differ only in punctuation dedupe as the same line.
_PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"',
          "–": "-", "—": "-"}


def _norm(text):
    """Loose key for dedupe: ASCII-punctuation, lowercased, collapsed whitespace.

    This catches lines that are identical apart from a curly vs straight quote or
    trailing spaces. It does NOT catch the same idea worded differently; that
    would need semantic (embedding) matching, which is a later improvement.
    """
    text = str(text)
    for fancy, plain in _PUNCT.items():
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text.strip().lower()).rstrip(".")


def _merge_lists(existing, extra):
    """Add items from `extra` to `existing`, skipping ones already present."""
    seen = {_norm(x) for x in existing}
    for item in extra:
        key = _norm(item)
        if key and key not in seen:
            existing.append(item)
            seen.add(key)
    return existing


def merge_results(results):
    """Combine per-chunk results into one deduped knowledge base.

    Rules are deduped by their rule text (violations from duplicates are pooled).
    Q&A pairs are deduped by their question (variants and key_points pooled).
    """
    rules_by_key = {}
    qa_by_key = {}

    for result in results:
        for rule in result.get("compliance_rules", []):
            key = _norm(rule["rule"])
            if key not in rules_by_key:
                rules_by_key[key] = {"rule": rule["rule"], "violations": []}
            _merge_lists(rules_by_key[key]["violations"], rule.get("violations", []))

        for qa in result.get("qa_pairs", []):
            key = _norm(qa["question"])
            if key not in qa_by_key:
                qa_by_key[key] = {
                    "category": qa.get("category", "general"),
                    "question": qa["question"],
                    "variants": [],
                    "key_points": [],
                    "ideal_answer": qa["ideal_answer"],
                }
            _merge_lists(qa_by_key[key]["variants"], qa.get("variants", []))
            _merge_lists(qa_by_key[key]["key_points"], qa.get("key_points", []))

    return {
        "compliance_rules": list(rules_by_key.values()),
        "qa_pairs": list(qa_by_key.values()),
    }


def _literal(value):
    """A pretty Python literal for the data (JSON is a valid subset here)."""
    return json.dumps(value, indent=4, ensure_ascii=False)


def write_kb_file(data, out_path, source_name):
    """Write the merged data as a knowledge_base-style Python DATA file.

    Only literal assignments are written (a string and two lists), so the file
    carries data and nothing executable.
    """
    agent_info = (
        f"Knowledge base generated from: {source_name}. "
        "Review and edit before use."
    )
    body = (
        '"""Company knowledge base (generated from a playbook PDF).\n\n'
        "This file is DATA only: an AGENT_INFO string, COMPLIANCE_RULES, and\n"
        "QA_PAIRS. It was produced automatically, so review it before loading it\n"
        "into the RAG. Same shape as knowledge_base.py.\n"
        '"""\n\n'
        f"AGENT_INFO = {_literal(agent_info)}\n\n"
        f"COMPLIANCE_RULES = {_literal(data['compliance_rules'])}\n\n"
        f"QA_PAIRS = {_literal(data['qa_pairs'])}\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_kb.py path/to/playbook.pdf [output.py]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "generated_knowledge_base.py"

    pages = extract_pages(pdf_path)
    chunks = chunk_pages(pages)
    print(f"\n{len(pages)} page(s), {len(chunks)} chunk(s). Extracting with Gemma...\n")

    results = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"  chunk {i}/{len(chunks)} (pages {chunk['pages']})...", flush=True)
        results.append(extract_from_chunk(chunk["text"]))

    merged = merge_results(results)
    write_kb_file(merged, out_path, source_name=pdf_path.split("/")[-1])

    print(f"\nDone. {len(merged['compliance_rules'])} rule(s) and "
          f"{len(merged['qa_pairs'])} Q&A pair(s) written to:\n  {out_path}")
    print("Open and review it before pointing the RAG at it.\n")
