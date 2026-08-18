"""Comprehensive Test for Accurate Guideline Parsing & RAG Policy Chunking."""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
for _p in [_ROOT, _SRC]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.rag.llm_separator import separate_criteria_and_policies

snet_markdown = """
| CALL LINE ITEMS | DEFINITION |
| --- | --- |
| SOFT SKILL CATEGORY (25%) | |
| Branding and Survey | The support adhered to the verbatim greeting spiel > Company Name (Branding) and support's Name, within 10 seconds\\n\\\"Thank you for calling S-NET Communications. My name is _____ how can I help you today?\\\"\\nThe support adhered to the verbatim closing spiel\\n\\\"Thank you for Choosing S-NET and have a great day.\\\"\\n\\\"I will be transferring you to a brief, 1-question survey regarding your call experience with me today.\\\" |
| Hold time and Dead Air | (1) Follow proper hold procedure: Inform the customer, set expectations & Thank the customer.\\n(2) Support did not exceed 3-minute hold times. 3rd hold up to 10 minutes. Grace period of 5seconds.\\n(3) Dead air should not exceed 20 seconds. |
| Personalized the call/ticket appropriately | Used the CORRECT name in the greeting or at least once throughout the conversation. |
| Empathy & Acknowledgment Statement | (1) Empathize and provide empathy statements.\\n(2) Acknowledged each question or statement. |
| Build rapport and observed professionalism | (1) Courteous. Respectful. (2) Tone does not aggravate. (3) Did not interrupt caller. |
| TECHNICAL KNOWLEDGE CATEGORY (50%) | |
| Paraphrasing | (1) Paraphrasing should be done at onset of call. (2) Repeat in own words. |
| Verified customer | (1) Validate name. (2) Validate company name. (3) All details must be validated: Company name, Caller name, email address & contact number. |
| Probing | Support used proper & effective probing questions. |
| Set proper expectations | (1) Accurate and complete expectations provided. (2) Address possible related issues. |
| Provided the appropriate solution | (1) Performed logical troubleshooting steps. (2) Followed recommended resolution (ARE validation). |
| Took ownership of the problem | (1) Exhausted all resources. (2) Offered assistance. (3) Ticket ownership. |
| Active listening | Asked customer for information already provided (2 repeated info is a markdown). |
| Confirmed the issue is resolved | (1) Gained confirmation. (2) Performed test. (3) Wrap up. |
| Managed the call/ticket in a timely manner | (1) Release call within 10s to 2 mins of closing spiel. (2) Avoid multiple emails. |
| PROCESS KNOWLEDGE CATEGORY (25%) | |
| Case Notes/Documentation | (1) Complete and Correct notes. (7) Late documentation is > 30 minutes. |
| Case Tagging | (1) Complete and Correct Contact, Location & Account, Request Type, Self QA checkboxes, Ticket Status, Channel in Zoho. |
| Provided ticket number | (1) Made sure customer captured ticket number before call ended. |
| Handled call/ticket in a timely manner | (1) Responded via email within 10 minutes. (2) Updated ticket daily. |
| AUTO FAIL CATEGORY | |
| Discourtesy | Support displayed profanity, bashing, impatience, sarcasm. |
| Call/Ticket Avoidance | Support did not respond, rejected call, closed ticket without resolution. |
| Escalation | Support refuses to escalate to a Supervisor at customer's request. |
| Line Release | Call prematurely ended. Did not report incident or initiate callback. |
| Fraud | Any alteration in information related to processes and protocols. |
| Non-First Call Resolution | Incomplete troubleshooting, incorrect resolution given. |
| Call/Ticket Abandonment | Support ceased to help customer for any reason. |
"""

