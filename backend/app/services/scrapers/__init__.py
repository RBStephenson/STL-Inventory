"""
Scraper dispatcher — routes URLs and search queries to the right site adapter.
"""
from typing import Optional
from app.services.scrapers.base import ScrapedModel, SearchResult
from app.services.scrapers import mmf, gumroad, cults3d

SITE_PATTERNS = [
    ("myminifactory", mmf),
    ("gumroad",       gumroad),
    ("cults3d",       cults3d),
]


def detect_site(url: str) -> Optional[str]:
    url_lower = url.lower()
    if "myminifactory.com" in url_lower:
        return "myminifactory"
    if "gumroad.com" in url_lower:
        return "gumroad"
    if "cults3d.com" in url_lower:
        return "cults3d"
    return None


async def fetch_url(url: str) -> Optional[ScrapedModel]:
    """Detect site from URL and fetch metadata."""
    site = detect_site(url)
    if site == "myminifactory":
        return await mmf.fetch(url)
    if site == "gumroad":
        return await gumroad.fetch(url)
    if site == "cults3d":
        return await cults3d.fetch(url)
    return None


async def search_site(site: str, query: str, limit: int = 12) -> list[SearchResult]:
    """Search a specific site by name."""
    if site == "myminifactory":
        return await mmf.search(query, limit)
    if site == "gumroad":
        return await gumroad.search(query, limit)
    if site == "cults3d":
        return await cults3d.search(query, limit)
    return []
