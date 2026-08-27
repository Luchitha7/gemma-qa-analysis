"""WEB VERSION of the Multi-Tenant QA analysis.

Run with: uvicorn src.api.web_app:app --host 0.0.0.0 --port 8000
"""

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_ROOT, "src")
for _path in [_ROOT, _SRC]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import json

from src.db.database import get_db, init_db
from src.db.models import Tenant, Document, CriteriaConfig, EvaluationReport
from src.rag.pdf_parser import convert_pdf_bytes_to_markdown
from src.rag.llm_separator import separate_criteria_and_policies
from src.rag.vector_store import add_policy_chunks, get_tenant_policies, search_policies, delete_tenant_policies
from src.services.dynamic_evaluator import evaluate_interaction, preview_evaluation_prompt

app = FastAPI(title="Multi-Tenant QA Service API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

class TenantCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""

class EvaluateRequest(BaseModel):
    transcript: str
    channel: Optional[str] = "Call"
    agent_name: Optional[str] = "Agent"
    custom_prompt: Optional[str] = None

# ============================================================================
# MULTI-TENANT & RAG API ENDPOINTS
# ============================================================================

@app.get("/api/tenants")
def list_tenants(db: Session = Depends(get_db)):
    """List all registered company tenants."""
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    # If no tenants exist, create default S-NET tenant
    if not tenants:
        default_tenant = Tenant(
            id="S-NET",
            name="S-NET Communications",
            description="Telecommunications & Enterprise IT Support"
        )
        db.add(default_tenant)
        db.commit()
        db.refresh(default_tenant)
        tenants = [default_tenant]

    return [{"id": t.id, "name": t.name, "description": t.description, "created_at": t.created_at} for t in tenants]


@app.post("/api/tenants")
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    """Create a new company tenant."""
    existing = db.query(Tenant).filter(Tenant.id == payload.id).first()
    if existing:
        return {"status": "exists", "tenant": {"id": existing.id, "name": existing.name}}
    tenant = Tenant(id=payload.id, name=payload.name, description=payload.description or "")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return {"status": "created", "tenant": {"id": tenant.id, "name": tenant.name}}


@app.post("/api/tenants/{tenant_id}/upload-pdf")
async def upload_pdf_guideline(tenant_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload company QA guideline PDF, convert to Markdown, separate Criteria and Policies, and store in PostgreSQL & ChromaDB."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        # Auto create tenant if not present
        tenant = Tenant(id=tenant_id, name=tenant_id, description=f"{tenant_id} Support Operations")
        db.add(tenant)
        db.commit()

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty PDF file uploaded.")

    # 1. Lossless PDF to Markdown Conversion
    markdown_text, page_count = convert_pdf_bytes_to_markdown(content, file.filename)

    # 2. Save Document in PostgreSQL
    doc = Document(
        tenant_id=tenant_id,
        filename=file.filename,
        raw_markdown=markdown_text,
        page_count=page_count
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 3. LLM Separation into Criteria JSON & Policy Chunks
    separation_result = separate_criteria_and_policies(markdown_text)
    criteria_json = separation_result.get("criteria", {})
    policy_chunks = separation_result.get("company_policies", [])

    # 4. Save Criteria Config in PostgreSQL
    criteria_record = CriteriaConfig(
        tenant_id=tenant_id,
        channel="All",
        category_weights=criteria_json.get("category_weights", {}),
        auto_fail_rules=criteria_json.get("auto_fail_rules", []),
        raw_json=criteria_json
    )
    db.add(criteria_record)
    db.commit()

    # 5. Embed and Store Policy Chunks in ChromaDB
    add_policy_chunks(tenant_id, policy_chunks)

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "filename": file.filename,
        "page_count": page_count,
        "markdown_char_count": len(markdown_text),
        "criteria_summary": {
            "categories": [c.get("name") for c in criteria_json.get("categories", [])],
            "weights": criteria_json.get("category_weights", {})
        },
        "policy_chunks_count": len(policy_chunks)
    }


@app.get("/api/samples")
def list_sample_inputs():
    """List and return all sample conversation JSON files from the inputs/ folder."""
    inputs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "inputs")
    samples = []
    if os.path.exists(inputs_dir):
        for fname in sorted(os.listdir(inputs_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(inputs_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["filename"] = fname
                        samples.append(data)
                except Exception as e:
                    print(f"Error loading sample {fname}: {e}")
    return samples


@app.get("/api/tenants/{tenant_id}/documents")
def list_tenant_documents(tenant_id: str, db: Session = Depends(get_db)):
    """List all uploaded PDF documents for the given tenant."""
    docs = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "page_count": d.page_count,
            "char_count": len(d.raw_markdown),
            "uploaded_at": d.uploaded_at
        }
        for d in docs
    ]


@app.delete("/api/tenants/{tenant_id}/documents/{document_id}")
def delete_tenant_document(tenant_id: str, document_id: int, db: Session = Depends(get_db)):
    """Delete a single document and remove its record from PostgreSQL."""
    doc = db.query(Document).filter(Document.tenant_id == tenant_id, Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    filename = doc.filename
    db.delete(doc)
    db.commit()
    
    # If no documents remain for tenant, clean up criteria configs & vector policies too
    remaining = db.query(Document).filter(Document.tenant_id == tenant_id).count()
    if remaining == 0:
        db.query(CriteriaConfig).filter(CriteriaConfig.tenant_id == tenant_id).delete()
        db.commit()
        delete_tenant_policies(tenant_id)
        
    return {"status": "deleted", "document_id": document_id, "filename": filename}


@app.delete("/api/tenants/{tenant_id}/knowledge-base")
def clear_tenant_knowledge_base(tenant_id: str, db: Session = Depends(get_db)):
    """Clear all documents, criteria configs, and vector policy chunks for a tenant."""
    # Delete documents
    db.query(Document).filter(Document.tenant_id == tenant_id).delete()
    # Delete criteria configs
    db.query(CriteriaConfig).filter(CriteriaConfig.tenant_id == tenant_id).delete()
    db.commit()
    
    # Delete vector store policies
    delete_tenant_policies(tenant_id)
    return {"status": "cleared", "tenant_id": tenant_id, "message": "All documents, criteria, and vector policies cleared."}


@app.get("/api/tenants/{tenant_id}/markdown")
def get_tenant_markdown(tenant_id: str, db: Session = Depends(get_db)):
    """Retrieve the latest converted Markdown document for the given tenant."""
    doc = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.uploaded_at.desc()).first()
    if not doc:
        return {"markdown": "# No document uploaded yet\nUpload a QA Guideline PDF to view its converted Markdown.", "filename": None}
    return {"markdown": doc.raw_markdown, "filename": doc.filename, "uploaded_at": doc.uploaded_at}


@app.get("/api/tenants/{tenant_id}/criteria")
def get_tenant_criteria(tenant_id: str, db: Session = Depends(get_db)):
    """Retrieve the latest parsed criteria JSON for the given tenant."""
    # Strictly check if an uploaded document exists for this tenant
    doc = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.uploaded_at.desc()).first()
    if not doc or not doc.raw_markdown:
        return {
            "has_criteria": False,
            "category_weights": {},
            "categories": [],
            "auto_fail_rules": []
        }

    criteria = db.query(CriteriaConfig).filter(CriteriaConfig.tenant_id == tenant_id).order_by(CriteriaConfig.created_at.desc()).first()
    if criteria and criteria.raw_json and criteria.raw_json.get("category_weights"):
        return criteria.raw_json

    # Extract dynamically from the uploaded document's markdown
    separation_result = separate_criteria_and_policies(doc.raw_markdown)
    criteria_json = separation_result.get("criteria", {})
    if criteria_json and criteria_json.get("category_weights"):
        crit = CriteriaConfig(
            tenant_id=tenant_id,
            channel="All",
            category_weights=criteria_json.get("category_weights", {}),
            auto_fail_rules=criteria_json.get("auto_fail_rules", []),
            raw_json=criteria_json
        )
        db.add(crit)
        db.commit()
        return criteria_json

    return {
        "has_criteria": False,
        "category_weights": {},
        "categories": [],
        "auto_fail_rules": []
    }


@app.get("/api/tenants/{tenant_id}/policies")
def get_tenant_policy_chunks(tenant_id: str, db: Session = Depends(get_db)):
    """Retrieve stored policy knowledge chunks from Vector DB for the tenant."""
    doc = db.query(Document).filter(Document.tenant_id == tenant_id).first()
    if not doc:
        return []
    return get_tenant_policies(tenant_id)


@app.post("/api/tenants/{tenant_id}/preview-prompt")
def preview_tenant_prompt(tenant_id: str, req: EvaluateRequest, db: Session = Depends(get_db)):
    """Build and preview the exact LLM prompt without executing evaluation."""
    criteria_record = db.query(CriteriaConfig).filter(CriteriaConfig.tenant_id == tenant_id).order_by(CriteriaConfig.created_at.desc()).first()
    criteria_data = criteria_record.raw_json if criteria_record else {}
    if not criteria_data:
        doc = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.uploaded_at.desc()).first()
        if doc and doc.raw_markdown:
            criteria_data = separate_criteria_and_policies(doc.raw_markdown).get("criteria", {})

    preview = preview_evaluation_prompt(
        transcript_text=req.transcript,
        criteria_data=criteria_data,
        tenant_id=tenant_id,
        channel=req.channel or "Call"
    )
    return preview


