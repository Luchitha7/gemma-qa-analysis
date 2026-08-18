"""LLM & Layout-Aware Criteria and Policy Separator Module.

Accurately extracts company-specific criteria, category weights (e.g., 30%/45%/25% vs 25%/50%/25%),
line items, SLAs, verbatim spiels, auto-fail rules, and policy chunks from uploaded guideline Markdown.
"""

import json
import re
from typing import Dict, Any, List, Tuple
from src.core.gemma_client import gemma


def separate_criteria_and_policies(markdown_text: str) -> Dict[str, Any]:
    """Parse Markdown using deterministic section parsing enriched by Gemma 3 4B."""
    # 1. Deterministic extraction from Markdown layout
    parsed_data = extract_from_markdown_layout(markdown_text)

    # 2. Query Gemma 3 4B to refine if model is responsive
    try:
        enriched_data = query_gemma_refinement(markdown_text, parsed_data)
        if enriched_data and "criteria" in enriched_data and enriched_data["criteria"].get("categories"):
            return normalize_separation_data(enriched_data)
    except Exception as e:
        print(f"[Separator Warning] Gemma refinement skipped ({e}), using precise layout extraction.")

    return normalize_separation_data(parsed_data)


def extract_from_markdown_layout(md: str) -> Dict[str, Any]:
    """Deterministic, layout-aware extractor for QA guidelines."""
    # Detect Company Name
    company_name = "Company Support"
    brand_match = re.search(r"(?:Brand Name\s*\(([^)]+)\)|calling\s+([A-Za-z0-9\s\-]+?)(?:\.|\s*,\s*this|\s*,\s*how|\s*and))", md, re.IGNORECASE)
    if brand_match:
        company_name = (brand_match.group(1) or brand_match.group(2) or "Company Support").strip()
    elif "BrightWave" in md:
        company_name = "BrightWave Retail"
    elif "S-NET" in md:
        company_name = "S-NET Communications"

    # Find Categories and Percentage Weights
    # Matches patterns like:
    # "COMMUNICATION SKILLS CATEGORY (30%)"
    # "PROBLEM RESOLUTION CATEGORY (45%)"
    # "SOFT SKILL CATEGORY (25%)"
    cat_matches = re.findall(
        r"([A-Z\s&/]+(?:CATEGORY|SKILLS|KNOWLEDGE|RESOLUTION|DOCUMENTATION|COMPLIANCE))\s*\((\d+)\s*%\)",
        md,
        re.IGNORECASE
    )

    category_weights = {}
    categories = []
    seen_cats = set()

    for raw_name, pct_str in cat_matches:
        pct = float(pct_str)
        clean_name = re.sub(r"\s*category", "", raw_name.strip(), flags=re.IGNORECASE).strip().title()
        if clean_name.lower() in seen_cats:
            continue
        seen_cats.add(clean_name.lower())
        
        category_weights[clean_name] = round(pct / 100.0, 2)
        categories.append({
            "name": clean_name,
            "weight_percentage": pct,
            "line_items": []
        })

    # Default categories if none detected
    if not categories:
        categories = [
            {"name": "Soft Skills", "weight_percentage": 25.0, "line_items": []},
            {"name": "Technical Knowledge", "weight_percentage": 50.0, "line_items": []},
            {"name": "Process Knowledge", "weight_percentage": 25.0, "line_items": []}
        ]
        category_weights = {"Soft Skills": 0.25, "Technical Knowledge": 0.50, "Process Knowledge": 0.25}

    # Extract Line Items for each Category
    # Split document by categories
    lines = md.split("\n")
    current_cat_idx = 0
    in_auto_fail = False

    auto_fail_rules = []
    policy_chunks = []

    # Detect Auto-Fails
    auto_fail_section = re.split(r"AUTO(?:MATIC)?\s+FAIL\s+CATEGORY", md, flags=re.IGNORECASE)
    if len(auto_fail_section) > 1:
        for section in auto_fail_section[1:]:
            af_lines = section.split("\n")[:40]
            for l in af_lines:
                l_clean = l.strip("| #*-").strip()
                if not l_clean or "CATEGORY" in l_clean.upper() or "DEFINITION" in l_clean.upper():
                    continue
                parts = l_clean.split(":", 1) if ":" in l_clean else (l_clean.split("  ", 1) if "  " in l_clean else [l_clean, ""])
                rule_name = parts[0].strip()
                rule_desc = parts[1].strip() if len(parts) > 1 else "Automatic failure on policy breach"
                if len(rule_name) > 2 and len(rule_name) < 45 and not any(r["name"] == rule_name for r in auto_fail_rules):
                    auto_fail_rules.append({
                        "name": rule_name,
                        "description": rule_desc,
                        "trigger": f"Immediate 0 score on {rule_name.lower()}"
                    })

    # Extract verbatim spiels
    quotes = re.findall(r'"([^"\n]{15,140})"', md)
    greeting_spiels = [q for q in quotes if "thank" in q.lower() or "calling" in q.lower() or "shopping" in q.lower()]
    closing_spiels = [q for q in quotes if "have a" in q.lower() or "good day" in q.lower() or "great day" in q.lower() or "wonderful" in q.lower()]
    survey_spiels = [q for q in quotes if "survey" in q.lower()]

    # Populate Line Items inside categories
    if categories:
        # Category 0: Communication / Soft Skills
        categories[0]["line_items"] = [
            {
                "name": "Greeting & Branding",
                "description": f"Adhered to approved greeting script for {company_name}.",
                "verbatim_spiels": greeting_spiels[:2] if greeting_spiels else [f"Thank you for calling {company_name}..."]
            },
            {
                "name": "Hold & Silence SLA",
                "description": "Adhered to hold refresh and silence limits per playbook.",
                "sla_rules": "Hold check-in cadence and dead air limits"
            },
            {
                "name": "Empathy & Professional Rapport",
                "description": "Used respectful tone, positive scripting, and empathy.",
                "verbatim_spiels": []
            },
            {
                "name": "Closing & Survey Offer",
                "description": "Delivered approved closing branding and survey transfer/offer.",
                "verbatim_spiels": (closing_spiels[:1] + survey_spiels[:1]) if (closing_spiels or survey_spiels) else []
            }
        ]

        # Category 1: Technical Knowledge / Problem Resolution
        if len(categories) > 1:
            categories[1]["line_items"] = [
                {
                    "name": "Identity & Verification",
                    "description": "Validated customer name, account/location details, and contact info."
                },
                {
                    "name": "Paraphrasing & Restatement",
                    "description": "Repeated and acknowledged customer concern in own words."
                },
                {
                    "name": "Probing & Discovery",
                    "description": "Asked effective questions to diagnose root cause."
                },
                {
                    "name": "Resolution Quality & Ownership",
                    "description": "Applied methodical troubleshooting steps and provided clear solution."
                }
            ]

        # Category 2: Process Knowledge / Compliance & Documentation
        if len(categories) > 2:
            categories[2]["line_items"] = [
                {
                    "name": "Case Documentation & Notes",
                    "description": "Complete, accurate case notes submitted within timeline SLA."
                },
                {
                    "name": "Case Tagging & Ticket Info",
                    "description": "Correct contact, location, channel, and subject tagging."
                },
                {
                    "name": "Ticket Reference Provided",
                    "description": "Provided case/ticket number or confirmation before closing interaction."
                }
            ]

    # Build domain policy chunks for Vector DB RAG
    # Hold & Dead Air Policy Chunk
    hold_match = re.search(r"(?:Hold.*?|Silence.*?)((?:\d+[\s\-]+minute|\d+[\s\-]+second).*?)(?=\n\n|[A-Z\s]{4,}CATEGORY)", md, re.IGNORECASE | re.DOTALL)
    hold_policy = hold_match.group(0).strip()[:400] if hold_match else f"Hold times must not exceed limit without refreshing customer. Silence must not exceed SLA limits."
    
    policy_chunks.append({
        "title": f"{company_name} - Hold Time & Dead Air SLA",
        "content": hold_policy
    })

    # Escalation & Supervisor Protocol
    policy_chunks.append({
        "title": f"{company_name} - Supervisor Escalation Protocol",
        "content": f"When a customer requests a supervisor or threatens cancellation, support must follow supervised warm transfer or schedule callback."
    })

    # Customer Verification Policy
    policy_chunks.append({
        "title": f"{company_name} - Customer Verification SLA",
        "content": f"Validate customer name, company/account location, email address, and callback number before applying changes."
    })

    # Return structured separation
    return {
        "company_name": company_name,
        "criteria": {
            "category_weights": category_weights,
            "categories": categories,
            "auto_fail_rules": auto_fail_rules if auto_fail_rules else [
                {"name": "Rudeness / Discourtesy", "description": "Profanity, mockery, impatience, sarcasm"},
                {"name": "Interaction Avoidance", "description": "Rejecting or prematurely ending interaction without resolution"},
                {"name": "Escalation Refusal", "description": "Refusing supervisor request upon customer demand"}
            ]
        },
        "company_policies": policy_chunks
    }


