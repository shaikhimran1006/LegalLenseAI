"""Deterministic attention engine tests."""
from __future__ import annotations

from app.db import demo as demo_data
from app.engine.attention import (
    apply_attention,
    compute_attention_summary,
    detect_context_profile,
    rank_clauses,
    score_clause,
    score_to_importance,
)
from app.schemas.models import Clause, Importance


def _clause(title, category, evidence, importance="MEDIUM"):
    return Clause(
        title=title,
        category=category,
        importance=importance,
        plain_language="",
        why_it_matters="",
        evidence=evidence,
        source_page=1,
        source_section="",
        confidence="HIGH",
    )


def test_training_repayment_scores_high():
    clause = _clause(
        "Training Repayment",
        "financial obligation",
        "The Employee shall repay the training cost of Rs. 50,000. Interest at 18% per annum.",
    )
    updated, score = apply_attention(clause)
    assert score >= 55
    assert updated.importance == Importance.HIGH


def test_benign_expense_clause_scores_low():
    clause = _clause(
        "Business Expenses",
        "other",
        "The Company shall reimburse reasonable business expenses against receipts.",
    )
    updated, _score = apply_attention(clause)
    assert updated.importance == Importance.LOW


def test_notice_90_days_high_30_days_medium():
    high = apply_attention(_clause("Notice Period", "notice", "ninety (90) days' written notice"))[0]
    medium = apply_attention(_clause("Notice Period", "notice", "thirty (30) days' written notice"))[0]
    assert high.importance == Importance.HIGH
    assert medium.importance == Importance.MEDIUM


def test_non_compete_high():
    clause = _clause(
        "Non-Compete",
        "non-compete",
        "For 12 months the Employee shall not engage in any competing business.",
    )
    updated, _ = apply_attention(clause)
    assert updated.importance == Importance.HIGH


def test_arbitration_high():
    clause = _clause("Arbitration", "arbitration", "binding arbitration, award shall be final and binding")
    updated, _ = apply_attention(clause)
    assert updated.importance == Importance.HIGH


def test_context_resignation_ranks_notice_training_first():
    clauses = [
        _clause("Leave Policy", "other", "15 days paid leave", importance="LOW"),
        _clause("Notice Period", "notice", "30 days notice", importance="MEDIUM"),
        _clause("Training Repayment", "financial obligation", "shall repay 50000 on resign", importance="HIGH"),
        _clause("Annual Review", "other", "annual performance review", importance="LOW"),
    ]
    ranked = rank_clauses(clauses, "I am considering resigning after 8 months")
    titles = [c.title for c, _, _ in ranked]
    assert titles[1] in ("Notice Period", "Training Repayment")
    assert titles[0] in ("Training Repayment", "Notice Period")


def test_context_profile_detection():
    assert detect_context_profile("I am planning to rent this property").label.lower().find("rent") != -1
    assert detect_context_profile("taking this loan").label.lower().find("loan") != -1
    assert detect_context_profile("").label == ""


def test_demo_seed_attention_counts_are_consistent():
    """The seed analysis must equal what the deterministic engine computes, so
    demo mode and a live re-run agree."""
    analysis = demo_data.demo_analysis("sample_employment")
    clauses = [Clause.model_validate(c) for c in analysis["important_clauses"]]
    updated, _ = zip(*(apply_attention(c) for c in clauses))
    summary = compute_attention_summary(list(updated))
    assert summary.high == 3
    assert summary.medium == 6
    assert summary.low == 11


def test_score_clip_upper_bound():
    clause = _clause("x", "penalty", "penalty damages equal double damages non-refundable indemnity")
    assert score_clause(clause) <= 100