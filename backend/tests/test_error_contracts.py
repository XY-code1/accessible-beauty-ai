import asyncio
import json

from fastapi.testclient import TestClient

from app.api import intent, plan
from main import app, global_exception_handler


client = TestClient(app)


def test_intent_failure_uses_stable_public_message(monkeypatch):
    """Verify intent failures fall back without exposing internal exception details."""
    monkeypatch.setattr(
        intent._intent_engine,
        "parse",
        lambda _query: (_ for _ in ()).throw(RuntimeError("secret path")),
    )

    response = client.post("/api/intent", json={"query": "自然日常妆"})

    assert response.status_code == 200
    body = response.json()
    assert body["fallback"] is True
    assert body["message"].startswith("INTENT_FALLBACK:")
    assert "secret path" not in body["message"]


def test_plan_failure_uses_stable_public_message(monkeypatch):
    """Verify plan failures return a stable code without exposing exception details."""
    monkeypatch.setattr(
        plan,
        "get_plan_engine",
        lambda: (_ for _ in ()).throw(RuntimeError("secret path")),
    )

    response = client.post(
        "/api/plan",
        json={
            "parameters": {
                "scene": "daily",
                "style": "natural",
                "intensity": "light",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"].startswith("PLAN_GENERATION_FAILED:")
    assert "secret path" not in body["message"]


def test_global_error_handler_uses_stable_public_contract():
    """Verify unhandled errors return the generic JSON contract with HTTP 500."""
    response = asyncio.run(
        global_exception_handler(None, RuntimeError("secret path"))
    )
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body == {
        "success": False,
        "code": "INTERNAL_SERVER_ERROR",
        "message": "服务器内部错误，请稍后重试",
    }
