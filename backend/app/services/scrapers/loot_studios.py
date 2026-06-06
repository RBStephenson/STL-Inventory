"""
Loot Studios scraper — individual bundle pages at
https://app.lootstudios.com/bundle/{slug}/

The Loot Studios bundle store listing is JS-rendered and cannot be crawled
without authentication.  This module supports fetching a single bundle page
by URL, which is fully server-rendered and publicly accessible.
"""
import re
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional

from app.services.scrapers.base import ScrapedModel, SearchResult

logger = logging.getLogger(__name__)

SITE = "loot-studios"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Matches both app.lootstudios.com/bundle/slug and lootstudios.com/bundle/slug
_URL_RE = re.compile(r"lootstudios\.com/bundle/([\w-]+)", re.I)


def extract_id(url: str) -> Optional[str]:
    m = _URL_RE.search(url)
    return m.group(1) if m else None


def _parse(html: str, url: str) -> Optional[ScrapedModel]:
    soup = BeautifulSoup(html, "html.parser")

    # Title from <h1>
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else None
    if not title:
        return None

    # Thumbnail: first <img> with a wp-content/uploads URL (hosted cover art)
    thumbnail_url: Optional[str] = None
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if "wp-content/uploads" in src:
            thumbnail_url = src
            break

    # Gallery images from the Loot Studios CDN
    image_urls: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if "assets.loot-studios.com" in src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    if not thumbnail_url and image_urls:
        thumbnail_url = image_urls[0]

    # Tags from common tag/category link patterns
    tags: list[str] = []
    for el in soup.select("a.tag, span.tag, .tags a, .tag-list a, [class*='tag'] a"):
        text = el.get_text(strip=True)
        if text and text not in tags:
            tags.append(text)

    return ScrapedModel(
        title=title,
        source_url=url,
        source_site=SITE,
        external_id=extract_id(url),
        creator_name="Loot Studios",
        thumbnail_url=thumbnail_url,
        image_urls=image_urls,
        tags=tags,
    )


async def fetch(url: str) -> Optional[ScrapedModel]:
    """Fetch a single Loot Studios bundle page."""
    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Loot Studios fetch({url}) failed: {e}")
            return None
    return _parse(r.text, str(r.url))


async def search(query: str, limit: int = 12) -> list[SearchResult]:
    """Loot Studios has no public search API; URL-paste is the primary path."""
    return []
