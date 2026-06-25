"""Reference-image fallback chain — STL-folder (rung 0) + from-URL (rung 4),
with provenance (#494, spec §4.4 / §8.5).

The data dir is redirected to a tmp path so stored copies don't touch the real
volume; model folder images live under the test STL root (conftest sets
STL_ROOTS=/tmp) so the scan-root safety guard accepts them.
"""
import asyncio
import io

import pytest
from PIL import Image

from app.models import Model
from app.painting.models import Guide, GuideReferenceImage
from app.painting.services import images
from app.services.thumbnails import ThumbnailDownloadError


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "data_dir", lambda: tmp_path)
    return tmp_path


def _png_bytes(size=(16, 16), color=(120, 80, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _write_image(path, size=(16, 16)):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes(size))
    return str(path)


def _model_with_images(db, tmp_path, *, thumb=True, extra=0):
    """Create a Model whose folder images live under the test STL root."""
    folder = tmp_path / "models" / "creator" / "fig"
    thumb_path = _write_image(folder / "thumb.png") if thumb else None
    extras = [_write_image(folder / f"img{i}.png") for i in range(extra)]
    model = Model(
        name="Fig",
        folder_path=str(folder),
        thumbnail_path=thumb_path,
        image_paths=extras,
    )
    db.add(model)
    db.commit()
    return model


def _guide(db, model=None, slug="presto") -> Guide:
    g = Guide(slug=slug, title="Presto", model_id=model.id if model else None)
    db.add(g)
    db.commit()
    return g


# ---------------------------------------------------------------------------
# Rung 0 — STL model folder candidates
# ---------------------------------------------------------------------------

class TestModelCandidates:
    def test_lists_thumbnail_first_then_image_paths(self, db, tmp_path):
        model = _model_with_images(db, tmp_path, thumb=True, extra=2)
        guide = _guide(db, model)

        candidates = images.list_model_candidates(db, guide)

        assert candidates[0] == model.thumbnail_path
        assert set(candidates) == {model.thumbnail_path, *model.image_paths}

    def test_empty_without_linked_model(self, db, tmp_path):
        guide = _guide(db, model=None)
        assert images.list_model_candidates(db, guide) == []

    def test_dedupes_and_drops_missing_files(self, db, tmp_path):
        model = _model_with_images(db, tmp_path, thumb=True, extra=1)
        # thumbnail repeated in image_paths + a path that doesn't exist on disk.
        model.image_paths = [model.thumbnail_path, str(tmp_path / "gone.png")]
        db.commit()
        guide = _guide(db, model)

        candidates = images.list_model_candidates(db, guide)
        assert candidates == [model.thumbnail_path]

    def test_drops_paths_outside_scan_root(self, db, tmp_path, monkeypatch):
        model = _model_with_images(db, tmp_path, thumb=True)
        # An absolute path outside STL_ROOTS must be refused even if it exists.
        outside = _write_image(tmp_path.parent / "outside.png")
        monkeypatch.setattr("app.routers.files._allowed_roots",
                            lambda: [tmp_path / "models"])
        model.thumbnail_path = outside
        model.image_paths = []
        db.commit()
        guide = _guide(db, model)

        assert images.list_model_candidates(db, guide) == []


class TestStoreFromModel:
    def test_copies_bytes_with_provenance(self, db, tmp_path):
        model = _model_with_images(db, tmp_path, thumb=True)
        guide = _guide(db, model)

        row = images.store_from_model(db, guide, model.thumbnail_path, alt_text="box art")
        db.commit()

        assert row.provenance == "stl_model_folder"
        assert row.source_url is None
        assert row.alt_text == "box art"
        assert guide.reference_image_id == row.id
        assert (tmp_path / row.storage_key).exists()

    def test_rejects_path_not_in_candidates(self, db, tmp_path):
        model = _model_with_images(db, tmp_path, thumb=True)
        guide = _guide(db, model)
        sneaky = _write_image(tmp_path / "models" / "creator" / "fig" / "other.png")

        with pytest.raises(images.ReferenceImageError):
            images.store_from_model(db, guide, sneaky)


# ---------------------------------------------------------------------------
# Rung 4 — user-supplied URL
# ---------------------------------------------------------------------------

@pytest.fixture
def _allow_url(monkeypatch):
    """Bypass the SSRF resolver so fetch-focused tests don't hit real DNS."""
    monkeypatch.setattr(images, "_assert_fetchable_url", lambda url: None)


def _fake_addrinfo(ip):
    return lambda host, port, **kw: [(None, None, None, "", (ip, 0))]


class TestStoreFromUrl:
    def test_stores_with_attribution(self, db, monkeypatch, _allow_url):
        guide = _guide(db)

        async def fake_fetch(url, **kw):
            return ".png", _png_bytes((20, 10))

        monkeypatch.setattr(images, "fetch_image_bytes", fake_fetch)
        row = asyncio.run(
            images.store_from_url(db, guide, "https://example.com/fig.png")
        )
        db.commit()

        assert row.provenance == "web_research"
        assert row.source_url == "https://example.com/fig.png"
        assert (row.width, row.height) == (20, 10)
        assert guide.reference_image_id == row.id

    def test_download_failure_becomes_reference_error(self, db, monkeypatch, _allow_url):
        guide = _guide(db)

        async def boom(url, **kw):
            raise ThumbnailDownloadError("nope")

        monkeypatch.setattr(images, "fetch_image_bytes", boom)
        with pytest.raises(images.ReferenceImageError, match="nope"):
            asyncio.run(images.store_from_url(db, guide, "https://x/y.png"))


class TestSsrfGuard:
    def test_rejects_non_http_scheme(self, db):
        with pytest.raises(images.ReferenceImageError, match="http"):
            images._assert_fetchable_url("file:///etc/passwd")

    @pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"])
    def test_rejects_non_public_addresses(self, db, monkeypatch, ip):
        # Covers loopback, private, the cloud metadata endpoint, and IPv6 loopback.
        monkeypatch.setattr(images.socket, "getaddrinfo", _fake_addrinfo(ip))
        with pytest.raises(images.ReferenceImageError, match="non-public"):
            images._assert_fetchable_url("https://evil.test/a.png")

    def test_allows_public_address(self, db, monkeypatch):
        monkeypatch.setattr(images.socket, "getaddrinfo", _fake_addrinfo("93.184.216.34"))
        images._assert_fetchable_url("https://example.com/a.png")  # no raise

    def test_store_from_url_blocks_internal_target(self, db, monkeypatch):
        guide = _guide(db)
        monkeypatch.setattr(images.socket, "getaddrinfo", _fake_addrinfo("127.0.0.1"))

        async def fetched(url, **kw):  # must never be reached
            raise AssertionError("fetch attempted on a blocked URL")

        monkeypatch.setattr(images, "fetch_image_bytes", fetched)
        with pytest.raises(images.ReferenceImageError, match="non-public"):
            asyncio.run(images.store_from_url(db, guide, "http://localhost/admin"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class TestEndpoints:
    def test_candidates_endpoint(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr(images, "data_dir", lambda: tmp_path)
        model = _model_with_images(db, tmp_path, thumb=True, extra=1)
        guide = _guide(db, model)

        resp = client.get(f"/painting/guides/{guide.id}/reference-image/candidates")
        assert resp.status_code == 200
        assert resp.json()["candidates"][0] == model.thumbnail_path

    def test_from_model_endpoint(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr(images, "data_dir", lambda: tmp_path)
        model = _model_with_images(db, tmp_path, thumb=True)
        guide = _guide(db, model)

        resp = client.post(
            f"/painting/guides/{guide.id}/reference-image/from-model",
            json={"path": model.thumbnail_path},
        )
        assert resp.status_code == 201
        assert resp.json()["provenance"] == "stl_model_folder"

    def test_from_url_endpoint(self, client, db, tmp_path, monkeypatch, _allow_url):
        monkeypatch.setattr(images, "data_dir", lambda: tmp_path)
        guide = _guide(db)

        async def fake_fetch(url, **kw):
            return ".png", _png_bytes()

        monkeypatch.setattr(images, "fetch_image_bytes", fake_fetch)
        resp = client.post(
            f"/painting/guides/{guide.id}/reference-image/from-url",
            json={"url": "https://example.com/a.png", "alt_text": "ref"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["provenance"] == "web_research"
        assert body["source_url"] == "https://example.com/a.png"

    def test_from_url_endpoint_surfaces_fetch_failure(
        self, client, db, monkeypatch, _allow_url
    ):
        guide = _guide(db)

        async def boom(url, **kw):
            raise ThumbnailDownloadError("bad url")

        monkeypatch.setattr(images, "fetch_image_bytes", boom)
        resp = client.post(
            f"/painting/guides/{guide.id}/reference-image/from-url",
            json={"url": "https://x/y.png"},
        )
        assert resp.status_code == 422
