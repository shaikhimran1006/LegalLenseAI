"""Document analysis orchestration (REAL AI MODE and DEMO MODE).

Pipeline:
  extracted text -> Gemini classification/extraction -> JSON validation
  -> deterministic attention engine -> evidence grounding check -> cache.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import HTTPException

from app.ai import prompts
from app.ai.client import GeminiClient, GeminiUnavailableError, model_schema, parse_json_object
from app.ai.guardrails import assert_wrapped, sanitize_for_storage
from app.db import demo as demo_data
from app.db import repository
from app.engine.attention import apply_attention_to_all, compute_attention_summary
from app.engine.rules import rule_analyze
from app.schemas.models import DocumentAnalysis, sanitize_analysis

logger = logging.getLogger("legallens.analysis")


def run_analysis(
    db,
    *,
    document_id: str,
    workspace_id: str,
    force_demo: bool = False,
    settings=None,
    client: Optional[GeminiClient] = None,
) -> dict:
    """Analyze a stored document. Returns an AnalyzeResponse-compatible dict."""
    settings = settings or _settings()
    document = repository.get_document(db, document_id, workspace_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if force_demo or settings.force_demo:
        return _demo_analysis(db, document, settings)

    # Seeded sample documents always load their instant pre-computed analysis,
    # never calling Gemini (saves quota, avoids latency/rate-limiting).
    if demo_data.demo_analysis(document.id) is not None:
        return _demo_analysis(db, document, settings)

    client = client or GeminiClient()
    if not client.available:
        return _demo_analysis(db, document, settings, unavailable_reason="ai_unconfigured")

    pages = _stored_pages(document, document_id)
    if not pages:
        raise HTTPException(status_code=422, detail="Document text is not available. Please re-upload.")

    start = time.monotonic()
    try:
        excerpt = "\n\n".join(pages)
        if len(excerpt) > 160_000:
            excerpt = excerpt[:160_000] + "\n[truncated for processing]"
        prompt = prompts.classify_and_extract_prompt(document.context, excerpt)
        analysis = _call_analysis_llm(client, prompt, settings)
        duration_ms = int((time.monotonic() - start) * 1000)
    except GeminiUnavailableError:
        raise HTTPException(status_code=503, detail="AI service is unavailable right now. Please try again shortly.")
    except ValueError as exc:
        logger.warning("AI analysis produced unparseable output: %s", exc)
        raise HTTPException(status_code=502, detail="The AI returned an unreadable analysis. Please try again.")
    except HTTPException:
        raise
    except Exception as exc:  # network / quota
        logger.warning("Gemini analysis failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="The AI service failed. This usually means the free-tier quota was reached. Try again in a minute or enable demo mode.")

    analysis = _finalize_analysis(analysis, pages)
    repository.save_analysis(
        db,
        document,
        analysis_json=analysis.model_dump(mode="json"),
        status="analyzed",
        mode="ai",
        status_detail="Analyzed with Gemini",
        processed_text={"pages": pages, "text": "\n\n".join(pages)},
    )
    return {
        "document_id": document_id,
        "analysis": analysis.model_dump(mode="json"),
        "mode": "ai",
        "duration_ms": duration_ms,
    }


def _call_analysis_llm(client: GeminiClient, prompt: str, settings) -> DocumentAnalysis:
    schema = model_schema(DocumentAnalysis)
    # Structured-output path preferred; graceful fallback to JSON parsing.
    try:
        raw = client.generate_structured(prompt, schema, max_output_tokens=8192, temperature=0.1)
    except Exception:
        raw = parse_json_object(client.generate_text(prompt, max_output_tokens=8192, temperature=0.1))
    return sanitize_analysis(raw)


def _finalize_analysis(analysis: DocumentAnalysis, pages: list[str]) -> DocumentAnalysis:
    clauses, _ = apply_attention_to_all(analysis.important_clauses)
    analysis.important_clauses = clauses
    analysis.attention_summary = compute_attention_summary(clauses)
    analysis.important_clauses = [ground_clause(c, pages) for c in analysis.important_clauses]
    return analysis


def ground_clause(clause, pages: list[str]):
    """Validate that a clause's evidence appears in the document; downgrade
    confidence when it cannot be found (hallucination control)."""
    evidence = clause.evidence or ""
    needle = _normalize(evidence.strip()[:120])
    if not needle:
        return clause
    hay = " ".join(_normalize(p) for p in pages)
    found = needle[:40] in hay or _token_overlap(evidence, hay) >= 0.55
    if not found:
        return clause.model_copy(update={"confidence": "LOW"})
    return clause


def confirms_evidence(clause, pages) -> bool:
    return ground_clause(clause, pages).confidence != "LOW" or not clause.evidence


def _token_overlap(text_a: str, text_b: str) -> float:
    import re

    tokens_a = set(re.findall(r"[a-z0-9]+", _normalize(text_a.lower())))
    tokens_b = set(re.findall(r"[a-z0-9]+", text_b.lower()))
    if not tokens_a:
        return 0.0
    inter = tokens_a & tokens_b
    return len(inter) / len(tokens_a)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _stored_pages(document, document_id: str) -> list[str]:
    if document.processed_text and document.processed_text.get("pages"):
        return document.processed_text["pages"]
    if document_id.startswith("demo"):
        pages = demo_data.demo_pages(document_id)
        if pages:
            return pages
    return []


# ---------------------------------------------------------------------------
# Demo mode
# ---------------------------------------------------------------------------

def _demo_analysis(db, document, settings, unavailable_reason: str = "") -> dict:
    analysis_raw = demo_data.demo_analysis(document.id)
    if analysis_raw is None:
        if document.analysis_json:
            analysis = DocumentAnalysis.model_validate(document.analysis_json)
        else:
            # No seed and no cached AI result: fall back to deterministic
            # rule-based detection over the stored text (fully offline).
            pages = _stored_pages(document, document.id)
            analysis = rule_analyze(
                pages,
                document_type=document.context or "",
                title=document.filename or "",
            )
            if not analysis.important_clauses:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No Gemini API key is configured and no clauses could be detected from "
                        "this document's text. Add a GEMINI_API_KEY or use a demo document."
                    ),
                )
    else:
        analysis = DocumentAnalysis.model_validate(analysis_raw)
        analysis = _finalize_analysis(analysis, demo_data.demo_pages(document.id))

    reason = "Demo mode" if settings.force_demo or not settings.real_ai_available else "AI unavailable — demo fallback"
    if unavailable_reason:
        reason = "AI is not configured — running in demo mode"
    repository.save_analysis(
        db,
        document,
        analysis_json=analysis.model_dump(mode="json"),
        status="analyzed",
        mode="demo",
        status_detail=reason,
        processed_text={"pages": _stored_pages(document, document.id), "text": ""},
    )
    return {
        "document_id": document.id,
        "analysis": analysis.model_dump(mode="json"),
        "mode": "demo",
        "duration_ms": 0,
    }


def _settings():
    from app.core.config import get_settings

    return get_settings()