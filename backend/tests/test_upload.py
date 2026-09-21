"""Upload validation tests."""
from __future__ import annotations

import io


def _upload(client, filename: str, content: bytes, context: str = "employment"):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        data={"context": context},
    )


def test_upload_txt_ok(client, txt_doc):
    r = _upload(client, "sample.txt", txt_doc.read_bytes())
    assert r.status_code == 201
    body = r.json()
    assert body["filename"] == "sample.txt"
    assert body["extension"] == "txt"
    assert body["status"] == "created"
    assert body["page_count"] == 1
    assert body["context"] == "employment"


def test_upload_invalid_extension(client):
    r = _upload(client, "malware.exe", b"MZ....")
    assert r.status_code == 415


def test_upload_empty_file(client):
    r = _upload(client, "empty.txt", b"")
    assert r.status_code == 400


def test_upload_too_large(client):
    size = (20 * 1024 * 1024) + 1
    r = _upload(client, "big.txt", b"x" * size)
    assert r.status_code == 413


def test_upload_corrupt_pdf(client):
    r = _upload(client, "broken.pdf", b"not a real pdf at all")
    assert r.status_code == 422
    assert "detail" in r.json()


def test_upload_scanned_pdf_no_text(client, untrusted_pdf_bytes):
    # This PDF has no text-extract path errors but we can check TTF handling elsewhere.
    r = _upload(client, "scan.pdf", untrusted_pdf_bytes)
    assert r.status_code in (201, 422)


def test_upload_unknown_context_normalized(client, txt_doc):
    r = _upload(client, "sample.txt", txt_doc.read_bytes(), context=" Weird Context ")
    assert r.status_code == 201
    assert r.json()["context"] == "weird" or r.json()["context"].startswith("weird")