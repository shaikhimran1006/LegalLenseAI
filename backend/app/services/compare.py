"""Contract comparison service (REAL AI MODE and deterministic fallback)."""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException

from app.ai import prompts
from app.ai.client import GeminiClient, GeminiUnavailableError
from app.engine.attention import score_clause, score_to_importance
from app.schemas.models import (
    Clause,
    ComparisonResult,
    ComparisonRow,
)
from app.engine.retrieval import build_passages, passage_to_evidence, retrieve

logger = logging.getLogger("legallens.compare")

_HIGH_CHANGE_AREAS = {
    "notice", "financial obligation", "termination", "penalty", "interest",
    "non-compete", "non-solicitation", "renewal", "default", "indemnity",
}


def compare_documents(
    db,
    *,
    document_a_id: str,
    document_b_id: str,
    workspace_id: str,
    settings=None,
    client: Optional[GeminiClient] = None,
) -> dict:
    from app.db import repository

    settings = settings or _settings()
    doc_a = repository.get_document(db, document_a_id, workspace_id)
    doc_b = repository.get_document(db, document_b_id, workspace_id)
    if doc_a is None or doc_b is None:
        raise HTTPException(status_code=404, detail="One of the documents was not found.")

    analysis_a = doc_a.analysis_json
    analysis_b = doc_b.analysis_json
    if not analysis_a or not analysis_b:
        raise HTTPException(status_code=409, detail="Both documents must be analyzed before comparison.")

    # Demo comparison for the two seeded demo documents is precomputed.
    if settings.force_demo or (doc_a.mode == "demo" and doc_b.mode == "demo"):
        result = _try_seed_comparison(document_a_id, document_b_id) or _deterministic_compare(
            analysis_a, analysis_b
        )
        mode = "demo"
    else:
        client = client or GeminiClient()
        if settings.force_demo or not client.available:
            result = _deterministic_compare(analysis_a, analysis_b)
            mode = "demo"
        else:
            result = _ai_compare(client, doc_a, doc_b, analysis_a, analysis_b, settings)
            mode = "ai"

    comparison = repository.save_comparison(
        db,
        document_a_id=document_a_id,
        document_b_id=document_b_id,
        result_json=result.model_dump(mode="json"),
        mode=mode,
        workspace_id=workspace_id,
    )
    return {
        "comparison_id": comparison.id,
        "document_a": doc_a.filename,
        "document_b": doc_b.filename,
        "result": result.model_dump(mode="json"),
        "mode": mode,
    }


