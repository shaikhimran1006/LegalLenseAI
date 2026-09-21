"""Deterministic rule-based clause detection (DEMO / no-key mode).

When no Gemini key is configured and a document has no built-in demo seed, we
cannot call a model — but a full UX still requires an analysis. This module
extracts candidate clauses from plain text using carefully-scoped rules and the
same attention engine used everywhere else, so an uploaded document can still be
analyzed, discussed and compared entirely offline.

Transparency: rule-extracted clauses are explanatory templates (never invented
obligations); evidence is always a verbatim sentence from the document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.engine.attention import apply_attention_to_all, compute_attention_summary
from app.engine.retrieval import _SECTION_PATTERN
from app.schemas.models import Clause, DocumentAnalysis

MAX_RULE_CLAUSES = 12
_MAX_EVIDENCE_CHARS = 420

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₹$€£])")


@dataclass(frozen=True)
class Rule:
    title: str
    category: str
    pattern: re.Pattern[str]
    plain_language: str
    why_it_matters: str


_RULES: tuple[Rule, ...] = (
    Rule(
        title="Notice period",
        category="notice",
        pattern=re.compile(r"\b\d{1,3}\s*(?:\([^)]*\)\s*)?days?(?:\s+written)?\s+notice", re.I),
        plain_language=(
            "This clause fixes how many days of advance written notice either side must give "
            "to end or change the agreement."
        ),
        why_it_matters="Missing a notice deadline is one of the most common ways to be held to a term you meant to avoid.",
    ),
    Rule(
        title="Non-compete restriction",
        category="non-compete",
        pattern=re.compile(r"non\s*-?\s*compete|noncompetition", re.I),
        plain_language=(
            "This clause restricts you from working for, or starting, a competing business for a "
            "set time, area, or role after the agreement ends."
        ),
        why_it_matters="Non-compete limits can affect your next job or business; the area, duration and scope matter a lot.",
    ),
    Rule(
        title="Non-solicitation restriction",
        category="non-solicitation",
        pattern=re.compile(r"non\s*-?\s*solicit", re.I),
        plain_language=(
            "This clause restricts you from approaching, poaching or doing certain business with the "
            "other party's clients, customers or employees."
        ),
        why_it_matters="It limits how you can use the relationships you built, even after the agreement ends.",
    ),
    Rule(
        title="Repayment obligation",
        category="financial obligation",
        pattern=re.compile(r"shall\s+repay|repayment|reimburse\s+the\s+(company|employer)|costs?\s+of\s+training|training\s+(?:cost|fee|expense)", re.I),
        plain_language=(
            "The agreement makes you repay a cost to the other party, often a training, relocation or "
            "hiring cost, usually if you leave early."
        ),
        why_it_matters="Repayment amounts can be large and the trigger conditions are easy to misunderstand.",
    ),
    Rule(
        title="Confidentiality obligation",
        category="confidentiality",
        pattern=re.compile(r"confidentialit|confidential\s+information", re.I),
        plain_language=(
            "This clause defines what information must be kept secret and how long that duty lasts."
        ),
        why_it_matters="The definition of 'confidential' and its duration determine what you may and may not share later.",
    ),
    Rule(
        title="Intellectual property assignment",
        category="intellectual property",
        pattern=re.compile(r"intellectual\s+property|invention|work\s+made\s+for\s+hire", re.I),
        plain_language=(
            "This clause says who owns the ideas, code, designs or other IP you create during the relationship."
        ),
        why_it_matters="If everything you build is assigned, work you do on the side may also be affected.",
    ),
    Rule(
        title="Penalty or late fee",
        category="penalty",
        pattern=re.compile(r"late\s+fee|penalt(?:y|ies)|penal(?:ise|ize)", re.I),
        plain_language="This clause sets financial consequences for paying late or failing to do something on time.",
        why_it_matters="Penalties can apply automatically; check whether there is any grace, cure or notice period.",
    ),
    Rule(
        title="Interest obligation",
        category="interest",
        pattern=re.compile(r"interest\s+(?:at|of|@)|per\s+annum|(?:annual|monthly)\s+interest", re.I),
        plain_language="This clause sets a rate of interest, typically charged on late payments or outstanding sums.",
        why_it_matters="Even small interest rates add up on long-owed balances; confirm how and when it is computed.",
    ),
    Rule(
        title="Indemnity obligation",
        category="indemnity",
        pattern=re.compile(r"indemnif|hold\s+harmless", re.I),
        plain_language="This clause makes one side compensate the other for specified losses or claims.",
        why_it_matters="Indemnities can shift large risks onto you; the scope of covered losses is the key detail.",
    ),
    Rule(
        title="Arbitration clause",
        category="arbitration",
        pattern=re.compile(r"arbitrat", re.I),
        plain_language="This clause routes disputes to arbitration instead of court, with its own process and location.",
        why_it_matters="Arbitration location, cost-sharing and whether it is mandatory change how a dispute actually plays out.",
    ),
    Rule(
        title="Automatic renewal",
        category="renewal",
        pattern=re.compile(r"auto\s*-?\s*renew|renew(?:s|al)?\s+automatically", re.I),
        plain_language="This clause makes the agreement continue for another term unless stopped within a set window.",
        why_it_matters="An automatic renewal can bind you for another full term if you miss the notice window.",
    ),
    Rule(
        title="Termination without cause",
        category="termination",
        pattern=re.compile(r"terminat(?:e|ion|ed)\s+without\s+cause|\bat\s+will\b", re.I),
        plain_language="This clause lets the other party end the agreement without proving a reason.",
        why_it_matters="Know what notice and payments apply if the agreement ends without cause.",
    ),
    Rule(
        title="Liability cap or limitation",
        category="liability",
        pattern=re.compile(r"liabilit|damages\s+(?:cap|capped|limit|limited)", re.I),
        plain_language="This clause caps or excludes how much one side can be held liable for.",
        why_it_matters="Liability caps and carve-outs determine how much you could actually recover if things go wrong.",
    ),
    Rule(
        title="Waiver of rights",
        category="waiver",
        pattern=re.compile(r"waiv(?:e|er|es)", re.I),
        plain_language="This clause gives up certain rights or says that failing to enforce a term is not a waiver.",
        why_it_matters="Waivers are easy to overlook and can remove protections you expected to keep.",
    ),
)


def _sentences(text: str) -> list[str]:
    return [_clean(s) for s in _SENTENCE_SPLIT.split(text) if _clean(s)]


def _clean(s: str) -> str:
    return " ".join(s.split()).strip()


def rule_analyze(pages: list[str], document_type: str = "", title: str = "") -> DocumentAnalysis:
    """Build a rule-based DocumentAnalysis from plain-text pages (deterministic)."""
    clauses: list[Clause] = []
    seen: set[str] = set()

    for page_index, page_text in enumerate(pages, start=1):
        current_section = ""
        for sentence in _sentences(page_text):
            if len(clauses) >= MAX_RULE_CLAUSES:
                break
            if _SECTION_PATTERN.match(sentence):
                current_section = _SECTION_PATTERN.match(sentence).group(1).strip().rstrip(".")
            key = re.sub(r"\s+", " ", sentence.lower())[:60]
            if key in seen:
                continue
            for rule in _RULES:
                if rule.pattern.search(sentence):
                    seen.add(key)
                    evidence = sentence[: _MAX_EVIDENCE_CHARS] + ("…" if len(sentence) > _MAX_EVIDENCE_CHARS else "")
                    clauses.append(
                        Clause(
                            title=rule.title,
                            category=rule.category,
                            importance="LOW",
                            plain_language=rule.plain_language,
                            why_it_matters=rule.why_it_matters,
                            source_page=page_index,
                            source_section=current_section,
                            evidence=evidence,
                            confidence="MEDIUM",
                        )
                    )
                    break
            if len(clauses) >= MAX_RULE_CLAUSES:
                break

    clauses, _scores = apply_attention_to_all(clauses)
    summary = compute_attention_summary(clauses)
    return DocumentAnalysis(
        document_type=document_type[:80] or "",
        document_title=title[:200] or "",
        parties=[],
        effective_date="",
        expiration_date="",
        jurisdiction="",
        important_dates=[],
        financial_amounts=[],
        important_clauses=clauses,
        attention_summary=summary,
    )