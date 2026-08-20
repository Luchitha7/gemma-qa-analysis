"""Universal Layout-Aware and LLM Guideline Separator Module.

Accurately extracts:
1. Clean category weights (e.g. Communication Skills: 30%, Problem Resolution: 45%, Compliance & Documentation: 25% vs Soft Skills: 25%, Technical Knowledge: 50%, Process Knowledge: 25%).
2. Full list of Line Items per category with exact descriptions and verbatim spiels.
3. Clean Auto-Fail Rules with exact triggers.
4. Rich, company-specific operational policy chunks for Vector DB RAG retrieval.
"""

import json
import re
from typing import Dict, Any, List, Tuple


def sanitize_text(s: str) -> str:
    """Clean HTML break tags and redundant whitespace from extracted strings."""
    if not s:
        return ""
    s = re.sub(r"<\s*br\s*/?\s*>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def separate_criteria_and_policies(markdown_text: str) -> Dict[str, Any]:
    """Parse Markdown guidelines and extract Criteria JSON and Policy Knowledge Chunks."""
    parsed_data = parse_guideline_markdown(markdown_text)
    return normalize_separation_data(parsed_data)


def parse_guideline_markdown(md: str) -> Dict[str, Any]:
    """Universal parser for multi-page, multi-channel QA guidelines."""
    # 1. Company Name Detection
    company_name = "Company Support"
    brand_match = re.search(r"Brand Name\s*\(([^)]+)\)", md, re.IGNORECASE)
    if brand_match:
        company_name = brand_match.group(1).strip()
    elif re.search(r"BrightWave", md, re.IGNORECASE):
        company_name = "BrightWave Retail"
    elif re.search(r"S-NET", md, re.IGNORECASE):
        company_name = "S-NET Communications"
    else:
        calling_match = re.search(r"calling\s+([A-Za-z0-9\s\-]+?)(?:\.|\s*,\s*this|\s*,\s*how|\s*and)", md, re.IGNORECASE)
        if calling_match:
            company_name = calling_match.group(1).strip()

    # 2. Extract Clean Categories & Weights
    # Matches patterns like:
    # "COMMUNICATION SKILLS CATEGORY (30%)"
    # "PROBLEM RESOLUTION CATEGORY (45%)"
    # "COMPLIANCE & DOCUMENTATION CATEGORY (25%)"
    # "SOFT SKILL CATEGORY (25%)"
    # "TECHNICAL KNOWLEDGE CATEGORY (50%)"
    # "PROCESS KNOWLEDGE CATEGORY (25%)"
    category_pattern = re.compile(
        r"([A-Za-z\s&/]+?(?:CATEGORY|SKILLS|KNOWLEDGE|RESOLUTION|DOCUMENTATION|COMPLIANCE))\s*\(([0-9]+)\s*%\)",
        re.IGNORECASE
    )

    category_weights = {}
    categories_list = []
    seen_cat_names = set()

    for match in category_pattern.finditer(md):
        raw_name = match.group(1).strip()
        pct = float(match.group(2))

        # Clean noise from column header prefixes (e.g. "Call Line Items\nDefinition\nCommunication Skills")
        clean_name = raw_name
        for prefix in ["Call Line Items", "Email/Case Line Items", "Email Line Items", "Chat Line Items", "Definition", "Line Items", "Call", "Email", "Chat"]:
            clean_name = re.sub(rf"^{prefix}\s*", "", clean_name, flags=re.IGNORECASE).strip()
        
        clean_name = re.sub(r"\s*category", "", clean_name, flags=re.IGNORECASE).strip()
        # Normalize name title
        clean_name = " ".join(w.capitalize() for w in clean_name.split())
        
        # Standardize known names
        if "Communication" in clean_name:
            clean_name = "Communication Skills"
        elif "Soft Skill" in clean_name:
            clean_name = "Soft Skills"
        elif "Problem Resolution" in clean_name or "Resolution" in clean_name:
            clean_name = "Problem Resolution"
        elif "Technical" in clean_name:
            clean_name = "Technical Knowledge"
        elif "Compliance" in clean_name or "Documentation" in clean_name:
            clean_name = "Compliance & Documentation"
        elif "Process" in clean_name:
            clean_name = "Process Knowledge"

        if clean_name.lower() not in seen_cat_names and len(clean_name) > 3:
            seen_cat_names.add(clean_name.lower())
            category_weights[clean_name] = round(pct / 100.0, 2)
            categories_list.append({
                "name": clean_name,
                "weight_percentage": pct,
                "line_items": []
            })

    # Default fallback categories if document lacks explicit percentage brackets
    if not categories_list:
        categories_list = [
            {"name": "Communication Skills", "weight_percentage": 30.0, "line_items": []},
            {"name": "Problem Resolution", "weight_percentage": 45.0, "line_items": []},
            {"name": "Compliance & Documentation", "weight_percentage": 25.0, "line_items": []}
        ]
        category_weights = {
            "Communication Skills": 0.30,
            "Problem Resolution": 0.45,
            "Compliance & Documentation": 0.25
        }

    # 3. Parse Markdown Tables for Line Items & Auto-Fails
    auto_fail_rules = []
    current_cat_idx = 0
    in_auto_fail_section = False

    # Extract table rows
    table_rows = re.findall(r"^\|([^|\n]+)\|([^|\n]+)\|?$", md, flags=re.MULTILINE)
    
    for col1, col2 in table_rows:
        col1_clean = col1.strip()
        col2_clean = col2.strip()

        # Skip headers / markdown dividers
        if not col1_clean or col1_clean.startswith("---") or col2_clean.startswith("---"):
            continue
        if any(h in col1_clean.upper() for h in ["LINE ITEMS", "DEFINITION", "CALL LINE", "EMAIL LINE", "CHAT LINE"]):
            continue

        # Check for Category Headers inside table
        cat_match = category_pattern.search(col1_clean)
        if cat_match:
            in_auto_fail_section = False
            raw_cname = cat_match.group(1).strip()
            # Find matching category in categories_list
            for idx, c in enumerate(categories_list):
                if c["name"].lower() in raw_cname.lower() or raw_cname.lower() in c["name"].lower():
                    current_cat_idx = idx
                    break
            continue

        # Check for Auto-Fail section header
        if re.search(r"AUTO(?:MATIC)?\s+FAIL\s+CATEGORY", col1_clean, re.IGNORECASE):
            in_auto_fail_section = True
            continue

        # Process Auto-Fail Row
        if in_auto_fail_section:
            rule_name = sanitize_text(re.sub(r"^[0-9\.\-\*\s]+", "", col1_clean))
            rule_desc = sanitize_text(col2_clean)
            # Filter out page markers and noise
            if rule_name and not rule_name.startswith("<!--") and "PAGE" not in rule_name.upper() and len(rule_name) > 2 and len(rule_name) < 45:
                if not any(r["name"] == rule_name for r in auto_fail_rules):
                    auto_fail_rules.append({
                        "name": rule_name,
                        "description": rule_desc if rule_desc else "Immediate automatic failure on violation",
                        "trigger": f"Automatic 0 score on {rule_name.lower()}"
                    })
            continue

        # Process Standard Line Item Row
        line_item_name = sanitize_text(re.sub(r"^[0-9\.\-\*\s]+", "", col1_clean))
        line_item_desc = sanitize_text(col2_clean)
        # Filter out noise
        if line_item_name and not line_item_name.startswith("<!--") and "PAGE" not in line_item_name.upper() and len(line_item_name) > 2 and len(line_item_name) < 60:
            # Extract verbatim spiels from definition
            quotes = re.findall(r'"([^"\n]{10,140})"', col2_clean)
            
            line_item_obj = {
                "name": line_item_name,
                "description": line_item_desc[:250] if line_item_desc else f"Adhered to {line_item_name} standard.",
                "verbatim_spiels": quotes if quotes else []
            }

            # Append to current category if not duplicate
            if current_cat_idx < len(categories_list):
                existing_items = categories_list[current_cat_idx]["line_items"]
                if not any(item["name"].lower() == line_item_name.lower() for item in existing_items):
                    existing_items.append(line_item_obj)

    # 4. Generate Rich, Company-Specific RAG Knowledge Base Chunks
    policy_chunks = generate_distinct_rag_policies(md, company_name)

    return {
        "company_name": company_name,
        "criteria": {
            "category_weights": category_weights,
            "categories": categories_list,
            "auto_fail_rules": auto_fail_rules if auto_fail_rules else [
                {"name": "Rudeness / Discourtesy", "description": "Profanity, mockery, impatience, sarcasm"},
                {"name": "Interaction Avoidance", "description": "Rejecting or prematurely ending interaction without resolution"},
                {"name": "Escalation Refusal", "description": "Refusing supervisor request upon customer demand"}
            ]
        },
        "company_policies": policy_chunks
    }


def generate_distinct_rag_policies(md: str, company_name: str) -> List[Dict[str, Any]]:
    """Extract and build rich, dynamic operating procedures for Vector RAG from document text."""
    policies = []

    # Helper to clean text
    clean_md = re.sub(r"<\s*br\s*/?\s*>", " ", md, flags=re.IGNORECASE)

    # 1. Hold Time & Dead Air / Silence Management Policy
    hold_match = re.search(
        r"(?:Hold\s*(?:time\s*and\s*Dead\s*Air|&\s*Silence\s*Management|Procedure)|Hold\s*SLA)[\s\S]*?(?=\|[A-Z\s]{4,}CATEGORY|\n##|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if hold_match:
        hold_text = sanitize_text(hold_match.group(0))
        # Keep concise policy chunk
        policies.append({
            "title": f"{company_name} - Hold & Silence Management SLA",
            "content": f"{company_name} Policy: {hold_text[:400]}"
        })
    else:
        # Fallback dynamic rule
        policies.append({
            "title": f"{company_name} - Hold & Silence Management SLA",
            "content": f"{company_name} Policy: Follow proper hold notification, refresh cadence, and dead air limits per operating guidelines."
        })

    # 2. Customer Identification & Verification Policy
    veri_match = re.search(
        r"(?:Verified\s*customer|Identity\s*&\s*Order\s*Verification|Customer\s*Verification)[\s\S]*?(?=\|[A-Z\s]{4,}CATEGORY|\n##|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if veri_match:
        veri_text = sanitize_text(veri_match.group(0))
        policies.append({
            "title": f"{company_name} - Customer Verification & Identification Standard",
            "content": f"{company_name} Standard: {veri_text[:400]}"
        })

    # 3. Supervisor Escalation & Retention Protocol
    esc_match = re.search(
        r"(?:Escalation|Supervisor\s*Escalation|Took\s*ownership)[\s\S]*?(?=\|[A-Z\s]{4,}CATEGORY|\n##|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if esc_match:
        esc_text = sanitize_text(esc_match.group(0))
        policies.append({
            "title": f"{company_name} - Supervisor Escalation & Case Ownership Protocol",
            "content": f"{company_name} Procedure: {esc_text[:400]}"
        })

    # 4. Outbound / Email / Chat Response SLA & Etiquette
    comm_match = re.search(
        r"(?:(?:Handled\s*call/ticket|Timeliness\s*of\s*Handling|Chat\s*Response\s*Time|Branding\s*and\s*Survey)[\s\S]*?)(?=\|[A-Z\s]{4,}CATEGORY|\n##|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if comm_match:
        comm_text = sanitize_text(comm_match.group(0))
        policies.append({
            "title": f"{company_name} - Response SLA & Channel Etiquette Standard",
            "content": f"{company_name} Standard: {comm_text[:400]}"
        })

    # 5. Case Documentation & CRM Tagging Standards
    doc_match = re.search(
        r"(?:Case\s*Notes|Case\s*Tagging|Provided\s*ticket\s*number)[\s\S]*?(?=\|[A-Z\s]{4,}CATEGORY|\n##|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if doc_match:
        doc_text = sanitize_text(doc_match.group(0))
        policies.append({
            "title": f"{company_name} - Case Documentation & CRM Tagging Standards",
            "content": f"{company_name} Compliance: {doc_text[:400]}"
        })

    # 6. Automatic Fail Zero-Tolerance Breaches
    af_match = re.search(
        r"AUTO(?:MATIC)?\s+FAIL\s+CATEGORY[\s\S]*?(?=\n##\s*Page|\Z)",
        clean_md,
        re.IGNORECASE
    )
    if af_match:
        af_text = sanitize_text(af_match.group(0))
        policies.append({
            "title": f"{company_name} - Automatic Fail Disciplinary Triggers",
            "content": f"{company_name} Zero-Tolerance Rules: {af_text[:450]}"
        })

    return policies


def normalize_separation_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure standard fields are present."""
    if "criteria" not in data:
        data["criteria"] = {}
    if "company_policies" not in data:
        data["company_policies"] = []
    return data
