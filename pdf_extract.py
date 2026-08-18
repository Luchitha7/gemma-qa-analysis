"""STEP 3 of the PDF -> knowledge base feature: turn a chunk into structured data.

pdf_to_kb.py already reads a playbook PDF and splits it into chunks. This step
takes ONE chunk of that text and asks Gemma to pull it apart into the shape our
knowledge base uses:

  - compliance_rules : {"rule": ..., "violations": [example phrases]}
  - qa_pairs         : {"category", "question", "variants", "key_points",
                        "ideal_answer"}

This is the hard part of the feature, so we prove it on a single chunk first
before building the merge-and-write plumbing around it. Gemma is asked to reply
with JSON only, and we parse it defensively: a messy reply is reported, never
crashes.

    python pdf_extract.py path/to/playbook.pdf          # extract chunk 1
    python pdf_extract.py path/to/playbook.pdf 2        # extract chunk 2
"""

import json
import re
import sys

import json_repair

from gemma_client import gemma
from pdf_to_kb import chunk_pages, extract_pages

# We ask Gemma for ONE thing at a time. A 1B model reliably mangles a single big
# object that mixes rules and Q&A, so each call returns a short, flat JSON list
# instead, which is far easier for it to get right (and for us to repair).

RULES_PROMPT = """You are reading part of a customer-support agent playbook.
Find the firm rules the agent MUST follow that actually appear in the text below.
Do NOT invent rules. If the text has no rules, reply with just: []

For each rule give:
  - "rule": a short sentence naming the rule
  - "violations": a LIST of 2-4 short quotes of what an agent BREAKING the rule
    would actually SAY. These are the WRONG, rude, or careless things a bad agent
    says. They must be the OPPOSITE of following the rule, never the correct way.

Study this example carefully, especially how each violation is the agent doing
the WRONG thing:
[
  {{"rule": "Verify the customer's identity before sharing account details",
    "violations": [
      "Sure, your balance is 82 dollars, no need to verify anything.",
      "I'll just read out the card on file, you sound legit.",
      "Verification is a hassle, let's skip it."
    ]}},
  {{"rule": "Never promise a refund without approval",
    "violations": [
      "Yes, I guarantee you'll get a full refund today.",
      "Don't worry, that money is definitely coming back to you."
    ]}}
]

The example above only shows the PATTERN. Do NOT reuse its sentences. Write fresh
violations based on the rules in the text below, in a support agent's own words.

Reply with ONLY a JSON array, nothing before or after it, in the shape shown above.

Text to read:
{chunk}
"""

QA_PROMPT = """You are reading part of a customer-support agent playbook.
Find the customer questions that the text below actually answers. Do NOT invent
questions. If the text has no questions, reply with just: []

For each question give:
  - "category": one of billing, technical, account, escalation, general
  - "question": the main way a customer would ask it
  - "variants": a LIST of 2-3 other ways to ask the same thing
  - "key_points": a LIST of the must-say facts a good answer needs
  - "ideal_answer": one or two sentences, the model answer

Reply with ONLY a JSON array, nothing before or after it, in this shape:
[
  {{"category": "...", "question": "...", "variants": ["...", "..."],
    "key_points": ["...", "..."], "ideal_answer": "..."}}
]

Text to read:
{chunk}
"""

EMPTY = {"compliance_rules": [], "qa_pairs": []}


def _parse_list(reply):
    """Pull a JSON array out of Gemma's reply and return it as a Python list.

    Strips a ```json fence if present, takes everything from the first '[' to
    the last ']', and repairs common small-model JSON mistakes (smart quotes,
    missing or trailing commas). Returns [] if nothing usable is found.
    """
    fenced = re.search(r"```(?:json)?\s*(\[.*\])\s*```", reply, re.DOTALL)
    blob = fenced.group(1) if fenced else None
    if blob is None:
        start = reply.find("[")
        end = reply.rfind("]")
        if start == -1 or end <= start:
            return []
        blob = reply[start:end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        data = json_repair.loads(blob)
    return data if isinstance(data, list) else []


def _as_list(value):
    """Force a value into a clean list of non-empty strings.

    Gemma sometimes returns a single string where the schema wants a list, so
    we coerce it here rather than trusting the reply.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _clean_rule(raw):
    """Keep only the schema fields of a compliance rule; drop anything extra."""
    rule = str(raw.get("rule", "")).strip()
    if not rule:
        return None
    return {"rule": rule, "violations": _as_list(raw.get("violations"))}


def _clean_qa(raw):
    """Keep only the schema fields of a Q&A pair; drop anything extra."""
    question = str(raw.get("question", "")).strip()
    ideal = str(raw.get("ideal_answer", "")).strip()
    if not question or not ideal:
        return None
    return {
        "category": str(raw.get("category", "general")).strip().lower() or "general",
        "question": question,
        "variants": _as_list(raw.get("variants")),
        "key_points": _as_list(raw.get("key_points")),
        "ideal_answer": ideal,
    }


def normalize(data):
    """Force Gemma's parsed reply into our exact schema.

    Coerces list fields, drops unknown fields, and skips items that are missing
    the parts we need. A slightly-off reply still comes out clean.
    """
    rules = [r for r in (_clean_rule(x) for x in data.get("compliance_rules", [])
                         if isinstance(x, dict)) if r]
    qa = [q for q in (_clean_qa(x) for x in data.get("qa_pairs", [])
                     if isinstance(x, dict)) if q]
    return {"compliance_rules": rules, "qa_pairs": qa}


def extract_from_chunk(chunk_text):
    """Turn one chunk into {compliance_rules, qa_pairs}, cleaned to our schema.

    Uses two focused Gemma calls (rules, then Q&A) so each reply is a short flat
    list the model can produce reliably. Always returns the schema shape.
    """
    rules_reply = gemma(RULES_PROMPT.format(chunk=chunk_text),
                        num_predict=1600, label="kb-rules")
    qa_reply = gemma(QA_PROMPT.format(chunk=chunk_text),
                     num_predict=2600, label="kb-qa")
    return normalize({
        "compliance_rules": _parse_list(rules_reply),
        "qa_pairs": _parse_list(qa_reply),
    })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_extract.py path/to/playbook.pdf [chunk_number]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    chunk_number = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    pages = extract_pages(pdf_path)
    chunks = chunk_pages(pages)

    if not 1 <= chunk_number <= len(chunks):
        print(f"This PDF has {len(chunks)} chunk(s). Pick a number in 1..{len(chunks)}.")
        sys.exit(1)

    chunk = chunks[chunk_number - 1]
    print(f"\nExtracting chunk {chunk_number} of {len(chunks)} "
          f"(pages {chunk['pages']}, {len(chunk['text'])} chars)...\n")

    result = extract_from_chunk(chunk["text"])

    rules = result["compliance_rules"]
    qa = result["qa_pairs"]
    print(f"Found {len(rules)} compliance rule(s) and {len(qa)} Q&A pair(s).\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
