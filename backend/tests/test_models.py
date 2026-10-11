import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import Ingredient, PlanRequest
from app.services.knowledge_base import IngredientStore


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "ingredients.json"


def test_catalog_loads_without_changing_values():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    ingredients = IngredientStore(str(CATALOG_PATH)).get_all()

    assert [ingredient.model_dump() for ingredient in ingredients] == catalog


@pytest.mark.parametrize(
    "field,value,location",
    [
        ("category", "unknown", ("category",)),
        ("cautionGroups", ["sensitive", "oily"], ("cautionGroups", 1)),
        ("cautionGroups", ["unknown"], ("cautionGroups", 0)),
    ],
)
def test_ingredient_rejects_unknown_catalog_values(field, value, location):
    ingredient = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))[0]
    ingredient[field] = value

    with pytest.raises(ValidationError) as error:
        Ingredient.model_validate(ingredient)

    assert error.value.errors()[0]["loc"] == location
    assert error.value.errors()[0]["type"] == "literal_error"


def test_plan_request_keeps_skin_type_open():
    request = PlanRequest.model_validate(
        {
            "parameters": {
                "scene": "daily",
                "style": "natural",
                "intensity": "light",
            },
            "profile": {"skinType": "combination"},
        }
    )

    assert request.profile.skinType == "combination"
