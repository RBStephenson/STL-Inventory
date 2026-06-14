"""
Regression tests for the single-product Gumroad scraper (issue #317).

Gumroad's Inertia app emits Open Graph tags with a `value=` attribute on
og:title / og:description (and `content=` on og:image). The scraper's `og()`
helper previously read `content` only, so title/description/thumbnail came back
None and product enrichment fell through. These tests pin the `value=`/`content=`
parsing against a trimmed capture of a real product page.
"""
import html as htmllib
import json
from pathlib import Path

from app.services.scrapers import gumroad

_FIXTURE = Path(__file__).parent / "fixtures" / "gumroad_qb01_product.html"
_URL = "https://francisquez.gumroad.com/l/qb01jshark"


def test_parses_value_attribute_og_tags():
    model = gumroad._parse(_FIXTURE.read_text(encoding="utf-8"), _URL)

    assert model is not None
    assert model.title == "QB01: J. Shark - 3D printing model"
    assert model.description.startswith("Hi!Q- Bestiary #01: J. Shark")
    # og:image uses content=, and seeds the image list / thumbnail.
    assert model.thumbnail_url == "https://public-files.gumroad.com/89u6yjpug60ndgc6ms9zf1z0fmut"
    assert model.source_site == "gumroad"
    assert model.external_id == "qb01jshark"


def test_og_reads_content_attribute_too():
    """Legacy `content=` OG markup must still parse (back-compat)."""
    html = (
        '<html><head>'
        '<meta property="og:title" content="Legacy Title">'
        '<meta property="og:description" content="Legacy description">'
        '<meta property="og:image" content="https://example.com/x.png">'
        '</head><body></body></html>'
    )
    model = gumroad._parse(html, "https://creator.gumroad.com/l/legacy1")

    assert model is not None
    assert model.title == "Legacy Title"
    assert model.description == "Legacy description"
    assert model.thumbnail_url == "https://example.com/x.png"


# ---------------------------------------------------------------------------
# Richer parsing from the Inertia data-page JSON (issue #326): creator name,
# the full cover image set and Gumroad's dedicated product thumbnail.
# ---------------------------------------------------------------------------

def _product_page(product: dict, *, og_image: str | None = None) -> str:
    data = {"component": "Products/Show", "props": {"product": product}}
    attr = htmllib.escape(json.dumps(data), quote=True)
    og = f'<meta property="og:image" content="{og_image}">' if og_image else ""
    return (
        f'<html><head><meta property="og:title" value="{product["name"]}">{og}</head>'
        f'<body><div id="app" data-page="{attr}"></div></body></html>'
    )


def test_parses_creator_and_covers_from_data_page():
    product = {
        "name": "QB01: J. Shark",
        "permalink": "exoqh",  # differs from the URL slug; we keep the slug as external_id
        "seller": {"name": "FRANCIS QUEZ"},
        "thumbnail_url": "https://files/thumb",
        "summary": "A dark Art Toy style model.",
        "covers": [
            {"type": "image", "url": "https://files/cover1"},
            {"type": "video", "url": "https://files/clip"},   # non-image, excluded
            {"type": "image", "url": "https://files/cover2"},
        ],
    }
    model = gumroad._parse(_product_page(product, og_image="https://files/cover1"), _URL)

    assert model is not None
    assert model.creator_name == "FRANCIS QUEZ"
    # Covers in order; the video is skipped; og image (== cover1) is de-duped.
    assert model.image_urls == ["https://files/cover1", "https://files/cover2"]
    # Dedicated product thumbnail wins over og image / first cover.
    assert model.thumbnail_url == "https://files/thumb"
    # URL slug, not the data-page permalink.
    assert model.external_id == "qb01jshark"


def test_data_page_summary_used_when_no_og_description():
    product = {"name": "No-OG Model", "seller": {"name": "Maker"}, "summary": "Short blurb."}
    model = gumroad._parse(_product_page(product), _URL)

    assert model is not None
    assert model.description == "Short blurb."
    assert model.creator_name == "Maker"
