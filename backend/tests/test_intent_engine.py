import pytest

from app.services.plan_engine import IntentEngine


@pytest.mark.parametrize("reverse_mapping", [False, True])
@pytest.mark.parametrize(
    "category,query,expected",
    [
        ("scene", "上班 职场 面试", "work"),
        ("style", "裸妆 哑光 雾面", "matte"),
        ("intensity", "轻 重 深", "full"),
    ],
)
def test_parse_selects_value_with_most_keyword_matches(
    monkeypatch, reverse_mapping, category, query, expected
):
    """Verify the highest keyword score wins regardless of mapping order."""
    engine = IntentEngine()
    if reverse_mapping:
        attribute = f"{category.upper()}_KEYWORDS"
        mapping = getattr(engine, attribute)
        monkeypatch.setattr(engine, attribute, dict(reversed(list(mapping.items()))))

    params, confidence = engine.parse(query)

    assert getattr(params, category) == expected
    assert confidence == 1.0


@pytest.mark.parametrize("reverse_mapping", [False, True])
@pytest.mark.parametrize(
    "category,query,expected",
    [
        ("scene", "上班 约会", "daily"),
        ("style", "裸妆 哑光", "matte"),
        ("intensity", "轻 深", "full"),
    ],
)
def test_parse_breaks_ties_by_value_and_counts_all_matches_for_confidence(
    monkeypatch, reverse_mapping, category, query, expected
):
    """Verify ties use value order while confidence includes all keyword matches."""
    engine = IntentEngine()
    if reverse_mapping:
        attribute = f"{category.upper()}_KEYWORDS"
        mapping = getattr(engine, attribute)
        monkeypatch.setattr(engine, attribute, dict(reversed(list(mapping.items()))))

    params, confidence = engine.parse(query)

    assert getattr(params, category) == expected
    assert confidence == pytest.approx(2 / 3)


@pytest.mark.parametrize(
    "query,expected,confidence",
    [
        ("PARTY PARTY", ("party", "natural", "medium"), 1 / 3),
        ("哑光", ("daily", "matte", "medium"), 1 / 3),
        ("浅", ("daily", "natural", "light"), 1 / 3),
        ("派对 约会 哑光 雾面 浅", ("date", "matte", "light"), 1.0),
        ("日常 自然", ("daily", "natural", "light"), 1.0),
    ],
)
def test_parse_preserves_defaults_confidence_and_keyword_presence_counting(
    query, expected, confidence
):
    """Verify defaults and confidence count keyword presence rather than repetition."""
    params, actual_confidence = IntentEngine().parse(query)

    assert (params.scene, params.style, params.intensity) == expected
    assert actual_confidence == pytest.approx(confidence)


@pytest.mark.parametrize("query", ["", "hello"])
def test_parse_returns_none_when_no_keywords_match(query):
    """Verify unmatched queries return no parameters and zero confidence."""
    assert IntentEngine().parse(query) == (None, 0.0)


def test_get_best_match_returns_none_for_empty_scores():
    """Verify an empty score mapping has no best match."""
    assert IntentEngine()._get_best_match({}) is None
