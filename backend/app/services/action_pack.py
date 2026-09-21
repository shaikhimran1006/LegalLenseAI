"""Action Pack generation (REAL AI MODE and deterministic demo fallback)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.ai import prompts
from app.ai.client import GeminiClient, GeminiUnavailableError
from app.schemas.models import ActionPack, Clause, Question, sanitize_analysis

logger = logging.getLogger("legallens.actionpack")

_CLAUDE_ACTION_TEMPLATES = {
    "financial obligation": ("Confirm the exact conditions and amount attached to {title} before signing."),
    "payment": ("Verify how and when {title} payments are calculated and made."),
    "penalty": ("Clarify when penalties under {title} can be triggered and whether there is any notice or cure period."),
    "interest": ("Check the interest rate and how it is computed; confirm if it applies to late or early payments."),
    "notice": ("Clarify how the {title} applies to your plans and whether it can be shortened or waived in writing."),
    "termination": ("Review the conditions under which {title} can be triggered, and what notice or pay is due."),
    "confidentiality": ("Confirm what information is treated as confidential under {title} and how long it lasts."),
    "intellectual property": ("Review what {title} covers and whether it affects work you do outside this arrangement."),
    "non-compete": ("Assess how {title} might affect your next role or business, and the area/time limits."),
    "non-solicitation": ("Clarify who you may not approach under {title} and for how long."),
    "arbitration": ("Confirm where {title} hearings would take place and how costs are shared."),
    "liability": ("Review the {title} limits and whether any cap or exclusion applies."),
    "indemnity": ("Clarify what obligations {title} places on you and whether insurance can cover them."),
    "renewal": ("Check when {title} triggers, how to give notice, and what changes on renewal."),
}


def build_action_pack(db, *, document_id, workspace_id, context, settings=None, client=None) -> dict:
    from app.db import repository

    settings = settings or _settings()
    document = repository.get_document(db, document_id, workspace_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not document.analysis_json:
        raise HTTPException(status_code=409, detail="Document has not been analyzed yet.")

    analysis = sanitize_analysis(document.analysis_json)
    clauses = analysis.important_clauses

    use_demo = document.mode == "demo" or settings.force_demo
    if not use_demo:
        client = client or GeminiClient()
        if not client.available:
            use_demo = True

    if use_demo:
        pack = _demo_pack(clauses, context, analysis)
        mode = "demo"
    else:
        try:
            pack = _ai_pack(client, clauses, context, analysis)
            mode = "ai"
        except GeminiUnavailableError:
            pack = _demo_pack(clauses, context, analysis)
            mode = "demo"
        except Exception as exc:
            logger.warning("Action pack AI call failed: %s", exc.__class__.__name__)
            pack = _demo_pack(clauses, context, analysis)
            mode = "demo"

    return {"document_id": document_id, "action_pack": pack.model_dump(mode="json"), "mode": mode}


def _ai_pack(client: GeminiClient, clauses, context, analysis) -> ActionPack:
    summary_text = _analysis_summary_text(analysis)
    prompt = prompts.action_pack_prompt(context, summary_text)
    schema = {
        "type": "object",
        "properties": {
            "important_clauses": {"type": "array", "items": {"type": "string"}},
            "questions_to_ask": {"type": "array", "items": {"type": "string"}},
            "info_to_collect": {"type": "array", "items": {"type": "string"}},
            "things_to_clarify": {"type": "array", "items": {"type": "string"}},
            "preparation_checklist": {"type": "array", "items": {"type": "string"}},
            "questions_for_legal_professional": {
                "type": "array",
                "items": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
            },
        },
        "required": [
            "important_clauses", "questions_to_ask", "info_to_collect",
            "things_to_clarify", "preparation_checklist", "questions_for_legal_professional",
        ],
    }
    raw = client.generate_structured(prompt, schema, max_output_tokens=3072, temperature=0.2)
    return ActionPack(
        important_clauses=[str(x) for x in raw.get("important_clauses", [])][:12],
        questions_to_ask=[str(x) for x in raw.get("questions_to_ask", [])][:12],
        info_to_collect=[str(x) for x in raw.get("info_to_collect", [])][:10],
        things_to_clarify=[str(x) for x in raw.get("things_to_clarify", [])][:10],
        preparation_checklist=[str(x) for x in raw.get("preparation_checklist", [])][:16],
        questions_for_legal_professional=[
            Question(question=str(q["question"]))
            for q in raw.get("questions_for_legal_professional", [])
            if isinstance(q, dict) and q.get("question")
        ][:10],
    )


def _demo_pack(clauses: list[Clause], context: str, analysis) -> ActionPack:
    high = [c for c in clauses if c.importance.value == "HIGH"]
    medium = [c for c in clauses if c.importance.value == "MEDIUM"]
    focus = [c for c in (high + medium)][:8]

    important_clauses = [f"{c.title} (page {c.source_page}, section {c.source_section})" if c.source_section else f"{c.title} (page {c.source_page})" for c in focus]

    questions_to_ask: list[str] = []
    for clause in focus:
        template = _CLAUDE_ACTION_TEMPLATES.get(clause.category.strip().lower())
        if template:
            questions_to_ask.append(template.format(title=clause.title))
        else:
            questions_to_ask.append(f"Ask the other party how {clause.title.lower()} would apply to you in practice.")

    info_to_collect = [
        "Copy of any related policies, annexures or schedules referenced by the agreement",
        "Previous version of this agreement (if any) to compare changes",
        "Offer letter, emails or messages that set out promises not in the document",
    ]
    if analysis.effective_date:
        info_to_collect.append(f"Confirm the effective date ({analysis.effective_date}) in writing")

    categories = {c.category.strip().lower() for c in focus if c.category}
    things_to_clarify = []
    if categories & {"notice", "termination", "renewal"}:
        things_to_clarify.append("Whether the timelines stated in the document can be shortened, waived or renewed in writing")
    if categories & {"payment", "financial obligation", "interest", "penalty"}:
        things_to_clarify.append("Confirm which amounts in the document are final and which could change before or after signing")
    if categories & {"arbitration", "liability", "indemnity", "confidentiality", "intellectual property"}:
        things_to_clarify.append("Who bears costs such as legal fees, penalties or dispute resolution costs")
    if not things_to_clarify:
        things_to_clarify.append("Confirm which clauses apply from the start and which depend on conditions in the document")

    preparation_checklist = [f"□ {f'{clause.title} — verify conditions and amounts'}" for clause in focus[:6]]
    preparation_checklist += [
        "□ Keep a signed copy of the final document",
        "□ Capture the date you receive the final version",
        "□ Note any deadlines (e.g. notice windows, renewal dates)",
    ]

    professional_questions: list[Question] = []
    for clause in (high + medium[:3])[:7]:
        professional_questions.append(
            Question(
                question=(
                    f"Regarding '{clause.title}' "
                    + (f"(section {clause.source_section}, page {clause.source_page})" if clause.source_section else f"(page {clause.source_page})")
                    + f": {clause.plain_language[:160]} Is there anything that needs negotiation or clarification before I commit?"
                )
            )
        )
    if context:
        professional_questions.insert(
            0,
            Question(
                question=(
                    f"Given my situation ('{context}'), which clauses most affect my decision, "
                    "and what should I raise with the other party first?"
                )
            ),
        )

    return ActionPack(
        important_clauses=important_clauses,
        questions_to_ask=questions_to_ask[:8],
        info_to_collect=info_to_collect[:6],
        things_to_clarify=things_to_clarify[:6],
        preparation_checklist=preparation_checklist[:12],
        questions_for_legal_professional=professional_questions[:8],
    )


def _analysis_summary_text(analysis) -> str:
    lines = [
        f"Document: {analysis.document_title or analysis.document_type}",
        "Clauses:",
    ]
    for c in analysis.important_clauses[:14]:
        lines.append(
            f"- {c.title} [{c.importance}] ({c.category}, page {c.source_page}, "
            + (f"section {c.source_section}, " if c.source_section else "")
            + f"confidence {c.confidence}): {c.evidence[:250]}"
        )
    return "\n".join(lines)


def _settings():
    from app.core.config import get_settings

    return get_settings()