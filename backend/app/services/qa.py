"""Grounded Q&A service.

REAL AI MODE: retrieve the most relevant passages, then call Gemini with ONLY
that evidence (free-tier friendly). DEMO MODE: deterministic retrieval + clause
matching over the cached seed analysis (no Gemini spend, reliably repeatable).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException

from app.ai import prompts
from app.ai.client import GeminiClient, GeminiUnavailableError, model_schema, parse_json_object
from app.engine.attention import rank_clauses
from app.engine.retrieval import (
    build_passages,
    retrieve,
)
from app.schemas.models import Answer, Clause, EvidenceRef

logger = logging.getLogger("legallens.qa")

_MISSING_ANSWER = (
    "The document does not provide enough information to answer this reliably.\n\n"
    "You may want to ask a legal professional about this."
)

# Phrases that indicate the model itself thinks the document lacks the answer;
# used to avoid re-labelling a real, grounded answer as "insufficient".
_MISSING_PHRASES = (
    "couldn't find enough information",
    "does not provide enough information",
    "not provide enough information",
    "does not contain enough information",
    "does not mention",
    "does not state",
)

# Map document kinds to a small set of fallback relevant clause categories used only
# when retrieval yields nothing (never invents content — just surfaces existing clauses).
_CONTEXT_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "employment": ("notice", "termination", "financial obligation", "non-solicitation", "confidentiality", "intellectual property"),
    "renting": ("financial obligation", "notice", "termination", "renewal", "penalty", "liability"),
    "loan": ("interest", "penalty", "financial obligation", "default", "termination"),
    "insurance": ("insurance", "warranty", "liability", "renewal"),
    "business": ("liability", "indemnity", "arbitration", "confidentiality", "warranty"),
    "consumer": ("penalty", "liability", "dispute resolution", "termination", "payment"),
    "other": (),
}


def answer_question(db, *, document_id, workspace_id, question, context, settings=None, client=None):
    from app.db import repository

    settings = settings or _settings()
    document = repository.get_document(db, document_id, workspace_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not document.analysis_json:
        raise HTTPException(status_code=409, detail="Document has not been analyzed yet.")

    pages = _pages_for(document, document_id)
    analysis_json = document.analysis_json
    clauses = _clauses_from_analysis(analysis_json)

    use_demo = (document.mode == "demo") or settings.force_demo
    if use_demo:
        answer = _demo_answer(question, context, pages, clauses, analysis_json)
        mode = "demo"
    else:
        client = client or GeminiClient()
        if not client.available:
            answer = _demo_answer(question, context, pages, clauses, analysis_json)
            mode = "demo"
        else:
            answer = _ai_answer(client, document, question, context, pages, clauses)
            mode = "ai"

    return {
        "document_id": document_id,
        "answer": answer.model_dump(mode="json"),
        "mode": mode,
    }


def _ai_answer(client, document, question, context, pages, clauses) -> Answer:
    if not client.available:
        return Answer(answer=_MISSING_ANSWER, insufficient=True)

    passages = build_passages(pages)

    # Passage-level retrieval over the actual document text. `hits` keeps only
    # passages the retriever actually scored; when nothing scores we still feed
    # the first few passages so the model can judge insufficiency itself.
    hits = retrieve(question, passages, k=8, context=context)
    retrieved = hits or passages[:3]

    # Clause-level ranking mirrors the "related clauses" the frontend shows and
    # gives Gemini precise verbatim evidence even where passage retrieval misses.
    ranked = rank_clauses(clauses, question) if clauses else []
    top_clauses = [c for c, _, _ in ranked[:5]]

    evidence_text = _build_evidence_context(retrieved, top_clauses)

    logger.debug(
        "QA question=%r hits=%d fallback=no clause_sources=%d evidence_chars=%d",
        question,
        len(hits),
        len(top_clauses),
        len(evidence_text),
    )
    logger.debug("QA retrieved clause titles: %s", ", ".join(c.title for c in top_clauses))
    logger.debug("QA retrieved page numbers: %s", ", ".join(str(p.page) for p in retrieved))

    prompt = prompts.qa_prompt(
        document.filename,
        context,
        evidence_text,
        question,
    )
    try:
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "section": {"type": "string"},
                            "quote": {"type": "string"},
                        },
                    },
                },
                "insufficient": {"type": "boolean"},
            },
            "required": ["answer", "evidence", "insufficient"],
        }
        raw = client.generate_structured(prompt, schema, max_output_tokens=2048, temperature=0.15)
    except GeminiUnavailableError:
        raise HTTPException(status_code=503, detail="AI service is temporarily unavailable.")
    except Exception:
        logger.warning("QA Gemini call failed; returning insufficient answer")
        return Answer(answer=_MISSING_ANSWER, insufficient=True)

    logger.debug(
        "QA Gemini response insufficient=%s evidence=%d answer_chars=%d",
        bool(raw.get("insufficient")),
        len(raw.get("evidence") or []),
        len((raw.get("answer") or "").strip()),
    )

    answer = _coerce_answer(raw)
    return _ground_answer(answer, pages=pages, hits=hits, top_clauses=top_clauses, question=question)


# ---------------------------------------------------------------------------
# Evidence assembly (what Gemini actually reads)
# ---------------------------------------------------------------------------

def _build_evidence_context(retrieved, top_clauses, limit_chars: int = 9000) -> str:
    """Build SOURCE blocks made of real document text.

    Precise verbatim clause evidence comes first, then the retrieved passage
    text (capped per passage so several sources survive the token budget).
    """
    blocks: list[str] = []
    budget = limit_chars
    seen: set[str] = set()

    for clause in top_clauses:
        if budget <= 0:
            break
        text = (clause.evidence or "").strip()
        if not text:
            continue
        key = _norm(text[:200])
        if key in seen:
            continue
        seen.add(key)
        block = _source_block(len(blocks) + 1, max(clause.source_page, 0), clause.title, text)
        blocks.append(block)
        budget -= len(block)

    per_passage = 1400
    for passage in retrieved:
        if budget <= 0:
            break
        text = passage.text.strip()
        if not text:
            continue
        key = _norm(text[:200])
        if key in seen:
            continue
        seen.add(key)
        section_label = _passage_section_label(passage, top_clauses)
        block = _source_block(len(blocks) + 1, passage.page, section_label, text[:per_passage])
        blocks.append(block)
        budget -= len(block)

    return "\n\n".join(blocks)


def _source_block(n: int, page: int, section: str, text: str) -> str:
    head = f"SOURCE {n}\nPage: {page}"
    if section:
        head += f"\nSection: {section}"
    return f"{head}\n\n{text}"


def _passage_section_label(passage, top_clauses) -> str:
    title = next((c.title for c in top_clauses if c.source_page == passage.page and c.title), "")
    return title or (passage.section or "")


# ---------------------------------------------------------------------------
# Grounding checks (only accept what the document actually supports)
# ---------------------------------------------------------------------------

def _ground_answer(answer: Answer, *, pages, hits, top_clauses, question) -> Answer:
    """Attach verified evidence and decide insufficiency *from the document*.

    The old logic replaced any answer whose quotes were paraphrased with the
    blanket "insufficient" message. Instead we keep the answer, re-verify the
    quotes tolerantly, and fall back to the real document text the retriever
    found. Insufficiency is only returned when no relevant evidence exists at
    all (or when the model genuinely says so).
    """
    if not answer.answer.strip():
        return Answer(answer=_MISSING_ANSWER, insufficient=True)

    answer.evidence = [e for e in answer.evidence if _quote_acceptable(e.quote, pages)]

    relevant = _has_relevant_evidence(hits, top_clauses, question)

    if answer.insufficient:
        if relevant and _looks_grounded(answer, top_clauses):
            if not answer.evidence:
                answer.evidence = _synthesize_evidence(hits, top_clauses)
            answer.insufficient = False
        else:
            answer.answer = _MISSING_ANSWER
            answer.evidence = []
        return answer

    if not answer.evidence:
        if relevant or _cites_clause(answer, top_clauses):
            answer.evidence = _synthesize_evidence(hits, top_clauses)
        else:
            # No document foundation, no citation, model didn't flag it: stay safe.
            return Answer(answer=_MISSING_ANSWER, insufficient=True)
    return answer


def _has_relevant_evidence(hits, top_clauses, question: str) -> bool:
    if hits:
        return True
    if not top_clauses or not question:
        return False
    q_tokens = set(re.findall(r"[a-z0-9]{3,}", question.lower()))
    if not q_tokens:
        return False
    for clause in top_clauses[:5]:
        hay = f"{clause.title} {clause.category} {clause.evidence}".lower()
        h_tokens = set(re.findall(r"[a-z0-9]{3,}", hay))
        if q_tokens & h_tokens:
            return True
    return False


def _looks_grounded(answer: Answer, top_clauses) -> bool:
    low = answer.answer.lower()
    if any(phrase in low for phrase in _MISSING_PHRASES):
        return False
    if len(answer.answer.split()) < 12:
        return False
    return bool(answer.evidence) or _cites_clause(answer, top_clauses)


def _synthesize_evidence(hits, top_clauses) -> list[EvidenceRef]:
    """Build evidence refs from the *actual* document text the retriever used."""
    refs: list[EvidenceRef] = []
    seen: set[str] = set()
    for clause in top_clauses[:4]:
        text = (clause.evidence or "").strip()
        if not text:
            continue
        key = _norm(text)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            EvidenceRef(
                page=max(clause.source_page, 0),
                section=clause.title or clause.source_section,
                quote=text[:400],
            )
        )
    for passage in hits[:3]:
        text = (passage.text or "").strip()
        if not text:
            continue
        key = _norm(text[:200])
        if key in seen:
            continue
        seen.add(key)
        refs.append(EvidenceRef(page=passage.page, section=passage.section, quote=text[:400]))
    return refs


def _quote_acceptable(quote: str, pages: list[str]) -> bool:
    """Accept a quoted citation if it strongly matches the document.

    Tolerates minor wording/normalization differences that Gemini introduces
    while still refusing made-up quotes (verbatim substring, or high token
    overlap for longer quotes).
    """
    if not quote:
        return True
    needle = " ".join(quote.lower().split())
    if not needle:
        return True
    hay = " ".join(" ".join(p.lower().split()) for p in pages)
    if needle[:80] in hay:
        return True
    n = len(set(re.findall(r"[a-z0-9]+", needle)))
    if n == 0:
        return True
    require = 1.0 if n <= 4 else 0.65
    return _token_overlap(needle, hay) >= require


def _token_overlap(text_a: str, text_b: str) -> float:
    import re as _re

    tokens_a = set(_re.findall(r"[a-z0-9]+", text_a.lower()))
    tokens_b = set(_re.findall(r"[a-z0-9]+", text_b.lower()))
    if not tokens_a:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a)


def _coerce_answer(raw) -> Answer:
    if not isinstance(raw, dict):
        return Answer(answer=_MISSING_ANSWER, insufficient=True)
    answer_text = (raw.get("answer") or "").strip()
    evidence_raw = raw.get("evidence") or []
    evidence = []
    if isinstance(evidence_raw, list):
        for item in evidence_raw:
            if not isinstance(item, dict):
                continue
            page = item.get("page") or 0
            try:
                page = int(float(page))
            except (TypeError, ValueError):
                page = 0
            evidence.append(
                EvidenceRef(
                    page=max(page, 0),
                    section=str(item.get("section") or "").strip(),
                    quote=str(item.get("quote") or "").strip(),
                )
            )
    insufficient = bool(raw.get("insufficient"))
    if not answer_text and not insufficient:
        return Answer(answer=_MISSING_ANSWER, insufficient=True)
    return Answer(answer=answer_text, evidence=evidence, insufficient=insufficient)


def _cites_clause(answer: Answer, clauses: list[Clause]) -> bool:
    if not clauses:
        return False
    low = answer.answer.lower()
    return any(c.title and c.title.lower() in low for c in clauses)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _demo_answer(question: str, context: str, pages: list[str], clauses: list[Clause], analysis_json: dict) -> Answer:
    if not clauses:
        return Answer(answer=_MISSING_ANSWER, insufficient=True)

    ranked = rank_clauses(clauses, context)
    question_low = question.lower()
    question_tokens = set(re.findall(r"[a-z0-9]{3,}", question_low))

    scores: list[tuple[float, Clause]] = []
    for clause, relevance, _reasons in ranked:
        hay_low = (clause.title + " " + clause.category + " " + clause.evidence + " " + clause.plain_language).lower()
        hay_tokens = set(re.findall(r"[a-z0-9]{3,}", hay_low))
        overlap = len(question_tokens & hay_tokens) / max(1, len(question_tokens))
        # Financial keywords strongly bias financial clauses.
        if re.search(r"(pay|amount|money|deposit|penalty|interest|repay|fee|cost)", question_low):
            if clause.category in {"financial obligation", "penalty", "interest", "payment"}:
                overlap += 0.5
        if re.search(r"(resign|notice|quit|leave|terminat|exit|leave\s+early)", question_low):
            if clause.category in {"notice", "termination"}:
                overlap += 0.5
            if clause.category in {"financial obligation", "penalty"}:
                overlap += 0.4
        scores.append((relevance / 100 + overlap, clause))

    scores.sort(key=lambda item: (item[0], item[1].importance.value), reverse=True)
    top = scores[0][1] if scores else clauses[0]

    passages = build_passages(pages)
    relevant = retrieve(question, passages, k=2, context=context)
    quotes: list[str] = []
    page_hits: list[int] = []
    if top.evidence:
        quotes.append(top.evidence)
    for passage in relevant[:2]:
        quote = passage.text[:220]
        if quote and quote not in quotes:
            quotes.append(quote)
        if passage.page not in page_hits:
            page_hits.append(passage.page)

    if not quotes:
        return Answer(answer=_MISSING_ANSWER, insufficient=True)

    evidence_refs = [
        EvidenceRef(page=top.source_page, section=top.source_section, quote=top.evidence[:400])
    ]
    for passage in relevant[:2]:
        evidence_refs.append(EvidenceRef(page=passage.page, section=passage.section, quote=passage.text[:220]))

    based_on = _build_demo_answer_text(top, quotes, questions=question)
    return Answer(answer=based_on, evidence=evidence_refs, insufficient=False)


def _build_demo_answer_text(clause: Clause, quotes: list[str], questions: str) -> str:
    lines = [
        "Based on your document:",
        "",
        f"The most relevant clause is \u201c{clause.title}\u201d ({clause.category}, "
        + (f"section {clause.source_section}, " if clause.source_section else "")
        + f"page {clause.source_page if clause.source_page else '—'}).",
        "",
        f"What it says: {_first_sentences(clause.evidence)}",
        "",
        f"In simple terms: {clause.plain_language}",
        "",
        f"Why it may matter: {clause.why_it_matters}",
        "",
        "This is information from the document, not legal advice. Interpretation of these terms can depend on the specific facts and applicable law \u2014 consider asking a legal professional about \u201c" + clause.title + "\u201d if it affects a decision you're making.",
    ]
    return "\n".join(lines)


def _first_sentences(text: str, max_chars: int = 300) -> str:
    text = " ".join(text.split())
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def _clauses_from_analysis(analysis_json: dict) -> list[Clause]:
    raw = analysis_json.get("important_clauses") or []
    clauses: list[Clause] = []
    for item in raw:
        try:
            clauses.append(Clause.model_validate(item))
        except Exception:
            continue
    return clauses


def _pages_for(document, document_id: str) -> list[str]:
    if document.processed_text and document.processed_text.get("pages"):
        return document.processed_text["pages"]
    from app.db import demo as demo_data

    pages = demo_data.demo_pages(document_id)
    return pages or []


def _settings():
    from app.core.config import get_settings

    return get_settings()