def _ai_compare(client: GeminiClient, doc_a, doc_b, analysis_a, analysis_b, settings) -> ComparisonResult:
    pages_a = _pages_of(doc_a)
    pages_b = _pages_of(doc_b)
    text_a = "\n\n".join(pages_a)[:60_000]
    text_b = "\n\n".join(pages_b)[:60_000]
    prompt = prompts.comparison_prompt(doc_a.filename, text_a, doc_b.filename, text_b)
    schema = {
        "type": "object",
        "properties": {
            "comparison_rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "contract_a_value": {"type": "string"},
                        "contract_b_value": {"type": "string"},
                        "change": {"type": "string", "enum": ["Significant", "Review", "Minor", "Added", "Removed"]},
                        "a_source_page": {"type": "integer"},
                        "a_source_section": {"type": "string"},
                        "b_source_page": {"type": "integer"},
                        "b_source_section": {"type": "string"},
                    },
                    "required": ["area"],
                },
            },
            "important_changes": {"type": "array", "items": {"type": "string"}},
            "clauses_added": {"type": "array", "items": {"type": "string"}},
            "clauses_removed": {"type": "array", "items": {"type": "string"}},
            "clauses_modified": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["comparison_rows", "important_changes", "clauses_added", "clauses_removed", "clauses_modified"],
    }
    try:
        raw = client.generate_structured(prompt, schema, max_output_tokens=4096, temperature=0.1)
    except GeminiUnavailableError:
        raise HTTPException(status_code=503, detail="AI service is temporarily unavailable.")
    except Exception as exc:
        logger.warning("Comparison AI call failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="The AI comparison failed, possibly due to free-tier quota. Please try again shortly.")
    result = ComparisonResult(
        comparison_rows=[ComparisonRow.model_validate(r) for r in raw.get("comparison_rows", []) if isinstance(r, dict)],
        important_changes=[str(x) for x in raw.get("important_changes", [])],
        clauses_added=[str(x) for x in raw.get("clauses_added", [])],
        clauses_removed=[str(x) for x in raw.get("clauses_removed", [])],
        clauses_modified=[str(x) for x in raw.get("clauses_modified", [])],
    )
    return result


def _try_seed_comparison(document_a_id: str, document_b_id: str) -> Optional[ComparisonResult]:
    from app.db import demo as demo_data

    for item in demo_data.load_seed().get("comparisons", []):
        if {item["document_a_id"], item["document_b_id"]} == {document_a_id, document_b_id}:
            return ComparisonResult.model_validate(item["result"])
    return None


def _deterministic_compare(analysis_a: dict, analysis_b: dict) -> ComparisonResult:
    clauses_a = [_to_clause(x) for x in analysis_a.get("important_clauses", []) if isinstance(x, dict)]
    clauses_b = [_to_clause(x) for x in analysis_b.get("important_clauses", []) if isinstance(x, dict)]

    by_category_a: dict[str, Clause] = _best_clause_by_category(clauses_a)
    by_category_b: dict[str, Clause] = _best_clause_by_category(clauses_b)
    categories = list(dict.fromkeys(list(by_category_a) + list(by_category_b)))

    rows: list[ComparisonRow] = []
    important_changes: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    modified: list[str] = []

    for category in categories:
        clause_a = by_category_a.get(category)
        clause_b = by_category_b.get(category)
        area = _area_label(category, clause_a or clause_b)

        if clause_a and not clause_b:
            rows.append(ComparisonRow(area=area, contract_a_value=_short_value(clause_a), contract_b_value="Not found", change="Removed", a_source_page=clause_a.source_page, a_source_section=clause_a.source_section))
            removed.append(_removed_line(clause_a))
            continue
        if clause_b and not clause_a:
            rows.append(ComparisonRow(area=area, contract_a_value="Not found", contract_b_value=_short_value(clause_b), change="Added", b_source_page=clause_b.source_page, b_source_section=clause_b.source_section))
            added.append(_added_line(clause_b))
            continue

        assert clause_a and clause_b
        value_a = _short_value(clause_a)
        value_b = _short_value(clause_b)
        changed = _significant_difference(clause_a, clause_b)
        if changed:
            change = "Significant" if category in _HIGH_CHANGE_AREAS else "Modified"
            modifier = _made_changed_line(category, clause_a, clause_b)
            modified.append(modifier)
            important_changes.append(
                f"{area.title()}: {_highlight_diff(clause_a, clause_b)} For Contract A see page {clause_a.source_page or '—'}"
                + (f", section {clause_a.source_section}" if clause_a.source_section else "")
                + f"; Contract B page {clause_b.source_page or '—'}"
                + (f", section {clause_b.source_section}" if clause_b.source_section else "") + "."
            )
            rows.append(ComparisonRow(area=area, contract_a_value=value_a, contract_b_value=value_b, change=change, a_source_page=clause_a.source_page, a_source_section=clause_a.source_section, b_source_page=clause_b.source_page, b_source_section=clause_b.source_section))
        else:
            rows.append(ComparisonRow(area=area, contract_a_value=value_a, contract_b_value=value_b, change="Minor", a_source_page=clause_a.source_page, a_source_section=clause_a.source_section, b_source_page=clause_b.source_page, b_source_section=clause_b.source_section))

    return ComparisonResult(
        comparison_rows=rows,
        important_changes=important_changes,
        clauses_added=added,
        clauses_removed=removed,
        clauses_modified=modified,
    )


def _to_clause(raw: dict) -> Clause:
    return Clause.model_validate(_coerce_clause(raw))


def _coerce_clause(raw: dict) -> dict:
    from app.schemas.models import _coerce_clause as coerce

    return coerce(raw)


def _best_clause_by_category(clauses: list[Clause]) -> dict[str, Clause]:
    best: dict[str, Clause] = {}
    for clause in clauses:
        cat = clause.category.strip().lower()
        existing = best.get(cat)
        if not existing or score_clause(clause) > score_clause(existing):
            best[cat] = clause
    return best


def _area_label(category: str, clause: Optional[Clause]) -> str:
    if clause:
        return clause.title
    return category.title()


def _short_value(clause: Clause) -> str:
    evidence = " ".join(clause.evidence.split())
    amount = re.findall(r"(?:rs\.?\s?|inr\s?|₹)?\d[\d,]*(?:k|l|,000)?", evidence, re.I)
    return evidence[:140] if evidence else clause.plain_language[:140]


def _significant_difference(a: Clause, b: Clause) -> bool:
    if a.title.lower() != b.title.lower():
        return True
    if _extract_numbers(a.evidence) != _extract_numbers(b.evidence):
        return True
    return len(_norm(a.evidence)) > 0 and a.evidence.lower() != b.evidence.lower()


def _extract_numbers(text: str) -> list[str]:
    return re.findall(r"\d[\d,]*(?:\.\d+)?", text)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _highlight_diff(a: Clause, b: Clause) -> str:
    numbers_a = _extract_numbers(a.evidence)
    numbers_b = _extract_numbers(b.evidence)
    if numbers_a and numbers_b and numbers_a != numbers_b:
        return f"{a.title} changed from {', '.join(numbers_a)} to {', '.join(numbers_b)}."
    if numbers_a and not numbers_b:
        return f"{b.title} appears ({', '.join(numbers_a)} in Contract A) but not found in Contract B."
    if not numbers_a and numbers_b:
        return f"{a.title} appears ({', '.join(numbers_b)} in Contract B) but not found in Contract A."
    return f"{a.title} wording differs between the two contracts."


def _added_line(clause: Clause) -> str:
    return f"{clause.title} (Contract B page {clause.source_page}" + (f", section {clause.source_section}" if clause.source_section else "") + ")."


def _removed_line(clause: Clause) -> str:
    return f"{clause.title} (Contract A page {clause.source_page}" + (f", section {clause.source_section}" if clause.source_section else "") + ")."


def _made_changed_line(category: str, a: Clause, b: Clause) -> str:
    return f"{a.title} ({a.category}) updated between the contracts."


def _pages_of(document) -> list[str]:
    if document.processed_text and document.processed_text.get("pages"):
        return document.processed_text["pages"]
    from app.db import demo as demo_data

    return demo_data.demo_pages(document.id) or []


def _settings():
    from app.core.config import get_settings

    return get_settings()