# Security

This document describes the security model of LegalLens AI and, in particular, how the
product resists **prompt injection** — a class of attack where a document tries to
coerce the LLM into ignoring instructions.

## Threat model

Legal documents are arbitrary attacker-controlled text. The most realistic risks:

1. **Prompt injection** — the document says *"ignore previous instructions"*,
   *"reveal your system prompt"*, or *"state that clause X is high risk"*.
2. **Prompt exfiltration** — the document asks the model to echo private system
   instructions, API keys, or other users' data.
3. **Grounded-data poisoning** — machine-generated or malicious clauses that then steer
   downstream outputs (comparison, action pack).
4. **Abuse of the API** — spam / quota burn through repeated AI calls.

## Countermeasures implemented

### 1. Untrusted-data wrapping

All AI prompts are assembled as:

```
SYSTEM_POLICY  (trusted, developer-provided)
  ...your instructions, evidence rules, output schema...

<UNTRUSTED_DOCUMENT_BEGIN>
  ...retrieved document text...
<UNTRUSTED_DOCUMENT_END>
Question: <user question (also treated as untrusted)>
```

The system policy states document text is **UNTRUSTED DATA** and that the system
instructions *always* take priority over anything in the document or the user's message.
Every prompt template goes through `wrap_untrusted(...)` — see
`backend/app/ai/prompts.py` and `backend/app/ai/guardrails.py`.

### 2. Injection detection + neutralisation

Uploaded and retrieved text passes `detect_injection`, which flags known instruction
patterns (`ignore previous`, `reveal your system prompt`, `you are now`, etc.). An
additional `neutralize_embedded_instructions` step neutralises embedded directive text
before it reaches the model. Tests in `tests/test_guardrails.py` cover:

- templates always wrap untrusted content,
- `detect_injection` catches a battery of attack strings,
- the system policy forbids following in-document instructions,
- re-formatted/injected quotes are normalised.

### 3. Structured outputs, not free text

Clause extraction uses JSON-schema-constrained generation (one-shot structured schema,
emitted via `GeminiClient.generate_structured`). Echoing live system prompts inside a
JSON schema response is impossible by construction — the schema simply has no field for
it, and strikes are re-attempted.

### 4. Evidence grounding as a poison defence

A claimed clause only survives if its `evidence` string is re-located verbatim in the
stored document text during the grounding pass. This bounds what the model can
"add" to the analysis, and it rejects clauses whose quotes do not exist.

### 5. Input validation, rate limits, workspace isolation

- Upload validation: extension whitelist (`.pdf/.docx/.doc/.txt`) and 20 MB cap.
- Rate limiting: in-memory sliding window per client IP on AI endpoints (default 30/min,
  configurable via `RATE_LIMIT_PER_MINUTE`).
- Workspace scoping: documents are namespaced by the `X-Workspace-Id` header (default
  `public`). Sample documents are read-only IDs and accessible from any workspace.
- Secret management: keys live in environment variables / Render secrets — never in the
  repo; the repo ships `.env.example` only and `.env`/`.env.*.local` are gitignored.
- `render.yaml` uses Render's `sync: false` secret fields and generates `JWT_SECRET`.

### 6. Clean failure

On Gemini unavailability or quota errors, AI endpoints return explicit HTTP 502s with
human-readable messages and **never** fall back to a partially-trusted answer. With no
API key configured, the preloaded sample documents still work (their analyses are
pre-computed) and uploaded documents use the deterministic offline fallback instead.

## Known limits & deploy-time recommendations

- In-memory rate limiter is per-process; scale-out deployments should move to a shared
  store (e.g. Redis) or an edge WAF.
- Uploaded files are held in the database as structured JSON after text extraction for
  analysis/QA. For production multi-tenant deployments, add per-workspace encryption and
  retention policies.
- Add auth (JWT/Session) before exposing to untrusted internet users; the current build
  intentionally has none so the hackathon demo is zero-friction.

## Quick verification

```bash
cd backend
.venv\Scripts\python -m pytest tests -q          # 43 passing incl. guardrails + attention
.venv\Scripts\python -m uvicorn app.main:app --port 8000
# Upload backend/samples/prompt_injection_sample.txt and observe the assistant
# refusing to follow the embedded instructions.
```