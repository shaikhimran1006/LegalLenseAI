"""Upload, extraction and document-record services."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.ai.guardrails import sanitize_for_storage
from app.db import repository
from app.engine.retrieval import DocumentExtractionError, extract_text, validate_file_name

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}
# Allow overriding the MIME-sniffing issue: we only check extension + magic bytes
# where possible, never trust the client MIME header alone.


def validate_upload(file: UploadFile, max_bytes: int) -> None:
    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="File must have an extension (pdf, txt, docx).")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a PDF, DOCX or TXT file.",
        )


def load_upload_bytes(file: UploadFile, max_bytes: int) -> bytes:
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return data


def save_to_temp(data: bytes, extension: str, upload_dir: Path) -> Path:
    """Persist the file for the duration of the request's analysis lifecycle.

    Files live in a git-ignored temp directory and are removed when analysis is
    complete (see services.analysis), so sensitive documents are not retained.
    """
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time() * 1000)}.{sanitize_for_storage(extension).strip('.') or 'bin'}"
    path = upload_dir / name
    path.write_bytes(data)
    return path


def remove_temp(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def process_upload(
    db,
    *,
    file: UploadFile,
    data: bytes,
    context: str,
    workspace_id: str,
    max_bytes: int,
) -> dict:
    ext = file.filename.rsplit(".", 1)[-1].lower()
    try:
        extracted = extract_text(data, ext, filename=file.filename)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc = repository.create_document(
        db,
        filename=validate_file_name(file.filename),
        extension=ext,
        page_count=extracted.page_count,
        size=len(data),
        context=context,
        workspace_id=workspace_id,
    )
    # Cache normalized page text so analysis/QA do not re-parse the binary.
    repository.save_analysis(
        db,
        doc,
        analysis_json=None,
        status="created",
        mode="ai",
        status_detail="",
        processed_text={"pages": extracted.pages, "text": extracted.text},
    )
    return {
        "id": doc.id,
        "filename": doc.filename,
        "extension": doc.extension,
        "page_count": doc.page_count,
        "size": doc.size,
        "status": doc.status,
        "context": doc.context,
    }