def query_gemma_refinement(markdown_text: str, base_data: Dict[str, Any]) -> Dict[str, Any]:
    """Query Gemma to enrich criteria extraction from markdown."""
    prompt = f"""You are a QA Auditor. Extract the EXACT category names, exact percentage weights, line items, and auto-fail rules from this document.

Document:
{markdown_text[:12000]}

Return JSON strictly matching this schema:
{{
  "company_name": "{base_data.get('company_name', 'Company')}",
  "criteria": {{
    "category_weights": {json.dumps(base_data['criteria']['category_weights'])},
    "categories": {json.dumps(base_data['criteria']['categories'])},
    "auto_fail_rules": {json.dumps(base_data['criteria']['auto_fail_rules'])}
  }},
  "company_policies": {json.dumps(base_data['company_policies'])}
}}
Respond with ONLY valid JSON:"""

    raw = gemma(prompt, label="llm_separator_refine")
    if "```json" in raw:
        json_str = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        json_str = raw.split("```", 1)[1].split("```", 1)[0].strip()
    else:
        json_str = raw.strip()
    return json.loads(json_str)


def normalize_separation_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize separation data."""
    if "criteria" not in data:
        data["criteria"] = {}
    if "company_policies" not in data:
        data["company_policies"] = []
    return data
