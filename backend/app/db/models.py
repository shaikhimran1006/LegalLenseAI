"""SQLAlchemy ORM models.

Analyses and clauses are cached as JSON columns (the free-tier friendly source of
truth for answering questions) while conversations and messages keep relational
shape with proper foreign keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True, default="public")
    filename: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(16), default="pdf")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    size: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[str] = mapped_column(String(64), default="other")
    status: Mapped[str] = mapped_column(String(32), default="created")  # created | analyzed
    mode: Mapped[str] = mapped_column(String(16), default="ai")  # ai | demo
    analysis_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    status_detail: Mapped[str] = mapped_column(String(255), default="")
    processed_text: Mapped[dict] = mapped_column(JSON, nullable=True)  # page text cache (in-memory persist)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped[Document] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=True)  # evidence refs etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True, default="public")
    document_a_id: Mapped[str] = mapped_column(String(64))
    document_b_id: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)