@app.post("/api/tenants/{tenant_id}/evaluate")
def evaluate_tenant_transcript(tenant_id: str, req: EvaluateRequest, db: Session = Depends(get_db)):
    """Run dynamic QA analysis on a transcript using tenant's custom criteria and Vector RAG."""
    # 1. Fetch criteria
    criteria_record = db.query(CriteriaConfig).filter(CriteriaConfig.tenant_id == tenant_id).order_by(CriteriaConfig.created_at.desc()).first()
    criteria_data = criteria_record.raw_json if criteria_record else {}
    if not criteria_data:
        doc = db.query(Document).filter(Document.tenant_id == tenant_id).order_by(Document.uploaded_at.desc()).first()
        if doc and doc.raw_markdown:
            criteria_data = separate_criteria_and_policies(doc.raw_markdown).get("criteria", {})

    # 2. Run Dynamic Evaluation (supporting custom_prompt if approved/edited by user)
    result = evaluate_interaction(
        transcript_text=req.transcript,
        criteria_data=criteria_data,
        tenant_id=tenant_id,
        channel=req.channel or "Call",
        custom_prompt=req.custom_prompt
    )

    # 3. Save Evaluation in PostgreSQL
    eval_report = EvaluationReport(
        tenant_id=tenant_id,
        channel=req.channel or "Call",
        agent_name=req.agent_name or "Agent",
        transcript=req.transcript,
        final_score=result["final_score"],
        is_auto_fail=result["is_auto_fail"],
        scorecard_json=result["scorecard"],
        sentiment_json=result["sentiment_analysis"],
        rag_matches_json=result["matched_policies"],
        summary=result["summary"],
        suggestions=result["suggestions"]
    )
    db.add(eval_report)
    db.commit()
    db.refresh(eval_report)

    result["evaluation_id"] = eval_report.id
    result["created_at"] = eval_report.created_at
    return result


