"""Integration test for Multi-Tenant PostgreSQL, Vector RAG, and Dynamic Evaluator."""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
for _p in [_ROOT, _SRC]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.db.database import init_db, SessionLocal
from src.db.models import Tenant, CriteriaConfig, Document
from src.rag.vector_store import add_policy_chunks, search_policies
from src.services.dynamic_evaluator import evaluate_interaction


def test_system():
    print("\n--- 1. Testing PostgreSQL Database Connection ---")
    init_db()
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == "S-NET").first()
    if not tenant:
        tenant = Tenant(id="S-NET", name="S-NET Communications", description="Enterprise Telecom Support")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    print(f"[OK] Tenant confirmed in PostgreSQL: {tenant.name} (ID: {tenant.id})")

    print("\n--- 2. Testing Vector RAG Embeddings & Retrieval ---")
    policies = [
        {"title": "Hold Time & Dead Air Policy", "content": "Support must not exceed 3-minute hold times without updating customer. Dead air must not exceed 20 seconds."},
        {"title": "Escalation & Supervisor Protocol", "content": "When a customer requests a supervisor, support must perform a supervised transfer to a lead or schedule a callback."}
    ]
    add_policy_chunks("S-NET", policies)
    hits = search_policies("S-NET", "I want to speak with a manager or supervisor", top_k=2)
    print(f"[OK] RAG Search returned {len(hits)} matching policies:")
    for h in hits:
        print(f"  - [{h['title']}] (Cosine Similarity: {h['similarity']})")

    print("\n--- 3. Testing Dynamic Evaluation Pipeline ---")
    criteria_data = {
        "categories": [
            {
                "name": "Soft Skills",
                "weight_percentage": 25.0,
                "line_items": [
                    {
                        "name": "Branding and Survey",
                        "description": "Verbatim greeting and closing spiels within SLA.",
                        "verbatim_spiels": ["Thank you for calling S-NET Communications...", "Thank you for Choosing S-NET and have a great day."]
                    }
                ]
            },
            {
                "name": "Technical Knowledge",
                "weight_percentage": 50.0,
                "line_items": [
                    {
                        "name": "Ownership",
                        "description": "Took responsibility and offered clear resolution."
                    }
                ]
            },
            {
                "name": "Process Knowledge",
                "weight_percentage": 25.0,
                "line_items": [
                    {
                        "name": "Documentation",
                        "description": "Captured details within SLA."
                    }
                ]
            }
        ],
        "category_weights": {"Soft Skills": 0.25, "Technical Knowledge": 0.50, "Process Knowledge": 0.25},
        "auto_fail_rules": [{"name": "Discourtesy", "description": "Profanity or rudeness"}]
    }

    sample_transcript = """[00:00] Client: My internet is completely down.
[00:05] Agent: Thank you for calling S-NET Communications. My name is Alex, how can I help you today?
[00:15] Agent: I will arrange a technician visit at no cost to fix the router. Thank you for Choosing S-NET and have a great day."""

    result = evaluate_interaction(sample_transcript, criteria_data, "S-NET", "Call")
    print(f"[OK] Dynamic QA Score: {result['final_score']} / 100 (Auto-Fail: {result['is_auto_fail']})")
    print(f"[OK] Scorecard items evaluated: {len(result['scorecard'])}")
    for item in result['scorecard']:
        print(f"  - {item['name']} ({item['category']}): {item['rating']} -> {item['reason']}")
    print("\n[OK] ALL INTEGRATION TESTS PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    test_system()
