"""Pydantic schemas for structured AI output and API request/response models."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Importance(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AttentionSummary(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0


class Clause(BaseModel):
    title: str = Field(description="Short human-readable title, e.g. 'Training Repayment'")
    category: str = Field(description="Category from the controlled vocabulary")
    importance: Importance = Field(description="Deterministic attention level; corrected server-side")
    plain_language: str = Field(description="Plain-language explanation, no legal jargon")
    why_it_matters: str = Field(description="Practical significance, without giving legal advice")
    source_page: int = Field(default=0, description="1-based page number in the uploaded document")
    source_section: str = Field(default="", description="Section/clause number in the document as written, e.g. '11.2'")
    evidence: str = Field(description="Short verbatim quote from the document supporting this clause")
    confidence: Confidence = Field(default=Confidence.MEDIUM)

    @field_validator("source_page")
    @classmethod
    def page_not_negative(cls, v: int) -> int:
        return max(v, 0)


class DocumentAnalysis(BaseModel):
    document_type: str = Field(default="")
    document_title: str = Field(default="")
    parties: list[str] = Field(default_factory=list)
    effective_date: str = Field(default="")
    expiration_date: str = Field(default="")
    jurisdiction: str = Field(default="")
    important_dates: list[str] = Field(default_factory=list)
    financial_amounts: list[str] = Field(default_factory=list)
    important_clauses: list[Clause] = Field(default_factory=list)
    attention_summary: AttentionSummary = Field(default_factory=AttentionSummary)


class Question(BaseModel):
    question: str = Field(description="A focused question worth asking a legal professional")


class ActionPack(BaseModel):
    important_clauses: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    info_to_collect: list[str] = Field(default_factory=list)
    things_to_clarify: list[str] = Field(default_factory=list)
    preparation_checklist: list[str] = Field(default_factory=list)
    questions_for_legal_professional: list[Question] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    area: str
    contract_a_value: str = ""
    contract_b_value: str = ""
    change: Literal["Significant", "Review", "Minor", "Added", "Removed", "Modified"] = "Review"
    a_source_page: int = 0
    a_source_section: str = ""
    b_source_page: int = 0
    b_source_section: str = ""


class ComparisonResult(BaseModel):
    comparison_rows: list[ComparisonRow] = Field(default_factory=list)
    important_changes: list[str] = Field(default_factory=list)
    clauses_added: list[str] = Field(default_factory=list)
    clauses_removed: list[str] = Field(default_factory=list)
    clauses_modified: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    answer: str = Field(description="Answer grounded only in the provided document evidence")
    evidence: list[EvidenceRef] = Field(default_factory=list)
    insufficient: bool = False


class EvidenceRef(BaseModel):
    page: int = 0
    section: str = ""
    quote: str = ""


class ContextRequest(BaseModel):
    context: str = Field(default="", max_length=2000, description="User's situation, e.g. 'I am considering resigning after 8 months.'")


class RankedClause(BaseModel):
    clause: Clause
    relevance: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: str = Field(default="", max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question must not be blank")
        return v.strip()


class ExplainClauseRequest(BaseModel):
    clause_id: Optional[str] = None
    title: Optional[str] = None


class ActionPackRequest(BaseModel):
    context: str = Field(default="", max_length=2000)


class CompareRequest(BaseModel):
    document_a_id: str
    document_b_id: str


class UploadResponse(BaseModel):
    id: str
    filename: str
    extension: str
    page_count: int
    size: int
    status: Literal["created", "analyzed"]
    context: str = ""


class AnalyzeResponse(BaseModel):
    document_id: str
    analysis: DocumentAnalysis
    mode: Literal["ai", "demo"]
    duration_ms: int = 0


class AskResponse(BaseModel):
    document_id: str
    answer: Answer
    mode: Literal["ai", "demo"] = "ai"


class ActionPackResponse(BaseModel):
    document_id: str
    action_pack: ActionPack
    mode: Literal["ai", "demo"] = "ai"


class CompareResponse(BaseModel):
    comparison_id: str
    document_a: str
    document_b: str
    result: ComparisonResult
    mode: Literal["ai", "demo"] = "ai"


class ApiError(BaseModel):
    detail: str
    code: str = "error"


class HealthResponse(BaseModel):
    status: Literal["UP"] = "UP"
    version: str = ""
    demo_mode: bool = False
    ai_configured: bool = False


def sanitize_analysis(result: Any) -> DocumentAnalysis:
    """Coerce a parsed AI payload into a valid DocumentAnalysis, dropping invalid fields."""
    if not isinstance(result, dict):
        result = {}
    result.setdefault("document_type", "")
    result.setdefault("document_title", "")
    result.setdefault("parties", [])
    result.setdefault("effective_date", "")
    result.setdefault("expiration_date", "")
    result.setdefault("jurisdiction", "")
    result.setdefault("important_dates", [])
    result.setdefault("financial_amounts", [])
    important_clauses = result.get("important_clauses", [])
    if not isinstance(important_clauses, list):
        important_clauses = []
    result["important_clauses"] = [_coerce_clause(c) for c in important_clauses if isinstance(c, dict)]
    return DocumentAnalysis.model_validate(result)


def _coerce_clause(raw: dict) -> dict:
    for key in ("title", "category", "plain_language", "why_it_matters", "evidence", "source_section"):
        if not isinstance(raw.get(key), str):
            raw[key] = ""
    if not isinstance(raw.get("importance"), str) or raw["importance"] not in {"HIGH", "MEDIUM", "LOW"}:
        raw["importance"] = "LOW"
    if not isinstance(raw.get("confidence"), str) or raw["confidence"] not in {"HIGH", "MEDIUM", "LOW"}:
        raw["confidence"] = "MEDIUM"
    if not isinstance(raw.get("source_page"), int):
        try:
            raw["source_page"] = int(float(raw.get("source_page", 0) or 0))
        except (TypeError, ValueError):
            raw["source_page"] = 0
    raw["source_page"] = max(raw["source_page"], 0)
    raw["title"] = raw["title"].strip()[:120]
    raw["category"] = raw["category"].strip()[:60]
    raw["evidence"] = raw["evidence"].strip()[:1000]
    return raw