brightwave_markdown = """
| ☎ CALL LINE ITEMS | DEFINITION |
| --- | --- |
| COMMUNICATION SKILLS CATEGORY (30%) | |
| Greeting & Sign-off | The agent used the approved opening script > Brand Name (BrightWave Retail) and agent's first name, within 8 seconds.\\n\\\"Thanks for calling BrightWave Retail, this is ____, how can I make your day better?\\\"\\n\\\"Thanks again for shopping with BrightWave — have a wonderful day!\\\"\\n\\\"I'll be sending you a quick two-question survey about today's experience.\\\" |
| Hold & Silence Management | (1) Hold procedure: notify customer, state estimated wait, thank upon return.\\n(2) Hold segments max 2 minutes. After 2 check-ins, up to 8 minutes max. Grace allowance: 4 seconds.\\n(3) Silence must not exceed 15 seconds (4-second grace). |
| Used Customer's Name | Used customer's correct first or last name at minimum once. |
| Empathy & Validation | (1) Expressed genuine empathy. (2) Acknowledged concern. (3) Positive scripting. |
| Rapport & Professional Conduct | (1) Built genuine connection. (2) Did not escalate. (3) Matched communication style. |
| Outbound Callback Procedure | (1) Outbound script: brand intro, order/case #, reason, resolution, closing. |
| PROBLEM RESOLUTION CATEGORY (45%) | |
| Restated the Issue | (1) Restated concern in own words. (2) Reconfirmed for repeat contacts. |
| Identity & Order Verification | (1) Full name, spelled back. (2) Shipping address/account. (4) All 4 fields verified: full name, email, phone number, order/case number. |
| Discovery Questions | Asked relevant, targeted discovery questions. |
| Expectation Setting | (1) Complete and accurate timelines. (2) Flagged downstream effects. |
| Resolution Quality | (1) Methodical troubleshooting. (2) Internal resolution path (fraud-review). |
| Ownership | (1) Exhausted available tools. (2) Warm/supervised transfer on escalation. |
| Active Listening | Re-asked for info already provided (2nd repeat = violation). |
| Resolution Confirmation | (1) Confirmed fully resolved. (2) Asked customer to test. |
| Time Management | (1) Released call within 10-90 seconds of closing script. (4) Updates within 4 hours. |
| COMPLIANCE & DOCUMENTATION CATEGORY (25%) | |
| Case Notes | (1) Complete, accurate notes. (7) Submitted within 20 minutes of interaction. |
| Case Tagging | (1) Correctly tagged Contact, Store/Region, Issue Category, Self-QA checkboxes, Case Status, Channel. |
| Case Number Provided | (1) Ensured customer received case number before ending interaction. |
| Timeliness of Handling | (1) Responded within 15 minutes of assignment. (2) Updated at least once per day. |
| AUTOMATIC FAIL CATEGORY | |
| Rudeness | Agent displayed profanity, mockery, impatience, sarcasm. |
| Interaction Avoidance | Agent did not respond, rejected interaction, stayed on line > 3 mins after closing. |
| Escalation Refusal | Refused to escalate to supervisor when customer requested or threatened cancellation. |
| Improper Disconnect | Call ended prematurely, not logged per dropped-call protocol. |
| Misrepresentation | Undocumented alteration of process-related info or misrepresenting facts. |
| Resolution Failure | Incomplete troubleshooting, incorrect resolution communicated. |
| Case Abandonment | Agent stopped assisting customer for any reason. |
"""

res_snet = separate_criteria_and_policies(snet_markdown)
res_bw = separate_criteria_and_policies(brightwave_markdown)

print("=" * 60)
print("COMPANY 1 (S-NET):", res_snet["company_name"])
print("Weights:", res_snet["criteria"]["category_weights"])
print("Total Categories:", len(res_snet["criteria"]["categories"]))
for cat in res_snet["criteria"]["categories"]:
    print(f"  - {cat['name']} ({cat['weight_percentage']}%): {len(cat['line_items'])} line items")
    for li in cat["line_items"][:2]:
        print(f"      * {li['name']}")
print("Auto-Fail Rules count:", len(res_snet["criteria"]["auto_fail_rules"]))
print("Auto-Fail Rule names:", [r["name"] for r in res_snet["criteria"]["auto_fail_rules"]])
print("RAG Policies count:", len(res_snet["company_policies"]))
for p in res_snet["company_policies"]:
    print(f"  [Policy] {p['title']}: {p['content'][:80]}...")

print("=" * 60)
print("COMPANY 2 (BRIGHTWAVE):", res_bw["company_name"])
print("Weights:", res_bw["criteria"]["category_weights"])
print("Total Categories:", len(res_bw["criteria"]["categories"]))
for cat in res_bw["criteria"]["categories"]:
    print(f"  - {cat['name']} ({cat['weight_percentage']}%): {len(cat['line_items'])} line items")
    for li in cat["line_items"][:2]:
        print(f"      * {li['name']}")
print("Auto-Fail Rules count:", len(res_bw["criteria"]["auto_fail_rules"]))
print("Auto-Fail Rule names:", [r["name"] for r in res_bw["criteria"]["auto_fail_rules"]])
print("RAG Policies count:", len(res_bw["company_policies"]))
for p in res_bw["company_policies"]:
    print(f"  [Policy] {p['title']}: {p['content'][:80]}...")
print("=" * 60)
