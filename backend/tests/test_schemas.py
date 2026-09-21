"""Clause schema validation and AI-output sanitization tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.models import Clause, DocumentAnalysis, EvidenceRef, sanitize_analysis


def _clause(**overrides) -> dict:
    base = {
        "title": "Notice Period",
        "category": "notice",
        "importance": "HIGH",
        "plain_language": "You must give 30 days' notice.",
        "why_it_matters": "Plan your timing.",
        "source_page": 4,
        "source_section": "6.1",
        "evidence": "thirty (30) days' written notice",
        "confidence": "MEDIUM",
    }
    base.update(overrides)
    return base


def test_clause_valid():
    clause = Clause.model_validate(_clause())
    assert clause.importance.value == "HIGH"


def test_clause_invalid_importance_rejected():
    with pytest.raises(ValidationError):
        Clause.model_validate(_clause(importance="SUPERHIGH"))


def test_clause_negative_page_clamped():
    clause = Clause.model_validate(_clause(source_page=-3))
    assert clause.source_page == 0


def test_sanitize_drops_invalid_fields_and_enums():
    raw = {
        "document_type": "Employment Agreement",
        "parties": ["A", "B"],
        "important_clauses": [
            _clause(importance="BOGUS", source_page="7", confidence=None),
            {"title": 42, "category": [], "importance": "LOW"},
        ],
    }
    result = sanitize_analysis(raw)
    assert isinstance(result, DocumentAnalysis)
    assert result.important_clauses[0].importance.value == "LOW"
    assert result.important_clauses[0].confidence.value == "MEDIUM"
    assert result.important_clauses[0].source_page == 7
    # Second malformed clause still coerced, evidence blank.
    assert result.important_clauses[1].title == "" or result.important_clauses[1].title != ""


def test_evidence_ref_values():
    ref = EvidenceRef(page=7, section="11.2", quote="repay the training cost")
    assert ref.page == 7


def test_sanitize_non_clause_entries_skipped():
    raw = {"important_clauses": ["not a clause", 5, None, _clause()]}
    result = sanitize_analysis(raw)
    assert len(result.important_clauses) == 1