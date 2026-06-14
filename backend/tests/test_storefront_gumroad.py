"""
Regression tests for the Gumroad storefront scraper (issue #286).

Gumroad's creator profile switched to an Inertia.js app: the old
`Accept: application/json` -> {"links": [...]} path returns nothing, so
enrichment silently produced an empty list. Products now live in the
HTML-escaped `data-page` JSON on `<div id="app">`. These tests pin that
parsing against a captured fixture and assert clear behaviour on bad input.
"""
import asyncio
import html as htmllib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scrapers import storefront

_FIXTURE = Path(__file__).parent / "fixtures" / "gumroad_carlos_profile.html"


def _run_scrape(html: str) -> list:
    """Run _scrape_gumroad against a single canned profile response."""
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()

    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(storefront.httpx, "AsyncClient", return_value=ctx):
        return asyncio.run(storefront._scrape_gumroad("https://carlosedu.gumroad.com/"))


def test_parses_products_from_inertia_page():
    products = _run_scrape(_FIXTURE.read_text(encoding="utf-8"))

    # Two sections, two products each, one permalink duplicated across them.
    assert [p.title for p in products] == ["Jinx 3D Print", "Cammy 3D Print", "Chun-Li 3D Print"]

    jinx = products[0]
    assert jinx.external_id == "gbifmz"
    assert jinx.source_site == "gumroad"
    assert jinx.source_url == "https://carlosedu.gumroad.com/l/gbifmz?layout=profile"
    assert jinx.thumbnail_url == "https://public-files.gumroad.com/jinxthumb"


def test_falls_back_to_built_url_when_product_url_missing():
    # Chun-Li has url=null in the fixture; we synthesise it from the permalink.
    products = _run_scrape(_FIXTURE.read_text(encoding="utf-8"))
    chunli = products[-1]
    assert chunli.source_url == "https://carlosedu.gumroad.com/l/chunli1"
    assert chunli.thumbnail_url is None


def test_missing_data_page_returns_empty():
    products = _run_scrape("<html><body><div id='app'></div></body></html>")
    assert products == []


def test_malformed_data_page_json_returns_empty():
    products = _run_scrape('<html><body><div id="app" data-page="{not json}"></div></body></html>')
    assert products == []


# ---------------------------------------------------------------------------
# Pagination (#316): page each section beyond its embedded first page via the
# products-search endpoint, scoped by section id + creator external_id.
# ---------------------------------------------------------------------------

def _product(permalink: str) -> dict:
    return {
        "permalink": permalink,
        "name": f"Model {permalink}",
        "thumbnail_url": f"https://files/{permalink}",
        "url": f"https://carlosedu.gumroad.com/l/{permalink}?layout=profile",
    }


def _profile_html(*, creator_id, section_id, total, embedded) -> str:
    data = {
        "component": "Users/Show",
        "props": {
            "creator_profile": {"external_id": creator_id, "subdomain": "carlosedu.gumroad.com"},
            "sections": [{
                "id": section_id,
                "type": "SellerProfileProductsSection",
                "search_results": {"total": total, "products": embedded},
            }],
        },
    }
    attr = htmllib.escape(json.dumps(data), quote=True)
    return f'<html><body><div id="app" data-page="{attr}"></div></body></html>'


def _run_paginating_scrape(profile_html: str, search_pages: dict[int, list[dict]]) -> list:
    """
    Drive _scrape_gumroad with a mock client that serves the profile page on the
    first GET and a products-search JSON page keyed by the `from` offset after.
    """
    calls: list = []

    async def fake_get(url, params=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.url = url
        if url.endswith("/products/search"):
            offset = params["from"]
            calls.append((params["section_id"], params["user_id"], offset))
            resp.json = MagicMock(return_value={"products": search_pages.get(offset, [])})
        else:
            resp.text = profile_html
        return resp

    client = MagicMock()
    client.get = AsyncMock(side_effect=fake_get)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.object(storefront.httpx, "AsyncClient", return_value=ctx):
        products = asyncio.run(storefront._scrape_gumroad("https://carlosedu.gumroad.com/"))
    return products, calls


def test_paginates_section_beyond_embedded_page():
    embedded = [_product("p0"), _product("p1")]
    # start=2, page size 9 → offsets 2 and 11 cover a total of 20.
    page_a = [_product(f"a{i}") for i in range(9)]
    page_b = [_product(f"b{i}") for i in range(9)]
    profile = _profile_html(creator_id="6680761514729", section_id="sec1==", total=20, embedded=embedded)

    products, calls = _run_paginating_scrape(profile, {2: page_a, 11: page_b})

    permalinks = [p.external_id for p in products]
    assert permalinks == ["p0", "p1"] + [f"a{i}" for i in range(9)] + [f"b{i}" for i in range(9)]
    # Correct endpoint scoping + offsets requested.
    assert sorted(c[2] for c in calls) == [2, 11]
    assert all(c[0] == "sec1==" and c[1] == "6680761514729" for c in calls)


def test_pagination_dedupes_across_pages():
    embedded = [_product("dup")]
    page = [_product("dup"), _product("fresh")]
    profile = _profile_html(creator_id="cid", section_id="s", total=3, embedded=embedded)

    products, _ = _run_paginating_scrape(profile, {1: page})

    assert [p.external_id for p in products] == ["dup", "fresh"]


def test_no_pagination_without_creator_id():
    # Existing fixture has no creator_profile.external_id → embedded page only.
    products = _run_scrape(_FIXTURE.read_text(encoding="utf-8"))
    assert [p.external_id for p in products] == ["gbifmz", "puvuyi", "chunli1"]
