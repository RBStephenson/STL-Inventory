"""
MyMiniFactory scraper.

MMF now requires OAuth app registration for API access, so we scrape
product pages directly. Their pages have reliable Open Graph tags,
JSON-LD structured data, and a readable HTML structure.

If MMF ever offers a simple API key again, the api_key path can be
restored — config.mmf_api_key is still wired up but unused for now.
"""
import re
import json
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional

from app.services.scrapers.base import ScrapedModel, SearchResult

logger = logging.getLogger(__name__)

SITE = "myminifactory"
BASE = "https://www.myminifactory.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# https://www.myminifactory.com/object/3d-print-some-model-name-12345
_URL_RE = re.compile(r"myminifactory\.com/object/([\w-]+)", re.I)
_ID_FROM_SLUG_RE = re.compile(r"-(\d+)$")


def extract_id(url: str) -> Optional[str]:
    m = _URL_RE.search(url)
    if not m:
        return None
    slug = m.group(1)
    # ID is the trailing number in the slug
    id_m = _ID_FROM_SLUG_RE.search(slug)
    return id_m.group(1) if id_m else slug


async def fetch(url: str) -> Optional[ScrapedModel]:
    async with httpx.AsyncClient(
        timeout=20,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
            final_url = str(r.url)
        except Exception as e:
            logger.error(f"MMF fetch({url}) failed: {e}")
            return None

    return _parse(html, final_url)


async def search(query: str, limit: int = 12) -> list[SearchResult]:
    async with httpx.AsyncClient(
        timeout=20,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            r = await client.get(
                f"{BASE}/search",
                params={"q": query, "type": "objects"},
            )
            r.raise_for_status()
            html = r.text
        except Exception as e:
            logger.error(f"MMF search({query!r}) failed: {e}")
            return []

    soup = BeautifulSoup(html, "html.parser")
    results = []

    # MMF search results — card selectors may need tuning as their HTML evolves
    for card in soup.select(".object-card, [class*='object-card'], article[data-id]")[:limit]:
        link = card.select_one("a[href*='/object/']")
        if not link:
            continue
        href = link.get("href", "")
        product_url = href if href.startswith("http") else f"{BASE}{href}"
        title_el = card.select_one("h3, h2, .object-name, [class*='name']")
        img_el = card.select_one("img[src], img[data-src]")
        thumb = (img_el.get("src") or img_el.get("data-src")) if img_el else None
        creator_el = card.select_one("[class*='designer'], [class*='creator'], [class*='author']")
        like_el = card.select_one("[class*='like'], [class*='heart']")
        like_count = None
        if like_el:
            m = re.search(r"\d+", like_el.get_text())
            if m:
                like_count = int(m.group())
        results.append(SearchResult(
            title=title_el.get_text(strip=True) if title_el else product_url,
            source_url=product_url,
            source_site=SITE,
            external_id=extract_id(product_url),
            creator_name=creator_el.get_text(strip=True) if creator_el else None,
            thumbnail_url=thumb,
            like_count=like_count,
        ))
    return results


def _parse(html: str, url: str) -> Optional[ScrapedModel]:
    soup = BeautifulSoup(html, "html.parser")

    def og(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=f"og:{prop}")
        return tag["content"].strip() if tag and tag.get("content") else None

    def meta_name(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"].strip() if tag and tag.get("content") else None

    title = og("title") or meta_name("title") or _text(soup, ["h1"])
    description = og("description") or meta_name("description")
    thumbnail_url = og("image")

    images: list[str] = []
    tags: list[str] = []
    creator_name: Optional[str] = None
    creator_url: Optional[str] = None
    license_str: Optional[str] = None
    like_count: Optional[int] = None
    download_count: Optional[int] = None
    make_count: Optional[int] = None
    category: Optional[str] = None

    # JSON-LD (MMF includes structured data)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            if isinstance(ld, list):
                ld = ld[0]
            t = ld.get("@type", "")
            if t in ("Product", "CreativeWork", "3DModel", "Thing"):
                title = title or ld.get("name")
                description = description or ld.get("description")
                author = ld.get("author") or ld.get("creator") or {}
                if isinstance(author, dict):
                    creator_name = creator_name or author.get("name")
                    creator_url = creator_url or author.get("url")
                for img in ld.get("image", []):
                    src = img if isinstance(img, str) else img.get("url", "")
                    if src and src not in images:
                        images.append(src)
                license_str = license_str or ld.get("license")
        except Exception:
            pass

    # Creator from page HTML
    if not creator_name:
        creator_name = _text(soup, [
            ".designer-name",
            "[class*='designer'] a",
            "[class*='creator'] a",
            "[itemprop='author'] [itemprop='name']",
        ])

    # Tags
    for tag_el in soup.select("[class*='tag'] a, .tags a, [rel='tag']"):
        t = tag_el.get_text(strip=True)
        if t and t not in tags:
            tags.append(t)

    # Category
    breadcrumb = soup.select(".breadcrumb a, [class*='breadcrumb'] a")
    if len(breadcrumb) > 1:
        category = breadcrumb[-1].get_text(strip=True)

    # Stats
    for stat in soup.select("[class*='stat'], [class*='count'], [class*='like'], [class*='download']"):
        text = stat.get_text(strip=True).lower()
        n_m = re.search(r"[\d,]+", text)
        if not n_m:
            continue
        n = int(n_m.group().replace(",", ""))
        if "like" in text or "heart" in text or "love" in text:
            like_count = n
        elif "download" in text:
            download_count = n
        elif "make" in text or "print" in text:
            make_count = n

    # Gallery images
    for img in soup.select(".gallery img, [class*='gallery'] img, [class*='picture'] img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy")
        if src and src.startswith("http") and src not in images:
            images.append(src)

    if thumbnail_url and thumbnail_url not in images:
        images.insert(0, thumbnail_url)
    images = [i for i in images if i and i.startswith("http")]

    if not title:
        return None

    return ScrapedModel(
        title=title,
        description=description,
        source_url=url,
        source_site=SITE,
        external_id=extract_id(url),
        creator_name=creator_name,
        creator_url=creator_url,
        thumbnail_url=images[0] if images else thumbnail_url,
        image_urls=images,
        tags=tags,
        category=category,
        license=license_str,
        like_count=like_count,
        download_count=download_count,
        make_count=make_count,
    )


def _text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True) or None
    return None
