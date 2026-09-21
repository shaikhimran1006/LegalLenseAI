"""Document text processing: extraction, page segmentation, retrieval."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import BinaryIO, Optional
from zipfile import BadZipFile

from pypdf import PdfReader

MAX_PDF_PAGES = 80
MAX_CHARS = 180_000  # generous cap for free-tier token budgets


class DocumentExtractionError(Exception):
    """Raised when a document cannot be read/extracted."""


@dataclass
class ExtractedDocument:
    text: str
    pages: list[str]  # one entry per page
    page_count: int
    extension: str

    def capped(self, limit: int = MAX_CHARS) -> str:
        if len(self.text) <= limit:
            return self.text
        return self.text[:limit] + "\n[truncated for processing]" if len(self.text) > limit else self.text


def validate_file_name(filename: str) -> str:
    import re as _re
    name = _re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", filename or "")
    return name.strip()[:120] or "document"


def extract_text(data: bytes, extension: str, filename: str = "") -> ExtractedDocument:
    """Extract text + per-page text from PDF/TXT/DOCX bytes."""
    ext = (extension or "").lower().lstrip(".")
    # Magic-byte checks: a renamed malicious file (e.g. .exe → .pdf) must never
    # reach a parser. PDFs always start with "%PDF-", DOCX is a ZIP (PK\x03\x04).
    if ext in {"pdf"} and not data[:5].startswith(b"%PDF-"):
        raise DocumentExtractionError("The file is not a valid PDF (missing PDF header).")
    if ext in {"docx"} and not data[:4] == b"PK\x03\x04":
        raise DocumentExtractionError("The file is not a valid DOCX (missing ZIP header).")
    if ext in {"pdf"}:
        return _extract_pdf(data)
    if ext in {"txt", "text"}:
        return _extract_txt(data)
    if ext in {"docx"}:
        return _extract_docx(data)
    raise DocumentExtractionError(f"Unsupported file type: {extension or filename}")


def _extract_pdf(data: bytes) -> ExtractedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
    except BadZipFile as exc:
        raise DocumentExtractionError("The PDF file appears to be corrupted.") from exc
    except Exception as exc:
        raise DocumentExtractionError("Could not read this PDF. It may be corrupted or password-protected.") from exc
    pages: list[str] = []
    for idx, page in enumerate(reader.pages[:MAX_PDF_PAGES]):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        pages.append(text)
    page_count = len(reader.pages) if len(reader.pages) <= MAX_PDF_PAGES else MAX_PDF_PAGES
    if not any(pages):
        raise DocumentExtractionError(
            "No extractable text was found in this PDF. It may be a scanned image document."
        )
    return ExtractedDocument(text="\n\n".join(pages), pages=pages, page_count=page_count, extension="pdf")


def _extract_txt(data: bytes) -> ExtractedDocument:
    from app.ai.guardrails import sanitize_for_storage

    try:
        raw = data.decode("utf-8-sig", errors="replace")
    except Exception:
        raw = data.decode("latin-1", errors="replace")
    text = sanitize_for_storage(raw)
    if not text.strip():
        raise DocumentExtractionError("The text file is empty.")
    single = text[: MAX_CHARS if len(text) > MAX_CHARS else len(text)]
    return ExtractedDocument(text=single, pages=[single], page_count=1, extension="txt")


def _extract_docx(data: bytes) -> ExtractedDocument:
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    except (BadZipFile, ValueError) as exc:
        raise DocumentExtractionError("Could not read this DOCX file. It may be corrupted.") from exc
    except Exception as exc:
        raise DocumentExtractionError("Could not read this DOCX file.") from exc
    if not paragraphs:
        raise DocumentExtractionError("No text content was found in the DOCX file.")
    text = "\n".join(paragraphs)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[truncated for processing]"
    return ExtractedDocument(text=text, pages=[text], page_count=1, extension="docx")


# ---------------------------------------------------------------------------
# Retrieval (free-tier friendly keyword/heading retrieval, no extra Gemini calls)
# ---------------------------------------------------------------------------

@dataclass
class Passage:
    page: int
    section: str
    text: str

    def label(self) -> str:
        return self.section if self.section else f"Page {self.page}"


_SECTION_PATTERN = re.compile(
    r"(?m)^\s*((?:clause|section|article|para(?:graph)?)?\.?\s?\d+(?:[.\-]\d+)*\.?)\s+[—–-]?\s*[A-Z0-9].*"
)


def build_passages(pages: list[str]) -> list[Passage]:
    passages: list[Passage] = []
    for page_index, page_text in enumerate(pages, start=1):
        # Split page into heading-delimited blocks when section markers exist.
        blocks: list[tuple[str, str]] = []
        current_section = ""
        current_block: list[str] = []
        for line in page_text.splitlines():
            m = _SECTION_PATTERN.match(line.strip())
            if m and len(line.strip()) > len(m.group(1)) + 1:
                if current_block:
                    blocks.append((current_section, "\n".join(current_block)))
                current_section = m.group(1).strip().rstrip(".")
                current_block = [line.strip()]
            else:
                current_block.append(line.strip())
        if current_block:
            blocks.append((current_section, "\n".join(current_block)))
        if not blocks:
            blocks = [("", page_text)]
        for section, block_text in blocks:
            if block_text.strip():
                passages.append(Passage(page=page_index, section=section, text=block_text.strip()))
    return passages


_TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "was", "were", "be", "been", "will", "shall", "may", "this", "that",
    "these", "those", "as", "at", "by", "from", "it", "its", "if", "then", "than",
}

# ---------------------------------------------------------------------------
# Fuzzy term matching for the keyword retriever.
#
# The naive overlap retriever misses legal questions because users rarely use
# the document's exact wording ("resign" vs "resignation", "salary" vs
# "compensation").  Synonym groups plus prefix matching make it robust without
# any extra Gemini spend.
# ---------------------------------------------------------------------------

_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"resign", "resignation", "resigned", "resigning", "quit", "leaving", "depart", "exit", "left"}),
    frozenset({"terminate", "termination", "terminated", "terminating", "dismiss", "dismissal", "discharged", "fire", "fired", "sever", "severance", "ending"}),
    frozenset({"notice", "notices", "notify", "notification", "notified"}),
    frozenset({"salary", "salaries", "pay", "payable", "payment", "payments", "compensation", "wages", "remuneration", "income"}),
    frozenset({"repay", "repayment", "repayments", "repayable", "reimburse", "reimbursement", "reimbursable", "refund", "refundable"}),
    frozenset({"indemnify", "indemnifies", "indemnity", "indemnification", "indemnif"}),
    frozenset({"confidential", "confidentiality", "proprietary", "secret", "secrets"}),
    frozenset({"solicit", "solicitation", "solicitations", "soliciting", "solicits", "solicited"}),
    frozenset({"compete", "competition", "competing", "competitor", "competitors", "noncompete"}),
    frozenset({"arbitration", "arbitrate", "arbitral", "dispute", "disputes", "litigation"}),
    frozenset({"employee", "employees", "worker", "workers", "staff", "personnel"}),
    frozenset({"obligation", "obligations", "duty", "duties", "responsibility", "responsibilities", "responsible", "requirement", "requirements"}),
    frozenset({"liability", "liabilities", "liable"}),
    frozenset({"renewal", "renew", "renews", "renewed", "renewing", "extend", "extension", "extensions"}),
    frozenset({"probation", "probationary"}),
    frozenset({"intellectual-property", "ip", "invention", "inventions", "copyright", "copyrights", "patent", "patents", "trademark", "trademarks"}),
    frozenset({"employer", "company", "organization", "organisation", "firm"}),
    frozenset({"loan", "finance", "financing", "emi", "borrow", "borrowing", "mortgage"}),
    frozenset({"insurance", "policy", "coverage", "insured", "insurer", "premium", "premiums"}),
    frozenset({"default", "defaults", "breach", "breaches", "breached", "violation", "violations"}),
)


def _word_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def _ngrams(words: list[str], n: int = 1) -> set[str]:
    if n == 1:
        return set(words)
    return {f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)}


def _tokens(text: str, ngrams: int = 1) -> set[str]:
    """Flat token helper (unigrams and optional bigrams). Kept for callers that
    only need a plain token set."""
    words = _word_tokens(text)
    toks = set(words)
    for n in range(2, ngrams + 1):
        toks |= _ngrams(words, n)
    return toks


def _synonym_group(token: str) -> frozenset[str] | None:
    for group in _SYNONYM_GROUPS:
        if token in group:
            return group
    return None


def _token_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:
        short, long = (a, b) if len(a) <= len(b) else (b, a)
        if long.startswith(short):
            return True
    ga, gb = _synonym_group(a), _synonym_group(b)
    return bool(ga and ga is gb)


def _fuzzy_hits(query: set[str], passage: set[str]) -> int:
    """Count query words that (fuzzily) appear in a passage's word set."""
    hits = 0
    for q in sorted(query):
        for p in passage:
            if _token_match(q, p):
                hits += 1
                break
    return hits


