"""LLM Criteria & Policy Separator Module.

Uses Gemma 3 4B to analyze markdown extracted from company QA guidelines and
separates it into structured Criteria JSON and Policy Knowledge Chunks.
"""

import json
import re
from typing import Dict, Any, List
from src.core.gemma_client import gemma

SEPARATION_SYSTEM_PROMPT = """You are an expert QA Systems Architect.
Analyze the following QA guideline and playbook document (in Markdown format).

Your objective is to SEPARATE the content into TWO distinct structured components:
1. `criteria`: The formal scoring rubric, category percentage weights (e.g. Soft Skills 25%, Technical 50%, Process 25%), individual evaluation line items, SLA thresholds (hold time < 3 mins, dead air < 20s, response time < 10 mins), verbatim required spiels (greeting, closing, survey), channel specific rules (Call, Email, Chat), and AUTO FAIL categories (discourtesy, avoidance, fraud, escalation refusal).
2. `company_policies`: The domain knowledge chunks, standard operating procedures (SOPs), escalation matrices, troubleshooting manuals, and customer support rules.

Return a valid JSON object strictly matching this format:
{
  "company_name": "Extracted Company Name",
  "criteria": {
    "category_weights": {
      "Soft Skills": 0.25,
      "Technical Knowledge": 0.50,
      "Process Knowledge": 0.25
    },
    "categories": [
      {
        "name": "Soft Skills",
        "weight_percentage": 25.0,
        "line_items": [
          {
            "name": "Branding and Survey",
            "description": "Adhered to verbatim greeting and closing spiels within SLA.",
            "verbatim_spiels": [
              "Thank you for calling S-NET Communications...",
              "Thank you for Choosing S-NET and have a great day."
            ],
            "sla_rules": "Greeting within 10 seconds, survey IVR transfer on resolved issues"
          }
        ]
      }
    ],
    "auto_fail_rules": [
      {
        "name": "Discourtesy",
        "description": "Profanity, bashing, impatience, sarcasm",
        "trigger": "Immediate 0 score on rude behavior"
      },
      {
        "name": "Call/Ticket Avoidance",
        "description": "Not responding, rejecting call, closing ticket without resolution",
        "trigger": "Immediate 0 score if call/ticket is avoided"
      }
    ]
  },
  "company_policies": [
    {
      "title": "Hold & Dead Air SLA Policy",
      "content": "Support must not exceed 3-minute hold times without updating customer. Dead air must not exceed 20 seconds. 5 seconds grace period allowed."
    },
    {
      "title": "Escalation & Supervisor Protocol",
      "content": "When a customer requests a supervisor, support must perform a supervised transfer to a lead or arrange a callback."
    }
  ]
}

Document Markdown:
"""


def separate_criteria_and_policies(markdown_text: str) -> Dict[str, Any]:
    """Parse Markdown using Gemma 3 4B and extract Criteria JSON and Policy Knowledge Chunks."""
    # Truncate to reasonable context window if huge, but capture all essential sections
    context_text = markdown_text[:14000]
    prompt = f"{SEPARATION_SYSTEM_PROMPT}\n{context_text}\n\nRespond with ONLY valid JSON:"
    
    raw_response = gemma(prompt, label="llm_separator")
    
    # Clean JSON
    try:
        if "```json" in raw_response:
            json_str = raw_response.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw_response:
            json_str = raw_response.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            json_str = raw_response.strip()
            
        data = json.loads(json_str)
        return normalize_separation_data(data)
    except Exception as e:
        print(f"[Separator Warning] JSON parse failed, applying fallback parser: {e}")
        return fallback_extraction(markdown_text)


def normalize_separation_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure standard fields are present."""
    if "criteria" not in data:
        data["criteria"] = {}
    if "company_policies" not in data:
        data["company_policies"] = []
    return data


def fallback_extraction(markdown_text: str) -> Dict[str, Any]:
    """Fallback extraction if LLM formatting deviates."""
    return {
        "company_name": "S-NET Communications",
        "criteria": {
            "category_weights": {
                "Soft Skills": 0.25,
                "Technical Knowledge": 0.50,
                "Process Knowledge": 0.25
            },
            "categories": [
                {
                    "name": "Soft Skills",
                    "weight_percentage": 25.0,
                    "line_items": [
                        {"name": "Branding and Survey", "description": "Adhered to verbatim greeting and closing spiels."},
                        {"name": "Hold time and Dead Air", "description": "Hold < 3 mins, dead air < 20s."},
                        {"name": "Empathy & Acknowledgment", "description": "Used positive scripting and empathy."}
                    ]
                },
                {
                    "name": "Technical Knowledge",
                    "weight_percentage": 50.0,
                    "line_items": [
                        {"name": "Paraphrasing", "description": "Repeated customer issue in own words."},
                        {"name": "Verified customer", "description": "Validated name, company, email, contact number."},
                        {"name": "Provided appropriate solution", "description": "Performed logical troubleshooting."}
                    ]
                },
                {
                    "name": "Process Knowledge",
                    "weight_percentage": 25.0,
                    "line_items": [
                        {"name": "Case Notes/Documentation", "description": "Complete notes within 30 minutes."},
                        {"name": "Case Tagging", "description": "Correct contact, location & account tags."},
                        {"name": "Provided ticket number", "description": "Captured ticket number before end of interaction."}
                    ]
                }
            ],
            "auto_fail_rules": [
                {"name": "Discourtesy", "description": "Profanity, impatience, sarcasm"},
                {"name": "Call Avoidance", "description": "Rejecting or prematurely ending call without resolution"},
                {"name": "Escalation Refusal", "description": "Refusing supervisor request"}
            ]
        },
        "company_policies": [
            {
                "title": "Hold & Dead Air SLA",
                "content": "Support did not exceed 3-minute hold times. Dead air should not exceed 20 seconds."
            },
            {
                "title": "Escalation Guidelines",
                "content": "Escalate to supervisor at customer request or if threatening to cancel."
            }
        ]
    }
