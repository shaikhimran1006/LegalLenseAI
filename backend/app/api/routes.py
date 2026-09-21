"""REST API routes for LegalLens AI."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db_dependency, get_workspace_id, rate_limit
from app.core.config import get_settings
from app.db import demo as demo_data
from app.db import repository
from app.engine.attention import rank_clauses
from app.schemas.models import (
    ActionPackRequest,
    AnalyzeResponse,
    AskRequest,
    AskResponse,
    CompareRequest,
    CompareResponse,
    ExplainClauseRequest,
    HealthResponse,
    UploadResponse,
)
from app.services import action_pack as action_pack_service
from app.services import analysis as analysis_service
from app.services import compare as compare_service
from app.services import documents as documents_service
from app.services import qa as qa_service

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="UP",
        version=settings.app_version,
        demo_mode=bool(settings.force_demo or not settings.real_ai_available),
        ai_configured=settings.real_ai_available,
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.post("/documents/upload", response_model=UploadResponse, status_code=201, dependencies=[Depends(rate_limit())])
def upload_document(
    file: UploadFile = File(...),
    context: str = Form(default="other"),
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    documents_service.validate_upload(file, settings.max_upload_bytes)
    data = documents_service.load_upload_bytes(file, settings.max_upload_bytes)
    context = (context or "other").strip().lower()[:40] or "other"
    return documents_service.process_upload(
        db, file=file, data=data, context=context, workspace_id=workspace_id, max_bytes=settings.max_upload_bytes
    )


@router.get("/documents")
def list_documents(db: Session = Depends(get_db_dependency()), workspace_id: str = Depends(get_workspace_id)):
    rows = repository.list_documents(db, workspace_id)
    return [
        {
            "id": row.id,
            "filename": row.filename,
            "extension": row.extension,
            "page_count": row.page_count,
            "size": row.size,
            "context": row.context,
            "status": row.status,
            "mode": row.mode,
            "status_detail": row.status_detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "analysis": _analysis_preview(row.analysis_json),
        }
        for row in rows
    ]


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    row = repository.get_document(db, document_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_response(row)


@router.post("/documents/{document_id}/analyze", response_model=AnalyzeResponse, dependencies=[Depends(rate_limit())])
def analyze_document(
    document_id: str,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    return analysis_service.run_analysis(db, document_id=document_id, workspace_id=workspace_id, settings=settings)


@router.get("/documents/{document_id}/clauses")
def get_clauses(
    document_id: str,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    row = repository.get_document(db, document_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not row.analysis_json:
        raise HTTPException(status_code=409, detail="Document has not been analyzed yet.")
    clauses = row.analysis_json.get("important_clauses", [])
    valid = [c for c in (repository2clause(x) for x in clauses) if c is not None]
    ranked = rank_clauses(valid, context="")
    return {
        "document_id": document_id,
        "clauses": [c for c, _, _ in ranked],
        "attention_summary": row.analysis_json.get("attention_summary", {"high": 0, "medium": 0, "low": 0}),
    }


def repository2clause(raw) :
    from app.schemas.models import Clause

    try:
        return Clause.model_validate(raw)
    except Exception:
        return None


@router.post("/documents/{document_id}/ask", response_model=AskResponse, dependencies=[Depends(rate_limit())])
def ask_question(
    document_id: str,
    payload: AskRequest,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    return qa_service.answer_question(
        db,
        document_id=document_id,
        workspace_id=workspace_id,
        question=payload.question,
        context=payload.context,
        settings=settings,
    )


@router.get("/documents/{document_id}/context-ranking")
def context_ranking(
    document_id: str,
    context: str = "",
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    row = repository.get_document(db, document_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not row.analysis_json:
        raise HTTPException(status_code=409, detail="Document has not been analyzed yet.")
    clauses_with = []
    for c in row.analysis_json.get("important_clauses", []):
        from app.schemas.models import Clause

        try:
            clauses_with.append(Clause.model_validate(c))
        except Exception:
            continue
    ranked = rank_clauses(clauses_with, context)
    return {
        "context": context,
        "profile": {"label": _profile_label(context)},
        "ranked_clauses": [
            {"clause": c.model_dump(mode="json"), "relevance": r, "reasons": reasons}
            for c, r, reasons in ranked
        ],
    }


def _profile_label(context: str) -> str:
    if not context:
        return ""
    from app.engine.attention import detect_context_profile

    return detect_context_profile(context).label


@router.post("/documents/{document_id}/action-pack", dependencies=[Depends(rate_limit())])
def generate_action_pack(
    document_id: str,
    payload: ActionPackRequest,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    return action_pack_service.build_action_pack(
        db,
        document_id=document_id,
        workspace_id=workspace_id,
        context=payload.context,
        settings=settings,
    )


@router.post("/documents/{document_id}/explain", dependencies=[Depends(rate_limit())])
def explain_clause(
    document_id: str,
    payload: ExplainClauseRequest,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    """Explain a specific clause using its structured content.

    This path never needs to re-read the whole document; it re-sends only the
    structured clause to Gemini, keeping free-tier usage low.
    """
    from app.ai import prompts
    from app.ai.client import GeminiClient
    from app.schemas.models import Clause

    row = repository.get_document(db, document_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not row.analysis_json:
        raise HTTPException(status_code=409, detail="Document has not been analyzed yet.")

    clause = _find_clause(row.analysis_json, payload)
    if clause is None:
        raise HTTPException(status_code=404, detail="Clause not found.")

    client = GeminiClient()
    if settings.force_demo or not client.available:
        return {"clause": clause.model_dump(mode="json"), "mode": "demo"}

    prompt = prompts.explain_clause_prompt(clause.model_dump(mode="json"))
    try:
        text = client.generate_text(prompt, max_output_tokens=1600, temperature=0.3)
    except Exception:
        raise HTTPException(status_code=502, detail="AI explanation failed, possibly due to free-tier quota. Please try again shortly.")
    explained = clause.model_dump(mode="json")
    explained["plain_language"] = text
    return {"clause": explained, "mode": "ai"}


def _find_clause(analysis_json: dict, payload: ExplainClauseRequest):
    from app.schemas.models import Clause

    for raw in analysis_json.get("important_clauses", []):
        try:
            clause = Clause.model_validate(raw)
        except Exception:
            continue
        if payload.clause_id and clause.title.lower() == payload.clause_id.lower():
            return clause
        if payload.title and clause.title.lower() == payload.title.lower():
            return clause
    return None


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

@router.get("/documents/{document_id}/conversation")
def get_conversation(
    document_id: str,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    row = repository.get_document(db, document_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    conv = repository.get_or_create_conversation(db, document_id)
    messages = repository.conversation_messages(db, conv.id)
    return {
        "document_id": document_id,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "payload": m.payload_json}
            for m in messages
        ],
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@router.post("/compare", response_model=CompareResponse, dependencies=[Depends(rate_limit())])
def compare_documents(
    payload: CompareRequest,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    return compare_service.compare_documents(
        db,
        document_a_id=payload.document_a_id,
        document_b_id=payload.document_b_id,
        workspace_id=workspace_id,
        settings=settings,
    )


@router.get("/comparisons/{comparison_id}")
def get_comparison(
    comparison_id: str,
    db: Session = Depends(get_db_dependency()),
    workspace_id: str = Depends(get_workspace_id),
):
    row = repository.get_comparison(db, comparison_id, workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return {
        "comparison_id": row.id,
        "document_a": row.document_a_id,
        "document_b": row.document_b_id,
        "result": row.result_json,
        "mode": row.mode,
    }


# ---------------------------------------------------------------------------
# Demo support
# ---------------------------------------------------------------------------

@router.get("/demo/documents")
def demo_documents():
    return {
        "items": demo_data.list_demo_documents(),
        "fictional_notice": demo_data.load_seed().get("_meta", {}).get("fictional_notice", ""),
    }


@router.get("/demo/documents/{document_id}")
def demo_document_detail(document_id: str):
    doc = demo_data.get_demo_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Sample document not found.")
    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "extension": doc["extension"],
        "context": doc["context"],
        "page_count": doc["page_count"],
        "size": 200_000,
        "status": "analyzed",
        "mode": "demo",
        "pages": doc.get("pages", []),
        "analysis": doc.get("analysis"),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _analysis_preview(analysis_json) -> Optional[dict]:
    if not analysis_json:
        return None
    return {
        "document_type": analysis_json.get("document_type"),
        "document_title": analysis_json.get("document_title"),
        "attention_summary": analysis_json.get("attention_summary"),
        "clause_count": len(analysis_json.get("important_clauses", [])),
    }


def _document_response(row):
    return {
        "id": row.id,
        "filename": row.filename,
        "extension": row.extension,
        "page_count": row.page_count,
        "size": row.size,
        "context": row.context,
        "status": row.status,
        "mode": row.mode,
        "status_detail": row.status_detail,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "analysis": row.analysis_json,
        "pages": (row.processed_text or {}).get("pages", []),
    }