def retrieve(
    question: str,
    passages: list[Passage],
    *,
    k: int = 4,
    context: str = "",
) -> list[Passage]:
    """Weighted keyword retrieval with synonym/prefix tolerance.

    Deterministic, no Gemini spend. Bigrams count double because phrases such
    as "notice period" are much stronger signals than single shared words.
    """
    q_words = _word_tokens(question) + _word_tokens(context or "")
    query_bigrams = _ngrams(q_words, 2)
    query_uni = set(q_words)
    if not query_uni and not query_bigrams:
        return passages[:k]
    scored: list[tuple[float, int, Passage]] = []
    for idx, passage in enumerate(passages):
        p_words = _word_tokens(passage.text)
        bigram_hits = len(query_bigrams & _ngrams(p_words, 2))
        unigram_hits = _fuzzy_hits(query_uni, set(p_words))
        overlap = bigram_hits * 2 + unigram_hits
        if overlap == 0:
            continue
        # Financial figures are high-value signals; weight when the question is about amounts.
        if re.search(r"\$|€|₹|rs\.|inr|amount|fee|deposit", question, re.I):
            amount_bonus = len(re.findall(r"\d[\d,]*(?:\.\d+)?", passage.text))
        else:
            amount_bonus = 0
        score = overlap * min(overlap, 6) + amount_bonus * 0.1
        scored.append((score, idx, passage))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:k]]


def passage_to_evidence(passages: list[Passage], limit_chars: int = 700) -> str:
    """Format retrieved passages as labeled evidence, sharing the budget fairly
    so later (often the most relevant) passages are not starved by the first."""
    if not passages:
        return ""
    per_passage = max(120, limit_chars // len(passages))
    parts = []
    budget = limit_chars
    for p in passages:
        if budget <= 0:
            break
        chunk = p.text[: min(per_passage, budget)]
        if not chunk:
            continue
        header = f"[Page {p.page}" + (f" | Section {p.section}]" if p.section else "]")
        parts.append(header + "\n" + chunk)
        budget -= len(chunk)
    return "\n\n".join(parts)


def clauses_context(clauses) -> str:
    """Compact clause list for prompting (keeps Gemini calls small)."""
    lines = []
    for i, clause in enumerate(clauses, start=1):
        lines.append(
            f"{i}. {clause.title} ({clause.category}, page {clause.source_page}"
            + (f", section {clause.source_section}" if clause.source_section else "")
            + f"): {clause.evidence[:300]}"
        )
    return "\n".join(lines)


def count_financial_matches(text: str) -> int:
    return len(re.findall(r"\d[\d,]*(?:\.\d+)?", text))