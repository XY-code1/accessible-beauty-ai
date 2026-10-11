import json

import pytest
from pydantic import ValidationError

from app.services.knowledge_base import IngredientStore


def test_missing_catalog_aborts_construction(tmp_path):
    with pytest.raises(FileNotFoundError):
        IngredientStore(str(tmp_path / "missing.json"))


def test_invalid_json_aborts_construction(tmp_path):
    catalog = tmp_path / "ingredients.json"
    catalog.write_text("[", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        IngredientStore(str(catalog))


def test_invalid_ingredient_aborts_construction(tmp_path):
    catalog = tmp_path / "ingredients.json"
    catalog.write_text('[{"id": "incomplete"}]', encoding="utf-8")

    with pytest.raises(ValidationError):
        IngredientStore(str(catalog))
