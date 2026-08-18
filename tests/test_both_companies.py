import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
for _p in [_ROOT, _SRC]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.rag.llm_separator import separate_criteria_and_policies

snet_text = """
# QA Form Guideline - S-NET Communications
## SOFT SKILL CATEGORY (25%)
Branding and Survey: The support adhered to verbatim greeting "Thank you for calling S-NET Communications. My name is _____ how can I help you today?"
## TECHNICAL KNOWLEDGE CATEGORY (50%)
Verified customer: Validated name, company, email.
## PROCESS KNOWLEDGE CATEGORY (25%)
Case Tagging: Tagged correctly in Zoho.
## AUTO FAIL CATEGORY
Discourtesy: Displayed profanity or rudeness.
Call Avoidance: Premature disconnect.
"""

brightwave_text = """
# QA Evaluation Form Guideline - BrightWave Retail
## COMMUNICATION SKILLS CATEGORY (30%)
Greeting & Sign-off: "Thanks for calling BrightWave Retail, this is ____, how can I make your day better?"
## PROBLEM RESOLUTION CATEGORY (45%)
Identity & Order Verification: Confirmed customer full name and shipping address.
## COMPLIANCE & DOCUMENTATION CATEGORY (25%)
Case Notes: Complete and clearly written notes.
## AUTOMATIC FAIL CATEGORY
Rudeness: Agent displayed profanity or mockery.
Interaction Avoidance: No response at any point.
"""

res_snet = separate_criteria_and_policies(snet_text)
res_bw = separate_criteria_and_policies(brightwave_text)

print("=== COMPANY 1: S-NET COMMUNICATIONS ===")
print("Company Name:", res_snet["company_name"])
print("Category Weights:", res_snet["criteria"]["category_weights"])
print("Line Item Categories:", [c["name"] + f" ({c['weight_percentage']}%)" for c in res_snet["criteria"]["categories"]])
print("Auto-Fail Rules:", [r["name"] for r in res_snet["criteria"]["auto_fail_rules"][:3]])

print("\n=== COMPANY 2: BRIGHTWAVE RETAIL ===")
print("Company Name:", res_bw["company_name"])
print("Category Weights:", res_bw["criteria"]["category_weights"])
print("Line Item Categories:", [c["name"] + f" ({c['weight_percentage']}%)" for c in res_bw["criteria"]["categories"]])
print("Auto-Fail Rules:", [r["name"] for r in res_bw["criteria"]["auto_fail_rules"][:3]])
