content = """# SignalQA Multi-Tenant API Reference & Samples

This document outlines the REST API for the **Multi-Tenant RAG QA Pipeline**. The backend runs on FastAPI.

Base URL for local development: http://localhost:8000

---

## 1. Manage Tenants

Tenants act as isolated workspaces for different companies or clients, each holding their own specific QA guidelines, knowledge base (ChromaDB vectors), and historical evaluations.

### **POST /api/tenants**
Create a new tenant.

**Request:**
`json
{
  "id": "snet-comm",
  "name": "S-NET Communications",
  "description": "Telecom and Internet Provider"
}
`

**Response:**
`json
{
  "id": "snet-comm",
  "name": "S-NET Communications",
  "description": "Telecom and Internet Provider",
  "created_at": "2026-08-27T10:00:00Z"
}
`

### **GET /api/tenants**
Lists all active tenants in the system.

---

## 2. Ingest Guidelines (PDF to RAG)

### **POST /api/tenants/{tenant_id}/upload-pdf**
Uploads a company Quality Assurance guideline PDF. 
The system automatically:
1. Converts the PDF layout into clean Markdown.
2. Extracts Category Weights and Auto-Fail Rules into PostgreSQL.
3. Chunks and indexes operational policies into ChromaDB (Vector RAG).

**Request:**
multipart/form-data with field ile (the .pdf file).

**Response:**
`json
{
  "status": "success",
  "document_id": 1,
  "tenant_id": "snet-comm",
  "criteria": {
    "categories": [
      {
        "name": "Professionalism",
        "weight_percentage": 40.0,
        "line_items": [
          {
            "name": "Greeting",
            "description": "Used standard greeting.",
            "verbatim_spiels": ["Thank you for calling S-NET, my name is..."]
          }
        ]
      }
    ],
    "auto_fail_rules": [
      {
        "name": "Profanity",
        "description": "Agent used offensive language."
      }
    ]
  },
  "policies_extracted": 5
}
`

---

## 3. Dynamic Evaluation (QA Audit)

### **POST /api/tenants/{tenant_id}/evaluate**
Executes a dynamic QA audit using Gemma 3 4B, RoBERTa sentiment analysis, and ChromaDB vector lookups.

**Request:**
`json
{
  "transcript": "[00:00] Agent: Thank you for calling S-NET support, my name is Alex. How can I help?\\n[00:06] Client: I was charged twice for my subscription this month and I want it fixed.\\n[00:09] Agent: I'm sorry to hear that. Let me pull up your account.",
  "channel": "Call",
  "agent_name": "Alex"
}
`

**Response:**
`json
{
  "evaluation_id": 42,
  "tenant_id": "snet-comm",
  "created_at": "2026-08-27T10:05:00Z",
  "final_score": 100.0,
  "is_auto_fail": false,
  "auto_fail_reason": null,
  "category_scores": {
    "Professionalism": 100.0
  },
  "scorecard": [
    {
      "category": "Professionalism",
      "name": "Greeting",
      "rating": "PASS",
      "score": 100.0,
      "reason": "Agent used standard greeting with their name."
    }
  ],
  "sentiment_analysis": {
    "intense_moments": [
      {
        "turn": 2,
        "speaker": "Client",
        "text": "I was charged twice for my subscription this month...",
        "sentiment": -0.85
      }
    ],
    "harsh_agent_lines": []
  },
  "matched_policies": [
    {
      "title": "Billing Dispute Protocol",
      "content": "Agents must apologize immediately for any duplicate charge claims and pull up the account.",
      "similarity": 0.82
    }
  ],
  "summary": "Client called regarding a duplicate subscription charge. Agent apologized and began account review.",
  "suggestions": "Great immediate empathy shown. Next step: confirm the charge amount explicitly."
}
`

---

## 4. Audit History

### **GET /api/evaluations?tenant_id={tenant_id}**
Retrieves the historical log of QA audits stored in PostgreSQL.

**Response:**
`json
[
  {
    "id": 42,
    "tenant_id": "snet-comm",
    "channel": "Call",
    "agent_name": "Alex",
    "final_score": 100.0,
    "is_auto_fail": false,
    "created_at": "2026-08-27T10:05:00Z"
  }
]
`
"""
import os
os.makedirs("docs", exist_ok=True)
with open("docs/api_samples.md", "w", encoding="utf-8") as f:
    f.write(content)