@app.get("/api/evaluations")
def list_evaluations(tenant_id: Optional[str] = None, db: Session = Depends(get_db)):
    """List past evaluation reports."""
    q = db.query(EvaluationReport)
    if tenant_id:
        q = q.filter(EvaluationReport.tenant_id == tenant_id)
    reports = q.order_by(EvaluationReport.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "channel": r.channel,
            "agent_name": r.agent_name,
            "final_score": r.final_score,
            "is_auto_fail": r.is_auto_fail,
            "created_at": r.created_at,
            "summary": r.summary
        }
        for r in reports
    ]


@app.get("/api/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
    """Get single evaluation report detail."""
    report = db.query(EvaluationReport).filter(EvaluationReport.id == evaluation_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return {
        "id": report.id,
        "tenant_id": report.tenant_id,
        "channel": report.channel,
        "agent_name": report.agent_name,
        "transcript": report.transcript,
        "final_score": report.final_score,
        "is_auto_fail": report.is_auto_fail,
        "scorecard": report.scorecard_json,
        "sentiment_analysis": report.sentiment_json,
        "matched_policies": report.rag_matches_json,
        "summary": report.summary,
        "suggestions": report.suggestions,
        "created_at": report.created_at
    }


@app.delete("/api/evaluations/{evaluation_id}")
def delete_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
    """Delete a single evaluation report from PostgreSQL by its ID."""
    report = db.query(EvaluationReport).filter(EvaluationReport.id == evaluation_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    
    db.delete(report)
    db.commit()
    return {"status": "deleted", "evaluation_id": evaluation_id}


@app.delete("/api/evaluations")
def clear_evaluations(tenant_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Clear all evaluation reports for a given tenant or across all tenants."""
    query = db.query(EvaluationReport)
    if tenant_id:
        query = query.filter(EvaluationReport.tenant_id == tenant_id)
    count = query.count()
    query.delete()
    db.commit()
    return {"status": "cleared", "deleted_count": count, "tenant_id": tenant_id}


SAMPLE = """[00:00] Agent: Thank you for calling HomeNet support, how can I help you today?
[00:06] Client: I was charged twice for my subscription this month and I want it fixed.
[00:09] Agent: I'm sorry to hear that. Let me pull up your account and take a look.
[00:14] Client: This is the second time this has happened, it's really frustrating.
[00:31] Agent: I completely understand, that's not acceptable. I can see the duplicate charge now.
[00:36] Client: Okay, so what happens now?
[00:39] Agent: I've refunded the extra charge and it will show up in 3 to 5 business days.
[00:43] Client: Alright, thank you.
[01:09] Agent: Of course. Is there anything else I can help you with?"""


.replace("%SAMPLE%", _sample_json())


def _sample_json():
    import json
    return json.dumps(SAMPLE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
