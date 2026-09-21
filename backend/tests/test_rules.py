"""Unit tests for the deterministic rule-based clause detector (offline demo fallback)."""
from __future__ import annotations

from app.engine.rules import rule_analyze

_EMPLOYMENT_PAGES = [
    (
        "EMPLOYMENT AGREEMENT between Acme Technologies Pvt. Ltd and Alex Sharma.\n\n"
        "7.1 Confidentiality: During and after employment, Employee shall not disclose confidential "
        "information, including trade secrets and client lists.\n"
        "7.2 Intellectual property: All inventions and works made for hire are the Company's property.\n"
    ),
    (
        "11.1 Notice of resignation: 30 days written notice. 11.2 Training costs: Employee shall repay "
        "training cost of Rs. 50,000 if resigning within 18 months.\n"
        "12.1 Non-compete: During employment and for 12 months after, Employee shall not work for a "
        "competing business within 50 km.\n"
    ),
]


def test_detects_common_employment_clauses():
    analysis = rule_analyze(_EMPLOYMENT_PAGES, document_type="Employment Agreement", title="sample.txt")
    titles = [c.title for c in analysis.important_clauses]
    assert "Confidentiality obligation" in titles
    assert "Intellectual property assignment" in titles
    assert "Notice period" in titles
    assert "Repayment obligation" in titles
    assert "Non-compete restriction" in titles


def test_attention_is_deterministic_for_rules():
    analysis = rule_analyze(_EMPLOYMENT_PAGES)
    by_title = {c.title: c for c in analysis.important_clauses}
    # Repayment (Rs. 50,000, "shall repay") is a high-attention signal.
    assert by_title["Repayment obligation"].importance.value == "HIGH"
    # Non-compete with 12 months scores HIGH (>= 60 pts).
    assert by_title["Non-compete restriction"].importance.value == "HIGH"
    # 30 days notice is MEDIUM.
    assert by_title["Notice period"].importance.value == "MEDIUM"


def test_evidence_is_verbatim_and_seeded():
    analysis = rule_analyze(_EMPLOYMENT_PAGES)
    repayment = next(c for c in analysis.important_clauses if c.title == "Repayment obligation")
    assert "shall repay" in repayment.evidence.lower()
    assert repayment.source_page == 2
    assert repayment.source_section in {"11", "11.2"}
    summary = analysis.attention_summary
    assert summary.high + summary.medium + summary.low == len(analysis.important_clauses)


def test_deduplicates_repeated_sentences():
    repeated = ["Arbitration: any dispute shall be resolved by binding arbitration."] * 4
    analysis = rule_analyze(repeated)
    titles = [c.title for c in analysis.important_clauses]
    assert titles.count("Arbitration clause") == 1


def test_empty_text_yields_no_clauses():
    analysis = rule_analyze(["Lorem ipsum dolor sit amet, consectetur adipiscing elit."])
    assert analysis.important_clauses == []
    assert analysis.attention_summary.high + analysis.attention_summary.medium + analysis.attention_summary.low == 0