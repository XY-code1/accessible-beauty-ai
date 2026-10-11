from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_contract():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == app.version
    assert isinstance(body["timestamp"], float)


def test_health_is_documented_in_openapi():
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/HealthResponse"}
