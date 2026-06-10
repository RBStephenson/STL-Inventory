"""Tests for the app_settings key/value store (#180)."""


def test_get_settings_returns_defaults(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert r.json() == {"painting_guides_enabled": False}


def test_patch_updates_and_persists(client):
    r = client.patch("/settings", json={"painting_guides_enabled": True})
    assert r.status_code == 200
    assert r.json()["painting_guides_enabled"] is True

    # Stored, not just echoed — a fresh GET reads it back from the DB.
    assert client.get("/settings").json()["painting_guides_enabled"] is True


def test_patch_toggle_back_off(client):
    client.patch("/settings", json={"painting_guides_enabled": True})
    r = client.patch("/settings", json={"painting_guides_enabled": False})
    assert r.status_code == 200
    assert client.get("/settings").json()["painting_guides_enabled"] is False


def test_patch_empty_body_is_a_noop(client):
    r = client.patch("/settings", json={})
    assert r.status_code == 200
    assert r.json() == {"painting_guides_enabled": False}


def test_patch_unknown_key_rejected(client):
    r = client.patch("/settings", json={"bogus_key": 1})
    assert r.status_code == 422


def test_patch_non_bool_value_rejected(client):
    r = client.patch("/settings", json={"painting_guides_enabled": "definitely"})
    assert r.status_code == 422


def test_patch_null_value_leaves_setting_unchanged(client):
    client.patch("/settings", json={"painting_guides_enabled": True})
    r = client.patch("/settings", json={"painting_guides_enabled": None})
    assert r.status_code == 200
    assert r.json()["painting_guides_enabled"] is True
