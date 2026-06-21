"""Tests for the bulk-set store-page endpoint (#500): set one source_url on a
SELECTED set of variants. Selection-scoped + overwriting, with NO fill-empty
propagation to unselected siblings (distinct from the single-model path #202).
"""
from tests.conftest import make_creator, make_model

URL = "https://www.myminifactory.com/object/print-ada-wong-12345"
ENDPOINT = "/models/group/source-url"


def _group(db, n=3, character="Ada Wong"):
    creator = make_creator(db)
    models = [
        make_model(db, creator, name=f"Ada Wong v{i}", character=character)
        for i in range(n)
    ]
    db.commit()
    return creator, models


class TestBulkSetSourceUrl:
    def test_sets_url_and_derives_known_site(self, client, db):
        _, (a, b, _c) = _group(db)
        resp = client.post(ENDPOINT, json={"model_ids": [a.id, b.id], "source_url": URL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_site"] == "myminifactory"
        assert sorted(body["updated"]) == sorted([a.id, b.id])
        for m in (a, b):
            db.refresh(m)
            assert m.source_url == URL
            assert m.source_site == "myminifactory"
            assert m.source_last_fetched is not None

    def test_overwrites_existing_url_on_selected(self, client, db):
        _, (a, _b, _c) = _group(db)
        a.source_url = "https://cults3d.com/old-listing"
        a.source_site = "cults3d"
        db.commit()

        resp = client.post(ENDPOINT, json={"model_ids": [a.id], "source_url": URL})
        assert resp.status_code == 200

        db.refresh(a)
        assert a.source_url == URL
        assert a.source_site == "myminifactory"

    def test_unselected_siblings_untouched(self, client, db):
        """No fill-empty propagation — only the selected ids change."""
        _, (a, b, c) = _group(db)
        resp = client.post(ENDPOINT, json={"model_ids": [a.id], "source_url": URL})
        assert resp.status_code == 200

        for sib in (b, c):
            db.refresh(sib)
            assert sib.source_url is None
            assert sib.source_site is None

    def test_other_groups_and_creators_untouched(self, client, db):
        creator, (a, *_) = _group(db)
        other_group = make_model(db, creator, name="Leon", character="Leon Kennedy")
        other_creator = make_creator(db, name="Other Studio")
        clone = make_model(db, other_creator, name="Ada Clone", character="Ada Wong")
        db.commit()

        client.post(ENDPOINT, json={"model_ids": [a.id], "source_url": URL})

        for m in (other_group, clone):
            db.refresh(m)
            assert m.source_url is None

    def test_unknown_ids_reported_as_missing(self, client, db):
        _, (a, *_) = _group(db)
        resp = client.post(ENDPOINT, json={"model_ids": [a.id, 999999], "source_url": URL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["updated"] == [a.id]
        assert body["missing"] == [999999]

    def test_unscraped_store_falls_back_to_hostname(self, client, db):
        _, (a, *_) = _group(db)
        resp = client.post(
            ENDPOINT,
            json={"model_ids": [a.id], "source_url": "https://www.patreon.com/posts/123"},
        )
        assert resp.status_code == 200
        assert resp.json()["source_site"] == "patreon.com"
        db.refresh(a)
        assert a.source_site == "patreon.com"

    def test_blank_url_rejected(self, client, db):
        _, (a, *_) = _group(db)
        resp = client.post(ENDPOINT, json={"model_ids": [a.id], "source_url": "   "})
        assert resp.status_code == 400

    def test_empty_ids_rejected(self, client, db):
        resp = client.post(ENDPOINT, json={"model_ids": [], "source_url": URL})
        assert resp.status_code == 400

    def test_scan_running_returns_409(self, client, db, monkeypatch):
        from app.services import scanner
        monkeypatch.setattr(scanner, "get_status", lambda: {"running": True})
        _, (a, *_) = _group(db)
        resp = client.post(ENDPOINT, json={"model_ids": [a.id], "source_url": URL})
        assert resp.status_code == 409
