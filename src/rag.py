"""The RAG retrieval step (the "R" in RAG).

Turns every known question (and its alternate phrasings) into an embedding --
its meaning as a list of numbers -- then for any client question finds the
closest one. This is how we look up the "ideal answer" for what the client
asked, even when the wording is completely different.

Small, local model (all-MiniLM-L6-v2) + cosine similarity. Embeddings are
normalized so the similarity scores are stable and comparable. No vector
database needed for a POC -- the knowledge base is tiny, so we compare in memory.

    python rag.py
"""

import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

import env_loader  # noqa: F401  (loads .env into os.environ on import)

from sentence_transformers import SentenceTransformer, util

from knowledge_base import QA_PAIRS

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# How confident a match is, based on the similarity score.
STRONG_MATCH = 0.55
WEAK_MATCH = 0.35   # below this we treat it as "no reliable match"

# Load once. First run downloads the small model (~90 MB), then it's cached.
_model = SentenceTransformer(MODEL_NAME)

# Build the search index: the main question AND every variant point back to the
# same knowledge-base entry, so any phrasing can find it.
_index_texts = []
_index_to_pair = []
for pair_idx, pair in enumerate(QA_PAIRS):
    for text in [pair["question"], *pair.get("variants", [])]:
        _index_texts.append(text)
        _index_to_pair.append(pair_idx)

_index_embeddings = _model.encode(_index_texts, convert_to_tensor=True,
                                  normalize_embeddings=True)


def _confidence(score):
    if score >= STRONG_MATCH:
        return "strong"
    if score >= WEAK_MATCH:
        return "weak"
    return "none"


def similarity(text_a, text_b):
    """How close two pieces of text are in meaning (0..1)."""
    emb = _model.encode([text_a, text_b], convert_to_tensor=True,
                        normalize_embeddings=True)
    return round(float(util.cos_sim(emb[0], emb[1])), 3)


def embed(texts):
    """Normalized embeddings for a list of texts (for batch comparisons)."""
    return _model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)


def max_similarity(lines, references):
    """For each line, the best similarity to any reference, and which one.

    Returns list of (best_score, best_reference_index) per line. Token-free.
    """
    if not lines or not references:
        return []
    line_emb = embed(lines)
    ref_emb = embed(references)
    sims = util.cos_sim(line_emb, ref_emb)   # rows = lines, cols = references
    out = []
    for row in sims:
        best_idx = int(row.argmax())
        out.append((round(float(row[best_idx]), 3), best_idx))
    return out


def retrieve(query, k=1):
    """Return the top-k closest knowledge-base entries for a client question.

    Each result carries the full entry (question, variants, key_points,
    ideal_answer) plus the match `score` (0..1) and a `confidence` label.
    Duplicate entries (matched via different variants) are collapsed.
    """
    query_embedding = _model.encode(query, convert_to_tensor=True,
                                    normalize_embeddings=True)
    scores = util.cos_sim(query_embedding, _index_embeddings)[0]

    # best score per knowledge-base entry
    best_per_pair = {}
    for i, score in enumerate(scores):
        pair_idx = _index_to_pair[i]
        s = float(score)
        if pair_idx not in best_per_pair or s > best_per_pair[pair_idx]:
            best_per_pair[pair_idx] = s

    ranked = sorted(best_per_pair.items(), key=lambda kv: kv[1], reverse=True)
    results = []
    for pair_idx, score in ranked[:k]:
        pair = QA_PAIRS[pair_idx]
        results.append({
            "question": pair["question"],
            "key_points": pair.get("key_points", []),
            "ideal_answer": pair["ideal_answer"],
            "score": round(score, 3),
            "confidence": _confidence(score),
        })
    return results


if __name__ == "__main__":
    tests = [
        "my net has been dead all day",
        "you charged me two times",
        "let me talk to your manager",
        "the router light is red and blinking",
        "what is your refund policy for gift cards",  # should be a weak/no match
    ]

    print("\n" + "=" * 78)
    print("RAG RETRIEVAL TEST  (client question -> closest known question)")
    print("=" * 78)
    for q in tests:
        best = retrieve(q, k=1)[0]
        print(f"\nClient said : {q}")
        print(f"Matched     : {best['question']}")
        print(f"Confidence  : {best['confidence']}  (similarity {best['score']})")
    print()
