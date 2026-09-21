"""Prompt-injection defense and untrusted-content handling."""
from __future__ import annotations

import re

from app.ai.prompts import UNTRUSTED_CLOSE, UNTRUSTED_OPEN

# Common injection patterns found inside hostile documents.
INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore-prior", re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I)),
    ("system", re.compile(r"reveal\s+your\s+system\s+prompt", re.I)),
    ("new-instructions", re.compile(r"disregard\s+(prior|earlier|above)\s+instructions?", re.I)),
    ("pretend", re.compile(r"(act\s+as\s+if|pretend\s+you(?:'re| are))\s+", re.I)),
    ("exfil", re.compile(r"send\s+this\s+(document|text|content)\s+to\s+", re.I)),
    ("output-format", re.compile(r"output\s+your\s+(system\s+)?prompt", re.I)),
    ("skip-model", re.compile(r"you\s+are\s+not\s+(an?\s+)?(ai|llm|model)", re.I)),
    ("override", re.compile(r"override\s+(your|these|all)\s+(instructions|rules)", re.I)),
]


def detect_injection(text: str | None) -> list[str]:
    """Scan untrusted text for obvious prompt-injection phrasing.

    Used for logging/diagnostics and tests. The primary defense is architectural:
    document content is always wrapped in untrusted-data markers before reaching
    the model (see prompts.wrap_untrusted) and system policy forbids following
    embedded instructions.
    """
    if not text:
        return []
    hits: list[str] = []
    for name, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(name)
    return hits


def sanitize_for_storage(text: str | None) -> str:
    """Strip zero-width / control characters that can be used to hide instruction text."""
    if not text:
        return ""
    text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff]", "", text)
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)


def assert_wrapped(document_text: str, injection_sample: str | None = None) -> None:
    """Raise if the wrapped document content marker is missing (defense misconfiguration)."""
    if UNTRUSTED_OPEN not in document_text or UNTRUSTED_CLOSE not in document_text:
        raise RuntimeError("untrusted document content was not wrapped before LLM call")
    if injection_sample and not document_text.startswith(UNTRUSTED_OPEN):
        raise RuntimeError("untrusted block markers must open the document content")

def neutralize_embedded_instructions(document_text: str) -> str:
    """Return a copy of untrusted text that has been rendered instruction-ineffective.

    We do not remove content (it is evidence), but we:
    - prefix every line inside the block so any directive reads as quoted material,
    - collapse line-level instruction starts to harmless text.
    This is defense-in-depth layered on top of marker wrapping and the system policy.
    """
    if not document_text:
        return ""
    lines = document_text.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if re.search(r"(?i)^(ignore|disregard|forget|you must|remember to|act as|pretend|reveal|output|now)\b", stripped):
            out.append("[document quote] " + line)
        else:
            out.append(line)
    return "\n".join(out)