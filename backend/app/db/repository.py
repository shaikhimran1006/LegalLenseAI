"""Thin data-access layer over SQLAlchemy."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import Comparison, Document, Message, Conversation

DEFAULT_WORKSPACE = "public"


def create_document(
    db: DbSession,
    *,
    filename: str,
    extension: str,
    page_count: int,
    size: int,
    context: str,
    workspace_id: str = DEFAULT_WORKSPACE,
) -> Document:
    doc = Document(
        workspace_id=workspace_id,
        filename=filename,
        extension=extension,
        page_count=page_count,
        size=size,
        context=context or "other",
        status="created",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: DbSession, document_id: str, workspace_id: str = DEFAULT_WORKSPACE) -> Optional[Document]:
    doc = db.scalar(
        select(Document).where(Document.id == document_id, Document.workspace_id == workspace_id)
    )
    if doc is None and document_id.startswith("sample"):
        doc = db.scalar(select(Document).where(Document.id == document_id))
    return doc


def list_documents(db: DbSession, workspace_id: str = DEFAULT_WORKSPACE, limit: int = 50) -> list[Document]:
    rows = db.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    return list(rows)


def save_analysis(
    db: DbSession,
    document: Document,
    *,
    analysis_json: dict,
    status: str,
    mode: str,
    status_detail: str = "",
    processed_text: Optional[dict] = None,
) -> Document:
    document.analysis_json = analysis_json
    document.status = status
    document.mode = mode
    document.status_detail = status_detail
    document.processed_text = processed_text
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: DbSession, document: Document) -> None:
    db.delete(document)
    db.commit()


def get_or_create_conversation(db: DbSession, document_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.document_id == document_id)
    )
    if conversation is None:
        conversation = Conversation(document_id=document_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def add_message(db: DbSession, conversation_id: str, role: str, content: str, payload: Optional[dict] = None) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        payload_json=payload,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def conversation_messages(db: DbSession, conversation_id: str, limit: int = 100) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
    )


def save_comparison(
    db: DbSession,
    *,
    document_a_id: str,
    document_b_id: str,
    result_json: dict,
    mode: str,
    workspace_id: str = DEFAULT_WORKSPACE,
) -> Comparison:
    comparison = Comparison(
        workspace_id=workspace_id,
        document_a_id=document_a_id,
        document_b_id=document_b_id,
        result_json=result_json,
        mode=mode,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return comparison


def get_comparison(db: DbSession, comparison_id: str, workspace_id: str = DEFAULT_WORKSPACE) -> Optional[Comparison]:
    return db.scalar(
        select(Comparison).where(Comparison.id == comparison_id, Comparison.workspace_id == workspace_id)
    )


def ensure_demo_documents(db: DbSession) -> int:
    """Create in-DB rows for sample documents so all services work uniformly.

    Sample rows are clearly marked mode='demo'. Their analysis is loaded from the
    curated seed (cached output), so no Gemini calls are required.
    Removes any legacy seed rows left over from older (renamed) seed ids.
    """
    from app.db import demo as demo_data
    from app.schemas.models import sanitize_analysis

    stale = db.scalars(select(Document).where(Document.id.like("demo_%"))).all()
    for row in stale:
        db.delete(row)

    created = 0
    for item in demo_data.list_demo_documents():
        existing = db.scalar(select(Document).where(Document.id == item["id"]))
        if existing is not None:
            continue
        analysis = sanitize_analysis(demo_data.demo_analysis(item["id"]) or {})
        pages = demo_data.demo_pages(item["id"])
        doc = Document(
            id=item["id"],
            workspace_id=DEFAULT_WORKSPACE,
            filename=item["filename"],
            extension=item["extension"],
            page_count=item["page_count"],
            size=item["size"],
            context=item["context"],
            status="analyzed",
            mode="demo",
            status_detail="Sample · pre-computed analysis",
            analysis_json=analysis.model_dump(mode="json"),
            processed_text={"pages": pages, "text": "\n\n".join(pages)},
        )
        db.add(doc)
        created += 1
    if stale or created:
        db.commit()
    return created