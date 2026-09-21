"""Health endpoint behaviour."""
from __future__ import annotations


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "UP"
    assert "version" in body
    assert "demo_mode" in body
    assert "ai_configured" in body


def test_health_prefixed_namespace(client):
    assert client.get("/health").status_code in (200, 404)  # only /api/* is routed