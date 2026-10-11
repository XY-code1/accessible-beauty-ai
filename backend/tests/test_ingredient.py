import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import ingredient
from app.services.knowledge_base import IngredientStore
from main import app


@pytest.mark.parametrize(
    ("catalog_content", "error_type"),
    [
        (None, FileNotFoundError),
        ("[", json.JSONDecodeError),
        ('[{"id": "incomplete"}]', ValidationError),
    ],
)
def test_ingredient_initialization_errors_propagate(
    monkeypatch, tmp_path, catalog_content, error_type
):
    catalog = tmp_path / "ingredients.json"
    if catalog_content is not None:
        catalog.write_text(catalog_content, encoding="utf-8")
    monkeypatch.setattr(ingredient, "_ingredient_store", None)
    monkeypatch.setattr(
        ingredient, "IngredientStore", lambda _path: IngredientStore(str(catalog))
    )

    with TestClient(app) as client:
        with pytest.raises(error_type):
            client.get("/api/ingredient/ing_001")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/ingredient/ing_001")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_SERVER_ERROR"


@pytest.mark.parametrize("ingredient_id", ["ing_001", "unknown"])
def test_ingredient_lookup_preserves_nullable_result(monkeypatch, ingredient_id):
    store = IngredientStore("data/ingredients.json")
    monkeypatch.setattr(ingredient, "_ingredient_store", store)

    with TestClient(app) as client:
        response = client.get(f"/api/ingredient/{ingredient_id}")

    assert response.status_code == 200
    expected = store.get_by_id(ingredient_id)
    assert response.json() == (expected.model_dump() if expected else None)
