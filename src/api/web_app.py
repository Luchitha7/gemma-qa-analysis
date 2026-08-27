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


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>SignalQA</title>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        :root {
          --cream: #fbf9f4;
          --beige: #eae8e3;
          --beige-warm: #f0e0ca;
          --ink: #1b1c19;
          --muted: #444748;
          --faint: #747878;
          --line: #c4c7c7;
          --error: #ba1a1a;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: 'Hanken Grotesk', -apple-system, sans-serif;
          background: var(--cream);
          color: var(--ink);
          -webkit-font-smoothing: antialiased;
        }
        .serif { font-family: 'Playfair Display', Georgia, serif; }
        a { color: inherit; text-decoration: none; }

        /* ---- top nav ---- */
        .nav {
          display: flex; align-items: center; justify-content: space-between;
          padding: 26px 64px; border-bottom: 0.5px solid var(--line);
        }
        .wordmark { font-family: 'Playfair Display', serif; font-style: italic; font-size: 22px; letter-spacing: 0.02em; }

        /* ---- layout ---- */
        .wrap { max-width: 1440px; margin: 0 auto; padding: 0 64px; }
        .grid { display: grid; grid-template-columns: 360px 1fr; gap: 72px; padding: 56px 0 96px; }
        @media (max-width: 900px) { .wrap { padding: 0 24px; } .grid { grid-template-columns: 1fr; gap: 48px; } .nav { padding: 20px 24px; } }

        h1.title { font-family: 'Playfair Display', serif; font-weight: 400; font-size: 56px; line-height: 1.05; letter-spacing: -0.02em; margin: 0 0 18px; }
        @media (max-width: 900px) { h1.title { font-size: 40px; } }
        .lede { font-size: 15px; line-height: 1.65; color: var(--muted); margin: 0 0 40px; max-width: 34ch; }

        .label { font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); }

        /* ---- input ---- */
        .field-label { display: block; margin-bottom: 12px; }
        textarea {
          width: 100%; min-height: 300px; background: var(--cream);
          border: 0.5px solid var(--line); border-radius: 0; padding: 18px;
          font-family: 'Hanken Grotesk', sans-serif; font-size: 14px; line-height: 1.7;
          color: var(--ink); resize: vertical;
        }
        textarea::placeholder { color: var(--faint); }
        textarea:focus { outline: none; border-color: var(--ink); }
        .actions { display: flex; gap: 14px; margin-top: 22px; }
        .btn {
          font-family: 'Hanken Grotesk', sans-serif; font-size: 12px; font-weight: 700;
          letter-spacing: 0.1em; text-transform: uppercase; padding: 15px 26px;
          border-radius: 0; cursor: pointer; border: 0.5px solid var(--ink); transition: background .15s, color .15s;
        }
        .btn.primary { background: var(--ink); color: var(--cream); }
        .btn.primary:hover { background: var(--beige-warm); color: var(--ink); border-color: var(--beige-warm); }
        .btn.ghost { background: transparent; color: var(--ink); }
        .btn.ghost:hover { background: var(--beige); }
        .btn:disabled { opacity: 0.4; cursor: default; }
        .hint { font-size: 12px; color: var(--faint); margin-top: 18px; line-height: 1.5; }

        /* ---- weights editor ---- */
        .wrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-bottom: 0.5px solid var(--line); }
        .wrow label { font-size: 14px; }
        .wcell { display: flex; align-items: center; gap: 6px; }
        .wcell input {
          width: 62px; background: var(--cream); border: 0.5px solid var(--line);
          padding: 8px 10px; font-family: 'Hanken Grotesk', sans-serif; font-size: 14px;
          color: var(--ink); text-align: right;
        }
        .wcell input:focus { outline: none; border-color: var(--ink); }
        .wsuffix { font-size: 13px; color: var(--faint); }
        .wtotal { border-bottom: none; }
        .wtotal label { font-weight: 600; }
        .wtotal #w_total { font-size: 15px; }
        .wtotal.off #w_total { color: var(--error); }
        .wtotal.off label { color: var(--error); }

        /* ---- left: tense moments ---- */
        .side-block { margin-top: 64px; }
        .side-block > .label { display: block; margin-bottom: 22px; padding-bottom: 12px; border-bottom: 0.5px solid var(--line); }
        .tense-item { padding-left: 16px; border-left: 2px solid var(--error); margin-bottom: 22px; }
        .tense-item .who { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--error); }
        .tense-item .val { font-size: 14px; color: var(--muted); margin-top: 2px; }

        /* ---- right column ---- */
        #results { display: none; }
        .placeholder { color: var(--faint); font-size: 15px; line-height: 1.7; max-width: 40ch; padding-top: 8px; }

        .score-block { display: flex; gap: 48px; align-items: center; flex-wrap: wrap; }
        .ring-wrap { position: relative; width: 200px; height: 200px; flex: none; }
        .ring-wrap svg { width: 200px; height: 200px; }
        .ring-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .ring-num { font-family: 'Playfair Display', serif; font-size: 30px; }
        .ring-label { font-size: 10px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--faint); margin-top: 4px; }
        .subscores { display: grid; grid-template-columns: 1fr 1fr; gap: 30px 44px; }
        .sub .sub-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); }
        .sub .sub-num { font-family: 'Playfair Display', serif; font-size: 34px; line-height: 1.1; margin-top: 6px; }

        .warn { background: var(--beige-warm); border: 0.5px solid #d8c49a; color: #6b4e12; padding: 14px 18px; margin-top: 32px; font-size: 14px; }

        section.blk { margin-top: 56px; }
        section.blk > h2 {
          font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
          color: var(--faint); margin: 0 0 20px; padding-bottom: 12px; border-bottom: 0.5px solid var(--line);
        }
        .prose { font-size: 16px; line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

        /* compliance / scorecard rows */
        .fill { background: var(--beige); padding: 30px 34px; }
        .row-line { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 0; border-bottom: 0.5px solid var(--line); }
        .row-line:last-child { border-bottom: none; }
        .row-line .rl-text { font-size: 15px; }
        .tag { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 5px 12px; color: #fff; }
        .tag.ok { background: var(--ink); }
        .tag.broken, .tag.fail { background: var(--error); }
        .tag.partial { background: var(--secondary, #685d4b); background: #685d4b; }
        .tag.pass { background: var(--ink); }
        .tag.unrated { background: var(--faint); }
        .evidence { font-size: 13px; font-style: italic; color: var(--error); margin-top: 4px; }
        .rl-sub { font-size: 13px; color: var(--muted); margin-top: 4px; }

        /* accuracy two-box */
        .acc-item { margin-bottom: 40px; }
        .acc-item:last-child { margin-bottom: 0; }
        .acc-q { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
        .acc-meta { font-size: 12px; color: var(--faint); margin-bottom: 16px; }
        .acc-boxes { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        @media (max-width: 700px) { .acc-boxes { grid-template-columns: 1fr; } }
        .acc-box { padding: 22px 24px; border: 0.5px solid var(--line); }
        .acc-box.ideal { background: var(--beige-warm); border-color: var(--beige-warm); }
        .acc-box .box-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--faint); margin-bottom: 12px; }
        .acc-box .box-text { font-size: 14px; line-height: 1.6; font-style: italic; }
        .kp { font-size: 13px; margin-top: 12px; }
        .kp.ok { color: #3d5c46; } .kp.no { color: var(--error); }

        /* response time */
        .rt-row { display: flex; align-items: baseline; gap: 18px; padding: 12px 0; border-bottom: 0.5px solid var(--line); }
        .rt-row:last-child { border-bottom: none; }
        .rt-delay { font-family: 'Playfair Display', serif; font-size: 20px; min-width: 64px; }
        .rt-delay.slow { color: var(--error); }
        .rt-text { font-size: 14px; color: var(--muted); }

        /* suggestions */
        .sugg { font-size: 15px; line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

        .spinner { width: 14px; height: 14px; border: 2px solid var(--line); border-top-color: var(--ink); border-radius: 50%; animation: spin .8s linear infinite; display: inline-block; vertical-align: middle; margin-right: 6px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        footer { border-top: 0.5px solid var(--line); }
        .foot { max-width: 1440px; margin: 0 auto; padding: 40px 64px; display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap; }
        .foot .copy { font-size: 12px; color: var(--faint); max-width: 30ch; line-height: 1.6; }
      </style>
    </head>
    <body>
      <nav class="nav">
        <div class="wordmark">SignalQA</div>
      </nav>

      <div class="wrap">
        <div class="grid">
          <div class="left">
            <h1 class="title">SignalQA</h1>
            <p class="lede">Automated linguistic and compliance evaluation for telecommunication customer interactions. Precision auditing for quality control.</p>

            <label class="label field-label">Session Transcript Input</label>
            <textarea id="transcript" placeholder="Paste call transcript here or load sample for analysis..."></textarea>
            <div class="actions">
              <button class="btn primary" id="analyzeBtn" onclick="analyze()">Analyze Call</button>
              <button class="btn ghost" onclick="loadSample()">Load Sample</button>
              <button class="btn ghost" id="reportBtn" onclick="downloadReport()" style="display:none">Download Report</button>
            </div>
            <div class="hint" id="status">One line per turn. Works with Agent:/Client:, also AI:/Customer: and [00:15] timestamps.</div>

            <div class="side-block" id="weightsBlock">
              <span class="label">Scoring Weights</span>
              <div class="wrow"><label>Agent handling</label><span class="wcell"><input type="number" id="w_agent" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Answer accuracy</label><span class="wcell"><input type="number" id="w_accuracy" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Compliance</label><span class="wcell"><input type="number" id="w_compliance" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Customer sentiment</label><span class="wcell"><input type="number" id="w_conversation" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow"><label>Response time</label><span class="wcell"><input type="number" id="w_response_time" step="1" min="0"><span class="wsuffix">%</span></span></div>
              <div class="wrow wtotal"><label>Total</label><span class="wcell"><strong id="w_total">100</strong><span class="wsuffix">%</span></span></div>
              <div class="actions">
                <button class="btn primary" id="saveWeightsBtn" onclick="saveWeights()">Save Weights</button>
                <button class="btn ghost" onclick="loadWeights()">Reload</button>
              </div>
              <div class="hint" id="weightsStatus">Loading current weightsâ€¦</div>
            </div>

            <div class="side-block" id="tenseBlock" style="display:none">
              <span class="label">Tense Moment Detected</span>
              <div id="tense"></div>
            </div>
          </div>

          <div class="right">
            <div id="placeholder" class="placeholder">Run an analysis to see the quality report â€” final score, agent scorecard, compliance check, answer accuracy, response time, and suggestions.</div>

            <div id="results">
              <div class="score-block">
                <div class="ring-wrap">
                  <svg viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="88" fill="none" stroke="var(--line)" stroke-width="2"/>
                    <circle id="ringArc" cx="100" cy="100" r="88" fill="none" stroke="var(--ink)" stroke-width="2" stroke-dasharray="552.9" stroke-dashoffset="552.9" transform="rotate(-90 100 100)"/>
                  </svg>
                  <div class="ring-center">
                    <div class="ring-num serif" id="finalScore">&mdash;</div>
                    <div class="ring-label">Final QA Score</div>
                  </div>
                </div>
                <div class="subscores">
                  <div class="sub"><div class="sub-label">Agent</div><div class="sub-num" id="agentScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Conversation</div><div class="sub-num" id="convScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Accuracy</div><div class="sub-num" id="accScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Compliance</div><div class="sub-num" id="compScore">&mdash;</div></div>
                  <div class="sub"><div class="sub-label">Response Time</div><div class="sub-num" id="rtScore">&mdash;</div></div>
                </div>
              </div>

              <div class="warn" id="warning" style="display:none"></div>

              <section class="blk"><h2>Summary</h2><div class="prose" id="summary"></div></section>
              <section class="blk"><h2>Compliance Check</h2><div class="fill" id="compliance"></div></section>
              <section class="blk"><h2>Agent Scorecard</h2><div id="scorecard"></div></section>
              <section class="blk"><h2>Response Time</h2><div id="responsetime"></div></section>
              <section class="blk"><h2>Accuracy Analysis</h2><div id="accuracy"></div></section>
              <section class="blk"><h2>Suggestions</h2><div class="sugg" id="suggestions"></div></section>
              <section class="blk"><h2>Gemma Token Cost</h2><div id="tokencost"></div></section>
            </div>
          </div>
        </div>
      </div>

      <footer>
        <div class="foot">
          <div class="wordmark">SignalQA</div>
          <div class="copy">Automated linguistic and compliance evaluation. Defined by precision.</div>
        </div>
      </footer>

      <script>
        const SAMPLE = %SAMPLE%;
        function loadSample() { document.getElementById('transcript').value = SAMPLE; }
        function esc(s){ const d=document.createElement('div'); d.textContent = (s==null?'':s); return d.innerHTML; }

        // ---- scoring weights ----
        // The backend stores weights as fractions (0.45); we show them as whole
        // percentages (45) because that's how people read them. We convert on
        // the way in and out. The scorer rescales anyway, so they need not total
        // exactly 100 â€” but we show the running total so it's easy to keep tidy.
        const WEIGHT_KEYS = ['agent','accuracy','compliance','conversation','response_time'];

        function updateTotal() {
          var total = 0;
          WEIGHT_KEYS.forEach(function(k){ total += parseFloat(document.getElementById('w_'+k).value) || 0; });
          total = Math.round(total);
          document.getElementById('w_total').textContent = total;
          // Flag when it doesn't add to 100. The score still rescales, so this
          // is a nudge to keep it tidy, not a hard error.
          document.querySelector('.wtotal').classList.toggle('off', total !== 100);
        }

        async function loadWeights() {
          const st = document.getElementById('weightsStatus');
          try {
            const w = await (await fetch('/weights')).json();
            WEIGHT_KEYS.forEach(function(k){
              document.getElementById('w_'+k).value = Math.round((w[k]||0) * 100);
            });
            updateTotal();
            st.textContent = 'These weights are applied to every call.';
          } catch(e){ st.textContent = 'Could not load weights: ' + e; }
        }

        async function saveWeights() {
          const st = document.getElementById('weightsStatus');
          const btn = document.getElementById('saveWeightsBtn');
          const payload = {};
          WEIGHT_KEYS.forEach(function(k){
            payload[k] = (parseFloat(document.getElementById('w_'+k).value) || 0) / 100;
          });
          btn.disabled = true;
          st.textContent = 'Savingâ€¦';
          try {
            const res = await fetch('/weights', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
            await res.json();
            st.textContent = 'Saved. Every call from now on uses these weights.';
          } catch(e){ st.textContent = 'Could not save: ' + e; }
          btn.disabled = false;
        }

        // Recompute the total live as the numbers are edited.
        WEIGHT_KEYS.forEach(function(k){
          document.getElementById('w_'+k).addEventListener('input', updateTotal);
        });

        loadWeights();  // fill the boxes with the current weights on page load

        let lastResult = null;  // the most recent /analyze result, for the PDF

        async function downloadReport() {
          if (!lastResult) return;
          const rbtn = document.getElementById('reportBtn');
          const status = document.getElementById('status');
          rbtn.disabled = true;
          const original = rbtn.textContent;
          rbtn.textContent = 'Preparingâ€¦';
          try {
            const res = await fetch('/report', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(lastResult) });
            if (!res.ok) { status.textContent = 'Could not build the report.'; return; }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'call_qa_report.pdf';
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
          } catch(e){ status.textContent = 'Something went wrong: ' + e; }
          rbtn.textContent = original;
          rbtn.disabled = false;
        }

        async function analyze() {
          const transcript = document.getElementById('transcript').value.trim();
          const btn = document.getElementById('analyzeBtn');
          const status = document.getElementById('status');
          if (!transcript) { status.textContent = 'Please paste a transcript first.'; return; }
          btn.disabled = true;
          status.innerHTML = '<span class="spinner"></span> Analyzingâ€¦';
          try {
            const res = await fetch('/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ transcript }) });
            const data = await res.json();
            if (data.error) { status.textContent = data.error; btn.disabled=false; return; }
            render(data);
            lastResult = data;
            document.getElementById('reportBtn').style.display = '';
            status.textContent = 'Analysis complete.';
          } catch(e){ status.textContent = 'Something went wrong: ' + e; }
          btn.disabled = false;
        }

        function render(d) {
          document.getElementById('placeholder').style.display = 'none';
          document.getElementById('results').style.display = 'block';

          document.getElementById('finalScore').textContent = d.final;
          const C = 552.9;
          document.getElementById('ringArc').style.strokeDashoffset = C * (1 - Math.max(0, Math.min(100, d.final)) / 100);

          document.getElementById('agentScore').textContent = d.agent;
          document.getElementById('convScore').textContent = d.conversation;
          document.getElementById('accScore').textContent = (d.accuracy_overall==null)?'n/a':d.accuracy_overall;
          document.getElementById('compScore').textContent = (d.compliance_score==null)?'n/a':d.compliance_score;
          document.getElementById('rtScore').textContent = (d.response_time_score==null)?'n/a':d.response_time_score;

          document.getElementById('summary').textContent = d.summary;
          document.getElementById('suggestions').textContent = d.suggestions;

          const warn = document.getElementById('warning');
          if (d.warning) { warn.textContent = d.warning; warn.style.display='block'; } else { warn.style.display='none'; }

          document.getElementById('compliance').innerHTML = (d.compliance||[]).map(function(r){
            var broken = r.status === 'BROKEN';
            return '<div class="row-line"><div><div class="rl-text">'+esc(r.rule)+'</div>'+(broken?'<div class="evidence">heard: "'+esc(r.evidence)+'"</div>':'')+'</div><span class="tag '+(broken?'broken':'ok')+'">'+(broken?'Broken':'OK')+'</span></div>';
          }).join('');

          document.getElementById('scorecard').innerHTML = (d.ratings||[]).map(function(r){
            return '<div class="row-line"><div><div class="rl-text">'+esc(r.name)+'</div><div class="rl-sub">'+esc(r.reason)+'</div></div><span class="tag '+r.rating.toLowerCase()+'">'+esc(r.rating)+'</span></div>';
          }).join('');

          var rt = document.getElementById('responsetime');
          if (!d.response_times || d.response_times.length===0) {
            rt.innerHTML = '<div class="placeholder">No timestamps found &mdash; add times like [00:15] to each line to measure response time.</div>';
          } else {
            rt.innerHTML = d.response_times.map(function(r){
              return '<div class="rt-row"><span class="rt-delay serif '+(r.slow?'slow':'')+'">'+r.delay+'s</span><span class="rt-text">after: '+esc(r.client_text)+'</span></div>';
            }).join('');
          }

          var acc = document.getElementById('accuracy');
          if (!d.accuracy || d.accuracy.length===0) {
            acc.innerHTML = '<div class="placeholder">No client questions matched the knowledge base, so accuracy could not be checked.</div>';
          } else {
            acc.innerHTML = d.accuracy.map(function(a){
              var covered = (a.covered||[]).map(function(p){return '<div class="kp ok">âœ“ '+esc(p)+'</div>';}).join('');
              var missed = (a.missed||[]).map(function(p){return '<div class="kp no">âœ— '+esc(p)+'</div>';}).join('');
              return '<div class="acc-item"><div class="acc-q">'+esc(a.client_question)+'</div><div class="acc-meta">matched: '+esc(a.matched_question)+' Â· '+esc(a.confidence)+' Â· '+a.accuracy+'/100</div><div class="acc-boxes"><div class="acc-box"><div class="box-label">Analyst Transcript</div><div class="box-text">"'+esc(a.agent_answer)+'"</div></div><div class="acc-box ideal"><div class="box-label">Ideal Answer</div><div class="box-text">"'+esc(a.ideal_answer)+'"</div></div></div>'+covered+missed+'</div>';
            }).join('');
          }

          var tok = document.getElementById('tokencost');
          var u = d.token_usage;
          if (!u) {
            tok.innerHTML = '<div class="placeholder">No token data available.</div>';
          } else {
            var rows = (u.calls||[]).map(function(c){
              return '<div class="row-line"><div class="rl-text">'+esc(c.label)+'</div><div class="rl-sub">'+c.input+' in Â· '+c.output+' out Â· '+(c.input+c.output)+' total</div></div>';
            }).join('');
            rows += '<div class="row-line"><div class="rl-text">Total</div><div class="rl-sub">'+u.input+' in Â· '+u.output+' out Â· <strong>'+u.total+' tokens</strong></div></div>';
            tok.innerHTML = rows + '<div class="acc-meta">Gemma only â€” sentiment and rule/accuracy checks run locally with no tokens.</div>';
          }

          var tenseBlock = document.getElementById('tenseBlock');
          var tense = document.getElementById('tense');
          tenseBlock.style.display = 'block';
          if (!d.intense || d.intense.length===0) {
            tense.innerHTML = '<div class="placeholder">None &mdash; the call stayed calm.</div>';
          } else {
            tense.innerHTML = d.intense.map(function(m){
              return '<div class="tense-item"><div class="who">Turn '+m.turn+': '+esc(m.speaker)+'</div><div class="val">sentiment '+m.sentiment+'</div></div>';
            }).join('');
          }
        }
      </script>
    </body>
    </html>
    """.replace("%SAMPLE%", _sample_json())


def _sample_json():
    import json
    return json.dumps(SAMPLE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
