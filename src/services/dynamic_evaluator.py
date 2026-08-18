"""Dynamic Multi-Tenant QA Evaluator Module.

Combines RoBERTa sentiment analysis, ChromaDB policy RAG retrieval, and
Gemma 3 4B reasoning against dynamic company criteria schemas.
"""

import re
from typing import Dict, Any, List, Optional
from src.core.gemma_client import gemma
from src.services.qa_intensity import analyze, INTENSITY_THRESHOLD
from src.services.qa_summary import SUMMARY_PROMPT
from src.services.qa_suggestions import SUGGESTIONS_PROMPT, clean_suggestions
from src.rag.vector_store import search_policies
from src.services.response_time import (
    leading_time_seconds, response_delays, response_time_score,
)

RATING_SCORES = {"PASS": 100, "PARTIAL": 50, "FAIL": 0}


def evaluate_interaction(
    transcript_text: str,
    criteria_data: Dict[str, Any],
    tenant_id: str,
    channel: str = "Call",
    times: Optional[List[Optional[int]]] = None
) -> Dict[str, Any]:
    """Execute dynamic QA evaluation for a customer interaction."""
    # 1. Parse turns
    turns = []
    parsed_times = []
    for line in transcript_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        t = leading_time_seconds(line)
        line = re.sub(r"^[\[\(]\s*\d{1,2}:\d{2}(?::\d{2})?\s*[\]\)]\s*", "", line)
        if ":" in line:
            spk, txt = line.split(":", 1)
            turns.append((spk.strip(), txt.strip()))
            parsed_times.append(t)

    if not turns:
        turns = [("Agent", transcript_text)]
        parsed_times = [None]

    # 2. RoBERTa Tone & Intensity Analysis
    sentiment_rows = analyze(turns)
    intense_moments = [r for r in sentiment_rows if r.get("intense")]
    harsh_agent_lines = [
        r for r in sentiment_rows
        if r.get("speaker", "").lower() == "agent" and r.get("sentiment", 0) <= INTENSITY_THRESHOLD
    ]

    # 3. Vector RAG Policy Search
    # Find client questions/concerns and search company policy chunks
    client_queries = [txt for spk, txt in turns if spk.lower() in {"client", "customer", "caller"}]
    combined_query = " ".join(client_queries[:3]) if client_queries else transcript_text[:300]
    matched_policies = search_policies(tenant_id, combined_query, top_k=3)

    # 4. Extract Criteria Line Items and Weights
    categories = criteria_data.get("categories", [])
    category_weights = criteria_data.get("category_weights", {})
    auto_fail_rules = criteria_data.get("auto_fail_rules", [])

    # If no categories provided, use standard default
    if not categories:
        categories = [
            {
                "name": "General Handling",
                "weight_percentage": 100.0,
                "line_items": [
                    {"name": "Professionalism & Tone", "description": "Polite, respectful, no discourtesy."},
                    {"name": "Accuracy & Knowledge", "description": "Provided correct solution according to policy."},
                    {"name": "Ownership & Resolution", "description": "Took ownership and resolved the issue."}
                ]
            }
        ]
        category_weights = {"General Handling": 1.0}

    # 5. Build Dynamic Scorecard Prompt
    scorecard_prompt = build_dynamic_prompt(
        transcript_text=transcript_text,
        categories=categories,
        auto_fail_rules=auto_fail_rules,
        matched_policies=matched_policies,
        intense_moments=intense_moments,
        harsh_lines=harsh_agent_lines,
        channel=channel
    )

    # 6. Gemma LLM Evaluation
    llm_reply = gemma(scorecard_prompt, label="dynamic_scorecard")
    ratings = parse_dynamic_ratings(llm_reply, categories)

    # 7. Check Auto-Fail Triggers
    is_auto_fail, auto_fail_reason = check_auto_fail(transcript_text, harsh_agent_lines, auto_fail_rules)

    # 8. Mathematical Scoring Engine
    category_scores, blended_score = calculate_category_scores(ratings, category_weights, is_auto_fail)

    # 9. Summary & Suggestions
    summary = gemma(SUMMARY_PROMPT.format(transcript=transcript_text), label="summary")
    suggestions = clean_suggestions(gemma(SUGGESTIONS_PROMPT.format(transcript=transcript_text), label="suggestions"))

    return {
        "final_score": blended_score,
        "is_auto_fail": is_auto_fail,
        "auto_fail_reason": auto_fail_reason,
        "category_scores": category_scores,
        "scorecard": ratings,
        "sentiment_analysis": {
            "rows": sentiment_rows,
            "intense_moments": intense_moments,
            "harsh_agent_lines": harsh_agent_lines
        },
        "matched_policies": matched_policies,
        "summary": summary,
        "suggestions": suggestions
    }


