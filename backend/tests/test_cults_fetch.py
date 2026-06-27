"""Cults3D detail mapping: _to_scraped_model carries the full field set.

Regression guard for the gap where category + license were dropped because the
GraphQL fetch query never requested them.
"""
from app.services.scrapers import cults3d


def _creation(**overrides) -> dict:
    c = {
        "name": "Goblin Warband",
        "description": "Ten goblins for the horde.",
        "shortUrl": "https://cults3d.com/en/3d-model/game/goblin-warband",
        "illustrationImageUrl": "https://cults.example/cover.jpg",
        "tags": ["goblin", "fantasy"],
        "license": {"name": "Standard Cults License", "code": "standard"},
        "category": {"name": "Game"},
        "likesCount": 42,
        "downloadsCount": 7,
        "creator": {"nick": "GoblinSmith"},
        "illustrations": [{"imageUrl": "https://cults.example/g1.jpg"}],
        "blueprints": [],
    }
    c.update(overrides)
    return c


def test_maps_category_and_license():
    m = cults3d._to_scraped_model(_creation(), "https://cults3d.com/x", "goblin-warband")
    assert m.category == "Game"
    assert m.license == "Standard Cults License"


def test_maps_core_fields():
    m = cults3d._to_scraped_model(_creation(), "https://cults3d.com/x", "goblin-warband")
    assert m.title == "Goblin Warband"
    assert m.description == "Ten goblins for the horde."
    assert m.tags == ["goblin", "fantasy"]
    assert m.creator_name == "GoblinSmith"
    assert m.like_count == 42
    assert m.download_count == 7
    assert m.source_site == "cults3d"
    assert "https://cults.example/cover.jpg" in m.image_urls


def test_missing_category_and_license_are_none():
    m = cults3d._to_scraped_model(
        _creation(license=None, category=None), "https://cults3d.com/x", "slug"
    )
    assert m.category is None
    assert m.license is None
