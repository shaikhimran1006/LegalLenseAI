"""Demo-mode data: loads the fictional seed documents and analyses.

DEMO MODE is a controlled, pre-computed experience so judges can explore the
product instantly and reliably. It uses the exact same schemas as REAL AI MODE
but reads a curated seed file instead of calling Gemini. The user can opt back
into a live Gemini analysis ("Re-run with AI") for the demo document.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from app.core.config import get_settings


class DemoSeedError(RuntimeError):
    pass


@lru_cache
def load_seed() -> dict[str, Any]:
    settings = get_settings()
    try:
        with open(settings.demo_seed, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise DemoSeedError(f"Demo seed file not found: {settings.demo_seed}") from exc
    except json.JSONDecodeError as exc:
        raise DemoSeedError("Demo seed file is corrupted.") from exc


def list_demo_documents() -> list[dict[str, Any]]:
    seed = load_seed()
    return [
        {
            "id": doc["id"],
            "filename": doc["filename"],
            "extension": doc["extension"],
            "context": doc["context"],
            "page_count": doc["page_count"],
            "size": 200_000,  # synthetic size, not a real file
            "status": "analyzed",
            "mode": "demo",
        }
        for doc in seed.get("documents", [])
    ]


def get_demo_document(document_id: str) -> Optional[dict[str, Any]]:
    for doc in seed_documents():
        if doc["id"] == document_id:
            return doc
    return None


def seed_documents() -> list[dict[str, Any]]:
    return load_seed().get("documents", [])


def demo_analysis(document_id: str) -> Optional[dict[str, Any]]:
    doc = get_demo_document(document_id)
    return doc["analysis"] if doc else None


def demo_comparison(comparison_id: str) -> Optional[dict[str, Any]]:
    for item in load_seed().get("comparisons", []):
        if item["id"] == comparison_id:
            return item
    return None


def demo_pages(document_id: str) -> list[str]:
    doc = get_demo_document(document_id)
    return doc.get("pages", []) if doc else []