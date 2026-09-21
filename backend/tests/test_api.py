"""API integration tests for the full demo pipeline (no live Gemini needed)."""
from __future__ import annotations


def test_demo_docs_listed(client):
    r = client.get("/api/demo/documents")
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert "sample_employment" in ids
    assert "sample_contract_b" in ids


def test_demo_analysis_counts(client):
    r = client.post("/api/documents/sample_employment/analyze")
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "demo"
    assert body["analysis"]["attention_summary"] == {"high": 3, "medium": 6, "low": 11}
    assert body["analysis"]["document_type"] == "Employment Agreement"


def test_demo_ask_grounded(client):
    r = client.post(
        "/api/documents/sample_employment/ask",
        json={"question": "What happens if I resign after 8 months?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert body["answer"]["insufficient"] is False
    assert body["answer"]["answer"]
    assert any(e["page"] for e in body["answer"]["evidence"])


def test_demo_ask_insufficient(client):
    r = client.post(
        "/api/documents/sample_employment/ask",
        json={"question": "Does the document discuss the color of the office carpet?"},
    )
    assert r.status_code == 200
    # Either genuinely insufficient or answered with the closest clause; never hallucinated numbers.
    text = r.json()["answer"]["answer"].lower()
    assert "carpet" not in text


def test_ask_requires_question(client):
    r = client.post("/api/documents/sample_employment/ask", json={"question": " "})
    assert r.status_code == 422


def test_demo_action_pack(client):
    r = client.post(
        "/api/documents/sample_employment/action-pack",
        json={"context": "I am considering resigning after 8 months."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    pack = body["action_pack"]
    assert len(pack["important_clauses"]) > 0
    assert len(pack["questions_for_legal_professional"]) >= 3


def test_demo_compare(client):
    r = client.post(
        "/api/compare",
        json={"document_a_id": "sample_employment", "document_b_id": "sample_contract_b"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    rows = body["result"]["comparison_rows"]
    notice = next((row for row in rows if "notice" in row["area"].lower()), None)
    assert notice is not None
    assert "90" in notice["contract_b_value"] or "90" in notice["contract_b_value"]
    assert notice["a_source_page"] == 4 and notice["b_source_page"] == 4


def test_context_ranking_endpoint(client):
    r = client.get(
        "/api/documents/sample_employment/context-ranking",
        params={"context": "I am considering resigning after 8 months."},
    )
    assert r.status_code == 200
    ranked = r.json()["ranked_clauses"]
    assert len(ranked) > 0
    assert "relevance" in ranked[0]


def test_metadata_endpoints_404(client):
    assert client.get("/api/documents/nonexistent").status_code == 404
    assert client.get("/api/comparisons/nope").status_code == 404


def test_upload_and_list_workflow(client, txt_doc):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("covered.txt", txt_doc.read_bytes(), "text/plain")},
        data={"context": "employment"},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    docs = client.get("/api/documents", headers={"X-Workspace-Id": "ws-test-1"}).json()
    ids = [d["id"] for d in docs]
    assert doc_id not in ids  # different workspace scoping

    # Model-level (non-upload) analysis avoids Gemini by design in tests.
    detail = client.get(f"/api/documents/{doc_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "created"


def test_conversation_roundtrip(client):
    got = client.get("/api/documents/sample_employment/conversation")
    assert got.status_code == 200
    assert "messages" in got.json()


def test_upload_analyze_demo_fallback(client, txt_doc):
    """Uploaded documents must analyze offline via rule-based detection (previously 404)."""
    r = client.post(
        "/api/documents/upload",
        files={"file": ("covered.txt", txt_doc.read_bytes(), "text/plain")},
        data={"context": "employment"},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]

    r2 = client.post(f"/api/documents/{doc_id}/analyze")
    assert r2.status_code == 200
    body = r2.json()
    assert body["mode"] == "demo"
    assert len(body["analysis"]["important_clauses"]) >= 2
    summary = body["analysis"]["attention_summary"]
    assert summary["high"] + summary["medium"] + summary["low"] == len(body["analysis"]["important_clauses"])

    detail = client.get(f"/api/documents/{doc_id}")
    assert detail.json()["status"] == "analyzed"

    ask = client.post(
        f"/api/documents/{doc_id}/ask",
        json={"question": "What happens if I resign early?"},
    )
    assert ask.status_code == 200
    assert ask.json()["answer"]["insufficient"] is False


def test_upload_unanalyzable_analyze_conflict(client):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("gibberish.txt", b"Lorem ipsum dolor sit amet.", "text/plain")},
        data={"context": "other"},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]
    r2 = client.post(f"/api/documents/{doc_id}/analyze")
    assert r2.status_code == 409
    assert "No Gemini API key" in r2.json()["detail"]


def test_action_pack_works_for_uploaded_document(client, txt_doc):
    """Action Pack works for a real uploaded document, not only sample_employment."""
    r = client.post(
        "/api/documents/upload",
        files={"file": ("covered.txt", txt_doc.read_bytes(), "text/plain")},
        data={"context": "employment"},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]

    r2 = client.post(f"/api/documents/{doc_id}/analyze")
    assert r2.status_code == 200
    assert r2.json()["mode"] == "demo"

    pr = client.post(f"/api/documents/{doc_id}/action-pack", json={"context": "I may resign soon."})
    assert pr.status_code == 200
    body = pr.json()
    assert body["document_id"] == doc_id
    assert body["mode"] == "demo"
    pack = body["action_pack"]
    assert len(pack["important_clauses"]) > 0
    text = " ".join(pack["important_clauses"])
    assert "Notice period" in text


def test_action_pack_other_document_type(client, lease_doc):
    """Action Pack generates meaningful content for a lease document."""
    r = client.post(
        "/api/documents/upload",
        files={"file": ("lease.txt", lease_doc.read_bytes(), "text/plain")},
        data={"context": "lease"},
    )
    doc_id = r.json()["id"]

    r2 = client.post(f"/api/documents/{doc_id}/analyze")
    assert r2.status_code == 200

    pr = client.post(f"/api/documents/{doc_id}/action-pack", json={"context": ""})
    assert pr.status_code == 200
    body = pr.json()
    assert body["document_id"] == doc_id
    text = " ".join(body["action_pack"]["important_clauses"])
    assert "Notice period" in text or "Automatic renewal" in text


def test_action_pack_switching_documents(client, lease_doc):
    """Switching between documents produces distinct Action Packs."""
    sample_r = client.post(
        "/api/documents/sample_employment/action-pack",
        json={"context": "I am considering resigning after 8 months."},
    )
    assert sample_r.status_code == 200
    sample_pack = sample_r.json()["action_pack"]

    r = client.post(
        "/api/documents/upload",
        files={"file": ("lease.txt", lease_doc.read_bytes(), "text/plain")},
        data={"context": "lease"},
    )
    doc_id = r.json()["id"]
    assert client.post(f"/api/documents/{doc_id}/analyze").status_code == 200
    up_r = client.post(f"/api/documents/{doc_id}/action-pack", json={"context": ""})
    assert up_r.status_code == 200
    up_body = up_r.json()
    assert up_body["document_id"] == doc_id
    assert up_body["action_pack"] != sample_pack