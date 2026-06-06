"""
Tests for the Loot Studios scraper.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.scrapers.loot_studios import extract_id, _parse, SITE
from app.services.scrapers.base import detect_site


# ---------------------------------------------------------------------------
# detect_site integration
# ---------------------------------------------------------------------------

class TestDetectSite:
    @pytest.mark.parametrize("url", [
        "https://app.lootstudios.com/bundle/elemental-revenge/",
        "https://app.lootstudios.com/bundle/chaos-warriors",
        "https://lootstudios.com/bundle/some-set/",
    ])
    def test_loot_studios_urls_detected(self, url):
        assert detect_site(url) == "loot-studios"

    @pytest.mark.parametrize("url", [
        "https://lootstudios.com.evil.com/bundle/foo",
        "https://evil.com/?x=lootstudios.com",
        "https://app.lootstudios.com/bundle-store/",  # store listing, no slug → still detected
    ])
    def test_lookalike_or_store_listing(self, url):
        # Store listing is still on lootstudios.com — it WILL detect as loot-studios
        # but extract_id will return None (no /bundle/{slug}/ pattern)
        result = detect_site(url)
        if "evil.com" in url:
            assert result is None
        else:
            assert result == "loot-studios"


# ---------------------------------------------------------------------------
# extract_id
# ---------------------------------------------------------------------------

class TestExtractId:
    @pytest.mark.parametrize("url,expected", [
        ("https://app.lootstudios.com/bundle/elemental-revenge/", "elemental-revenge"),
        ("https://app.lootstudios.com/bundle/chaos-warriors-2024", "chaos-warriors-2024"),
        ("https://lootstudios.com/bundle/sky-pirates/", "sky-pirates"),
    ])
    def test_extracts_slug(self, url, expected):
        assert extract_id(url) == expected

    @pytest.mark.parametrize("url", [
        "https://app.lootstudios.com/bundle-store/",
        "https://app.lootstudios.com/",
        "https://example.com/other/page",
    ])
    def test_returns_none_for_non_bundle_urls(self, url):
        assert extract_id(url) is None


# ---------------------------------------------------------------------------
# _parse
# ---------------------------------------------------------------------------

_BUNDLE_HTML = """
<html>
<body>
  <h1>Elemental Revenge</h1>
  <img src="https://app.lootstudios.com/wp-content/uploads/2024/01/cover.jpg" />
  <img src="https://assets.loot-studios.com/bundles/elemental-revenge/preview1.jpg" />
  <img src="https://assets.loot-studios.com/bundles/elemental-revenge/preview2.jpg" />
  <div class="tags">
    <a class="tag">Fantasy</a>
    <a class="tag">Dragons</a>
  </div>
</body>
</html>
"""

_BUNDLE_NO_H1_HTML = """
<html><body><p>No title here</p></body></html>
"""

_BUNDLE_CDN_ONLY_HTML = """
<html>
<body>
  <h1>Sky Pirates</h1>
  <img src="https://assets.loot-studios.com/bundles/sky/cover.jpg" />
</body>
</html>
"""


class TestParse:
    def test_extracts_title(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert result is not None
        assert result.title == "Elemental Revenge"

    def test_extracts_thumbnail_from_wp_content(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert result.thumbnail_url == "https://app.lootstudios.com/wp-content/uploads/2024/01/cover.jpg"

    def test_extracts_cdn_gallery_images(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert len(result.image_urls) == 2
        assert all("assets.loot-studios.com" in u for u in result.image_urls)

    def test_falls_back_to_cdn_thumbnail_when_no_wp_content(self):
        result = _parse(_BUNDLE_CDN_ONLY_HTML, "https://app.lootstudios.com/bundle/sky-pirates/")
        assert result.thumbnail_url == "https://assets.loot-studios.com/bundles/sky/cover.jpg"

    def test_extracts_tags(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert "Fantasy" in result.tags
        assert "Dragons" in result.tags

    def test_creator_is_always_loot_studios(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert result.creator_name == "Loot Studios"

    def test_site_is_loot_studios(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert result.source_site == SITE

    def test_external_id_from_slug(self):
        result = _parse(_BUNDLE_HTML, "https://app.lootstudios.com/bundle/elemental-revenge/")
        assert result.external_id == "elemental-revenge"

    def test_returns_none_when_no_title(self):
        result = _parse(_BUNDLE_NO_H1_HTML, "https://app.lootstudios.com/bundle/empty/")
        assert result is None


# ---------------------------------------------------------------------------
# fetch (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetch:
    def test_returns_none_on_http_error(self):
        import asyncio
        from app.services.scrapers.loot_studios import fetch
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = Exception("connection refused")
            mock_client_cls.return_value = mock_client

            result = asyncio.run(fetch("https://app.lootstudios.com/bundle/test/"))
        assert result is None

    def test_returns_scraped_model_on_success(self):
        import asyncio
        from app.services.scrapers.loot_studios import fetch
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = _BUNDLE_HTML
        mock_response.url = "https://app.lootstudios.com/bundle/elemental-revenge/"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(fetch("https://app.lootstudios.com/bundle/elemental-revenge/"))

        assert result is not None
        assert result.title == "Elemental Revenge"
        assert result.creator_name == "Loot Studios"