def build_dynamic_prompt(
    transcript_text: str,
    categories: List[Dict[str, Any]],
    auto_fail_rules: List[Dict[str, Any]],
    matched_policies: List[Dict[str, Any]],
    intense_moments: List[Dict[str, Any]],
    harsh_lines: List[Dict[str, Any]],
    channel: str
) -> str:
    """Construct dynamic LLM prompt tailored to tenant criteria."""
    items_list = []
    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            desc = item.get("description", "")
            spiels = item.get("verbatim_spiels", [])
            spiel_txt = f" [Required Spiels: {', '.join(spiels)}]" if spiels else ""
            items_list.append(f"- [{cat_name}] {name}: {desc}{spiel_txt}")

    criteria_str = "\n".join(items_list)
    
    policies_str = "\n".join(
        f"• {p['title']}: {p['content'][:300]}" for p in matched_policies
    ) or "• No specific policy override found."

    intense_str = "\n".join(
        f"- Turn {m.get('turn')} ({m.get('speaker')}): {m.get('text')}" for m in intense_moments
    ) or "- (none flagged)"

    harsh_str = "\n".join(
        f"- Turn {m.get('turn')}: {m.get('text')}" for m in harsh_lines
    ) or "- (none)"

    return f"""You are a STRICT Call Quality Assurance Auditor evaluating a {channel} interaction.
Your task is to judge the AGENT against each specific evaluation line item.

RATING CRITERIA:
- PASS: Agent met all requirements, was polite, helpful, and followed required spiels/policies.
- PARTIAL: Agent was partially compliant, missed a spiel minorly, or showed minor delays.
- FAIL: Agent was rude, unhelpful, failed policy, or refused to help.

COMPANY POLICY CONTEXT (Retrieved from Knowledge Base):
{policies_str}

EVALUATION LINE ITEMS TO RATE:
{criteria_str}

FLAGGED TENSE MOMENTS:
{intense_str}

HARSH/NEGATIVE AGENT LINES (Weigh heavily for tone):
{harsh_str}

TRANSCRIPT:
{transcript_text}

OUTPUT FORMAT INSTRUCTIONS:
Reply with ONE line per line item in this exact format:
Line Item Name: PASS/PARTIAL/FAIL - Short specific audit reason.
"""


def parse_dynamic_ratings(reply: str, categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse PASS/PARTIAL/FAIL ratings from LLM output."""
    ratings = []
    for cat in categories:
        cat_name = cat.get("name", "Category")
        for item in cat.get("line_items", []):
            name = item.get("name", "Item")
            rating = "PASS"
            reason = "Standard compliant response"

            # Search in reply
            for line in reply.splitlines():
                if name.lower() in line.lower() or name.split()[0].lower() in line.lower():
                    match = re.search(r"\b(PASS|PARTIAL|FAIL)\b", line, re.IGNORECASE)
                    if match:
                        rating = match.group(1).upper()
                        reason = line.split(match.group(0), 1)[-1].lstrip(" -:").strip()
                        break

            score = RATING_SCORES.get(rating, 50)
            ratings.append({
                "category": cat_name,
                "name": name,
                "rating": rating,
                "score": score,
                "reason": reason or f"Evaluated as {rating}"
            })
    return ratings


def check_auto_fail(
    transcript: str,
    harsh_lines: List[Dict[str, Any]],
    auto_fail_rules: List[Dict[str, Any]]
) -> (bool, Optional[str]):
    """Check for instant zero auto-fail breaches."""
    lower_tx = transcript.lower()

    # Profanity / extreme discourtesy check
    profanities = ["fuck", "shut up", "idiot", "get lost", "stupid", "hang up"]
    for word in profanities:
        if word in lower_tx:
            return True, f"Auto-Fail Triggered: Profanity/Discourtesy detected ('{word}')"

    # Extreme harsh agent lines
    if len(harsh_lines) >= 3:
        return True, "Auto-Fail Triggered: Multiple highly hostile/harsh agent statements detected"

    return False, None


def calculate_category_scores(
    ratings: List[Dict[str, Any]],
    category_weights: Dict[str, float],
    is_auto_fail: bool
) -> (Dict[str, float], float):
    """Calculate weighted category scores and blended final score."""
    if is_auto_fail:
        return {cat: 0.0 for cat in category_weights}, 0.0

    grouped = {}
    for r in ratings:
        cat = r.get("category", "General Handling")
        grouped.setdefault(cat, []).append(r["score"])

    cat_scores = {}
    for cat, scores in grouped.items():
        cat_scores[cat] = round(sum(scores) / len(scores), 1)

    total_weight = sum(category_weights.values()) or 1.0
    blended = sum(cat_scores.get(cat, 70.0) * (category_weights.get(cat, 1.0) / total_weight) for cat in category_weights)
    
    if not category_weights:
        all_scores = [r["score"] for r in ratings]
        blended = sum(all_scores) / len(all_scores) if all_scores else 80.0

    return cat_scores, round(blended, 1)
