# Responsible AI

LegalLens AI is designed around two principles: **every output is evidence-backed**, and
**the user (never the LLM) makes decisions**. This document explains the safeguards
baked into the product.

## Grounding: no answer without a citation

1. Documents are split into pages and passages during ingestion.
2. For Q&A, a deterministic retrieval layer (token-overlap over pages) selects the
   relevant evidence — only that evidence is placed in front of the model.
3. The model is constrained by a system policy that requires answers to use only the
   supplied evidence and to decline or mark `insufficient` when the document cannot
   support an answer.
4. Confidence is not a model opinion: a clause's `confidence` is downgraded to **LOW**
   when its supporting quote cannot be re-found verbatim in the stored document text.

Consequence: **the demo's code path can never hallucinate a clause, page number, or
dollar amount** — it is either in the document, or not produced.

## Deterministic attention, not vibes

Clause importance (`HIGH / MEDIUM / LOW`) is computed by the **attention engine**:

- rule-based signals tuned per context profile (termination, notice, financial,
  non-compete, confidentiality, renewal, liability, data/privacy, etc.),
- with explicit lengths such as notice days, non-compete months, and radius/amount
  thresholds (e.g. ≥ 60 days notice → HIGH; ≥ 12 months non-compete → HIGH).

The GenerativeAI extractor proposes clauses; the deterministic engine **re-rates** them,
so attention ratings are stable and explainable. Test `test_attention.py` locks the
behaviour (e.g. `"ninety (90) days' written notice"` → HIGH, `30 days` → MEDIUM,
probation `7 days` → MEDIUM).

## One voice: English-only responses

All responses are written in clear, simple English. The same grounding rules apply to
every answer — quoted document wording is always kept verbatim.

## Clear boundary: not legal advice

- The system policy states the assistant is **not a lawyer** and must not give
  definitive legal conclusions.
- The UI repeats this everywhere: the responsible-AI notice card, footer, drawer
  footnotes, the Settings page, and the Action-Pack panel all carry the same warning.

## Transparency signals

- Every answer card shows its cited quotes + page + section.
- The Action Pack distinguishes "questions to ask the other party", "things to
  clarify", and "questions for a legal professional".
- Responses for preloaded sample documents are labelled `Sample` in the UI, and the
  API health endpoint reports `"demo_mode": true` to flag that the sample analyses are
  pre-computed rather than run live.

## Failure behaviour

- AI endpoints are rate-limited (per IP) and produce clean HTTP errors (`502` with a
  human message) when the model is unavailable or a generation fails — no silent
  partial answers. Analysis re-runs are idempotent and cached in the database.

---

## Acceptable use

This tool helps people *prepare* for conversations with legal professionals. It is not a
replacement for a lawyer, and it is not law. For genuine legal decisions, consult a
qualified professional in the relevant jurisdiction.