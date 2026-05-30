"""
Cults3D scraper — no public API, parse product page HTML.

Cults3D is more aggressive about blocking scrapers. We:
  - Use a realistic User-Agent
  - Add a short delay between requests
  - Pull from Open Graph + JSON-LD + page HTML
"""
import re
import json
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import Optional

from app.services.scrapers.base import ScrapedModel, SearchResult

logger = logging.getLogger(__name__)

SITE = "cults3d"
BASE = "https://cults3d.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://cults3d.com/",
}

# https://cults3d.com/en/3d-model/various/my-model-slug
# https://cults3d.com/en/3d-printing-file/my-model-slug
_URL_RE = re.compile(
    r"cults3d\.com/\w+/3d-(?:model|printing-file|modelling)/(.+?)(?:/|$)",
    re.I,
)


def extract_id(url: str) -> Optional[str]:
    m = _URL_RE.search(url)
    return m.group(1) if m else None


async def fetch(url: str) -> Optional[ScrapedModel]:
    await asyncio.sleep(1)  # be polite
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
            logger.error(f"Cults3D fetch({url}) failed: {e}")
            return None

    return _parse(html, final_url)


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
    like_count: Optional[int] = None
    download_count: Optional[int] = None

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            if isinstance(ld, list):
                ld = ld[0]
            t = ld.get("@type", "")
            if t in ("Product", "CreativeWork", "3DModel"):
                title = title or ld.get("name")
                description = description or ld.get("description")
                author = ld.get("author") or ld.get("creator") or {}
                creator_name = creator_name or (
                    author.get("name") if isinstance(author, dict) else None
                )
                for img in ld.get("image", []):
                    if isinstance(img, str) and img not in images:
                        images.append(img)
        except Exception:
            pass

    # Creator from page
    if not creator_name:
        creator_name = _text(soup, [
            ".creator-pseudo",
            ".user-name",
            '[class*="creator"] a',
            '[itemprop="author"] [itemprop="name"]',
        ])

    # Tags
    for tag_el in soup.select('[class*="tag"], [rel="tag"]'):
        t = tag_el.get_text(strip=True)
        if t and t not in tags:
            tags.append(t)

    # Stats (likes, downloads shown on page)
    for stat in soup.select('[class*="stat"], [class*="count"]'):
        text = stat.get_text(strip=True).lower()
        num_match = re.search(r"[\d,]+", text)
        if not num_match:
            continue
        n = int(num_match.group().replace(",", ""))
        if "like" in text or "love" in text:
            like_count = n
        elif "download" in text:
            download_count = n

    if thumbnail_url and thumbnail_url not in images:
        images.insert(0, thumbnail_url)
    # Also grab gallery images
    for img in soup.select('.creation-cover img, .gallery img, [class*="picture"] img'):
        src = img.get("src") or img.get("data-src")
        if src and src not in images:
            images.append(src)

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
        thumbnail_url=images[0] if images else None,
        image_urls=images,
        tags=tags,
        like_count=like_count,
        download_count=download_count,
    )


async def search(query: str, limit: int = 12) -> list[SearchResult]:
    await asyncio.sleep(1)
    async with httpx.AsyncClient(
        timeout=20,
        headers=_HEADERS,
        follow_redirects=True,
    ) as client:
        try:
            r = await client.get(
                f"{BASE}/en/3d-models/search",
                params={"q": query},
            )
            r.raise_for_status()
            html = r.text
        except Exception as e:
            logger.error(f"Cults3D search({query!r}) failed: {e}")
            return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for card in soup.select("article.creation, [class*='creation-card']")[:limit]:
        link = card.select_one("a[href*='/3d-model/'], a[href*='/3d-printing-file/']")
        if not link:
            continue
        href = link.get("href", "")
        product_url = href if href.startswith("http") else f"{BASE}{href}"
        title_el = card.select_one("h3, h2, .title, [class*='name']")
        img_el = card.select_one("img[src], img[data-src]")
        thumb = (img_el.get("src") or img_el.get("data-src")) if img_el else None
        creator_el = card.select_one("[class*='creator'], [class*='user']")
        results.append(SearchResult(
            title=title_el.get_text(strip=True) if title_el else product_url,
            source_url=product_url,
            source_site=SITE,
            external_id=extract_id(product_url),
            creator_name=creator_el.get_text(strip=True) if creator_el else None,
            thumbnail_url=thumb,
        ))
    return results


def _text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True) or None
    return None
