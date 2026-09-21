"""Deterministic Legal Attention engine.

Gemini proposes clauses and writes explanations, but attention levels are
computed here from the clause evidence using deterministic rules. This stops the
LLM from arbitrarily inventing risk scores while keeping explanations grounded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.models import AttentionSummary, Clause, Importance

# (regex, points, label that will be reported in reasons)
_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"non-refundable", re.I), 55, "non-refundable payment"),
    (re.compile(r"late\s+fee|penalty|penalties|penal(?:ise|ize)", re.I), 60, "penalty clause"),
    (re.compile(r"interest\s+(at|of|@)|per\s+annum|%?\s*(?:annual|monthly)\s+interest", re.I), 55, "interest obligation"),
    (re.compile(r"shall\s+repay|repayment|reimburse\s+(?:the|to)?\s*(?:company|employer)|costs?\s+of\s+training", re.I), 55, "repayment obligation"),
    (re.compile(r"indemnif|indemnity|indemnif(?:ies|y)", re.I), 65, "indemnity"),
    (re.compile(r"hold\s+harmless", re.I), 60, "hold harmless"),
    (re.compile(r"arbitrat", re.I), 55, "arbitration requirement"),
    (re.compile(r"auto\s*-?renew|renew(s|al)?\s+automatically", re.I), 60, "automatic renewal"),
    (re.compile(r"lock\s*-?in", re.I), 65, "lock-in period"),
    (re.compile(r"non\s*-?compete|noncompetition", re.I), 60, "non-compete"),
    (re.compile(r"non\s*-?solicit", re.I), 50, "non-solicitation"),
    (re.compile(r"waive(s|d)?\s+(any\s+)?rights?|waiver", re.I), 45, "waiver of rights"),
    (re.compile(r"unlimited\s+liability|broad\s+liability|entire\s+liability", re.I), 55, "broad liability"),
    (re.compile(r"terminat(?:e|ion|ed)?\s+without\s+cause|at\s+will", re.I), 45, "termination without cause"),
    (re.compile(r"sole\s+discretion|arbitrary", re.I), 40, "sole discretion"),
    (re.compile(r"damages\s+equal|double\s+damages|treble", re.I), 65, "multiplied damages"),
    (re.compile(r"confidential|confidentiality", re.I), 35, "confidentiality"),
    (re.compile(r"intellectual\s+property|invention|work(s)?\s+made\s+for\s+hire", re.I), 45, "IP assignment"),
    (re.compile(r"non\s*-?solicit", re.I), 50, "non-solicitation"),
    (re.compile(r"survive|surv(i)?(?:al|es)", re.I), 35, "survival after termination"),
    (re.compile(r"damages?\s+(?:cap|capped|limit|limited)", re.I), 45, "damages cap"),
    (re.compile(r"exclusiv|sole\s+remedy", re.I), 45, "exclusive remedy"),
]

# Category baselines (points) applied even without a keyword hit.
_CATEGORY_BASE: dict[str, int] = {
    "penalty": 55,
    "interest": 50,
    "indemnity": 60,
    "non-compete": 55,
    "non-solicitation": 45,
    "arbitration": 45,
    "financial obligation": 45,
    "liability": 45,
    "renewal": 45,
    "termination": 40,
    "notice": 35,
    "confidentiality": 35,
    "intellectual property": 40,
    "payment": 40,
    "insurance": 30,
    "warranty": 30,
    "default": 40,
    "dispute resolution": 35,
    "other": 25,
}

# Notice-period length rules. Tolerates writing like "(90) days" or "90 (ninety) days".
_NOTICE_DAYS = re.compile(r"(\d{1,3})[^a-z0-9]{0,3}days?(?!\w)", re.I)


def score_clause(clause: Clause, category: str | None = None, evidence: str | None = None) -> int:
    """Deterministic attention score 0..100 for a clause."""
    cat = (category or clause.category or "").strip().lower()
    text = evidence or clause.evidence or ""
    title = clause.title or ""
    full = f"{cat}\n{title}\n{text}"

    score = _CATEGORY_BASE.get(cat, 25)

    for pattern, points, _label in _PATTERNS:
        if pattern.search(full):
            score = max(score, points)

    # Long notice periods are worth raising attention.
    m = _NOTICE_DAYS.search(full)
    if m:
        days = int(m.group(1))
        if "notice" in cat or "notices" in title.lower():
            if days >= 60:
                score = max(score, 55)
            elif days >= 30:
                score = max(score, 40)

    # Amounts adjacent to obligations push score up a bit.
    if re.search(r"[\u20b9₹]|rs\.?|inr", full, re.I):
        score = min(100, score + 5)

    return min(100, score)


def score_to_importance(score: int) -> Importance:
    if score >= 55:
        return Importance.HIGH
    if score >= 35:
        return Importance.MEDIUM
    return Importance.LOW


def apply_attention(clause: Clause) -> tuple[Clause, int]:
    """Return a copy of the clause with deterministic importance applied."""
    score = score_clause(clause)
    importance = score_to_importance(score)
    updated = clause.model_copy(update={"importance": importance})
    return updated, score


def apply_attention_to_all(clauses: list[Clause]) -> tuple[list[Clause], dict[str, int]]:
    scores: dict[str, int] = {}
    updated = []
    for clause in clauses:
        c, s = apply_attention(clause)
        updated.append(c)
        scores[c.title] = s
    return updated, scores


def compute_attention_summary(clauses: list[Clause]) -> AttentionSummary:
    summary = {"high": 0, "medium": 0, "low": 0}
    for clause in clauses:
        key = clause.importance.value.lower()
        summary[key] = summary.get(key, 0) + 1
    return AttentionSummary.model_validate(summary)


@dataclass
class ContextProfile:
    """A detected user situation that boosts certain clause categories."""

    label: str = ""
    boosts: dict[str, int] = field(default_factory=dict)

    def score(self, category: str) -> int:
        return self.boosts.get(category, 0)


_SITUATION_KEYWORDS: list[tuple[str, ContextProfile]] = [
    (
        "resign",
        ContextProfile(
            label="Considering resigning",
            boosts={
                "notice": 30, "termination": 25, "financial obligation": 20,
                "non-solicitation": 15, "confidentiality": 10,
                "intellectual property": 10, "non-compete": 15,
            },
        ),
    ),
    (
        "renting|rent|lease|landlord|deposit",
        ContextProfile(
            label="Planning to rent",
            boosts={
                "financial obligation": 25, "notice": 15, "termination": 15,
                "renewal": 20, "penalty": 15, "liability": 10, "maintenance": 20,
            },
        ),
    ),
    (
        "loan|borrow|finance|emi|repay",
        ContextProfile(
            label="Considering a loan",
            boosts={
                "interest": 30, "penalty": 25, "financial obligation": 25,
                "default": 25, "termination": 10,
            },
        ),
    ),
    (
        "insurance|policy|claim|coverage",
        ContextProfile(
            label="Checking insurance",
            boosts={
                "insurance": 30, "warranty": 15, "liability": 15,
                "renewal": 15, "exclusions": 20,
            },
        ),
    ),
    (
        "business|vendor|client|customer|service|supplier|contract",
        ContextProfile(
            label="Business arrangement",
            boosts={
                "liability": 25, "indemnity": 25, "arbitration": 15,
                "confidentiality": 15, "warranty": 15, "dispute resolution": 15,
            },
        ),
    ),
    (
        "notice|sued|compensation|consumer|refund|grievance",
        ContextProfile(
            label="Consumer or legal notice",
            boosts={
                "penalty": 20, "liability": 20, "dispute resolution": 20,
                "termination": 15, "payment": 15,
            },
        ),
    ),
]


def detect_context_profile(context: str) -> ContextProfile:
    if not context:
        return ContextProfile(label="")
    combined = context.lower()
    base = ContextProfile(label="General situation")
    for pattern, profile in _SITUATION_KEYWORDS:
        if re.search(pattern, combined):
            return profile
    return base


def rank_clauses(clauses: list[Clause], context: str = "") -> list[tuple[Clause, int, list[str]]]:
    """Rank clauses by relevance to the user's situation.

    Returns (clause, relevance, reasons). Never makes decisions for the user —
    it only prioritizes what to look at.
    """
    profile = detect_context_profile(context)
    ranked: list[tuple[Clause, int, list[str]]] = []
    for clause in clauses:
        score = score_clause(clause)
        base_importance_points = {"HIGH": 30, "MEDIUM": 15, "LOW": 0}[clause.importance.value]
        relevant_points = profile.score(clause.category.strip().lower())
        relevance = min(100, base_importance_points + relevant_points + score // 3)
        reasons: list[str] = []
        if relevant_points >= 20:
            reasons.append(f"Relevant to: {profile.label or 'your situation'}")
        if clause.importance == Importance.HIGH:
            reasons.append("High attention clause")
        ranked.append((clause, relevance, reasons))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked