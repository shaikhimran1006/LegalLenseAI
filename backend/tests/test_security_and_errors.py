"""Security + failure-path tests.

Covers graceful AI degradation (never a raw 500 when Gemini fails), magic-byte
validation, rate limiting, filename sanitization, and input-shape edge cases.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.deps import rate_limit
from app.core.config import Settings
from app.db import demo as demo_data
from app.db import repository
from app.db.database import SessionLocal
from app.engine.retrieval import validate_file_name
from app.services import action_pack as action_pack_service
from app.services import analysis as analysis_service
from app.services import compare as compare_service
from app.services import qa as qa_service


class _BoomClient:
    """A Gemini stub that reports as available but fails on every call, proving
    the services degrade gracefully instead of returning a raw 500."""

    available = True

    def generate_structured(self, *args, **kwargs):
        raise Exception("simulated Gemini outage")

    def generate_text(self, *args, **kwargs):
        raise Exception("simulated Gemini outage")


def _ai_settings() -> Settings:
    return Settings(force_demo=False, gemini_api_key="test-key-not-real")


def _seed_ai_document():
    """Create a stored, *analyzed* document whose mode is 'ai' (so services take
    the real-AI path and exercise their Gemini failure handling)."""
    db = SessionLocal()
    doc = repository.create_document(
        db,
        filename="seeded.txt",
        extension="txt",
        page_count=1,
        size=123,
        context="employment",
        workspace_id="public",
    )
    repository.save_analysis(
        db,
        doc,
        analysis_json=demo_data.demo_analysis("sample_employment"),
        status="analyzed",
        mode="ai",
        processed_text={"pages": demo_data.demo_pages("sample_employment"), "text": ""},
    )
    return db, doc


# ---------------------------------------------------------------------------
# Graceful AI degradation
# ---------------------------------------------------------------------------


def test_qa_gemini_failure_returns_insufficient_not_500():
    db, doc = _seed_ai_document()
    try:
        result = qa_service.answer_question(
            db,
            document_id=doc.id,
            workspace_id="public",
            question="What is the notice period?",
            context="",
            settings=_ai_settings(),
            client=_BoomClient(),
        )
        assert result["mode"] == "ai"
        assert result["answer"]["insufficient"] is True
        assert result["answer"]["answer"]
    finally:
        db.close()


def test_action_pack_gemini_failure_falls_back_to_demo():
    db, doc = _seed_ai_document()
    try:
        result = action_pack_service.build_action_pack(
            db,
            document_id=doc.id,
            workspace_id="public",
            context="",
            settings=_ai_settings(),
            client=_BoomClient(),
        )
        assert result["mode"] == "demo"
        assert result["action_pack"]["important_clauses"]
    finally:
        db.close()


def test_analysis_gemini_failure_returns_502():
    db, doc = _seed_ai_document()
    try:
        with pytest.raises(HTTPException) as exc:
            analysis_service.run_analysis(
                db,
                document_id=doc.id,
                workspace_id="public",
                settings=_ai_settings(),
                client=_BoomClient(),
            )
        assert exc.value.status_code == 502
    finally:
        db.close()


def test_compare_gemini_failure_returns_502():
    db, doc_a = _seed_ai_document()
    try:
        doc_b = repository.create_document(
            db, filename="b.txt", extension="txt", page_count=1, size=1, context="employment", workspace_id="public"
        )
        repository.save_analysis(
            db,
            doc_b,
            analysis_json=demo_data.demo_analysis("sample_contract_b"),
            status="analyzed",
            mode="ai",
            processed_text={"pages": demo_data.demo_pages("sample_contract_b"), "text": ""},
        )
        with pytest.raises(HTTPException) as exc:
            compare_service.compare_documents(
                db,
                document_a_id=doc_a.id,
                document_b_id=doc_b.id,
                workspace_id="public",
                settings=_ai_settings(),
                client=_BoomClient(),
            )
        assert exc.value.status_code == 502
    finally:
        db.close()


def test_explain_clause_demo_mode(client):
    r = client.post(
        "/api/documents/sample_employment/explain",
        json={"title": "Notice period"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert body["clause"]["title"]


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, host: str = "10.0.0.1", origin: str = "https://rl-test.example"):
        self.client = type("C", (), {"host": host})()
        self.headers = {"origin": origin}


def test_rate_limit_enforces_window():
    dep = rate_limit(max_requests=3)
    req = _FakeRequest()
    dep(req)
    dep(req)
    dep(req)
    with pytest.raises(HTTPException) as exc:
        dep(req)
    assert exc.value.status_code == 429


def test_rate_limit_respects_distinct_origins():
    dep = rate_limit(max_requests=1)
    dep(_FakeRequest(origin="https://a.example"))
    # Different origin = different bucket, must be allowed.
    dep(_FakeRequest(origin="https://b.example"))


# ---------------------------------------------------------------------------
# Input validation & filename sanitization
# ---------------------------------------------------------------------------


def test_upload_docx_magic_bytes_rejected(client):
    # DOCX is a ZIP; garbage bytes must not reach the parser.
    r = client.post(
        "/api/documents/upload",
        files={"file": ("fake.docx", b"\x00\x01\x02 not a zip at all", "application/octet-stream")},
        data={"context": "other"},
    )
    assert r.status_code == 422


def test_upload_pdf_magic_bytes_rejected(client):
    # A renamed .exe with .pdf extension must be rejected by magic bytes, not parsed.
    r = client.post(
        "/api/documents/upload",
        files={"file": ("malware.pdf", b"MZ\x90\x00this is actually an exe", "application/octet-stream")},
        data={"context": "other"},
    )
    assert r.status_code == 422


def test_upload_filename_sanitized(client, txt_doc):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("../evil<script>.txt", txt_doc.read_bytes(), "text/plain")},
        data={"context": "employment"},
    )
    assert r.status_code == 201
    name = r.json()["filename"]
    assert "/" not in name and "\\" not in name and "<" not in name and ">" not in name


def test_validate_file_name_strips_controls_and_separators():
    assert validate_file_name('..\\evil:name?.txt') == ".._evil_name_.txt"
    assert validate_file_name("\x00\x1f.exe") == "__.exe"
    assert validate_file_name("   ") == "document"
    assert len(validate_file_name("x" * 200)) <= 120


def test_ask_malformed_question_tuple_rejected(client):
    r = client.post("/api/documents/sample_employment/ask", json={"question": 12345})
    assert r.status_code == 422


def test_compare_missing_document_404(client):
    r = client.post(
        "/api/compare",
        json={"document_a_id": "sample_employment", "document_b_id": "does-not-exist"},
    )
    assert r.status_code == 404


def test_compare_unanalyzed_documents_409(client, txt_doc, lease_doc):
    a = client.post(
        "/api/documents/upload",
        files={"file": ("covered.txt", txt_doc.read_bytes(), "text/plain")},
        data={"context": "employment"},
    ).json()
    b = client.post(
        "/api/documents/upload",
        files={"file": ("lease.txt", lease_doc.read_bytes(), "text/plain")},
        data={"context": "lease"},
    ).json()
    r = client.post("/api/compare", json={"document_a_id": a["id"], "document_b_id": b["id"]})
    assert r.status_code == 409