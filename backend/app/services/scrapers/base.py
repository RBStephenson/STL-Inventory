"""
Shared result type and base class for all site scrapers.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScrapedModel:
    """Normalised metadata returned by any scraper."""
    # Core
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    source_site: Optional[str] = None
    external_id: Optional[str] = None

    # Creator
    creator_name: Optional[str] = None
    creator_url: Optional[str] = None

    # Media
    thumbnail_url: Optional[str] = None
    image_urls: list[str] = field(default_factory=list)

    # Taxonomy
    tags: list[str] = field(default_factory=list)
    category: Optional[str] = None
    license: Optional[str] = None

    # Stats
    like_count: Optional[int] = None
    download_count: Optional[int] = None
    make_count: Optional[int] = None


@dataclass
class SearchResult:
    """One item in a search results list."""
    title: str
    source_url: str
    source_site: str
    external_id: Optional[str] = None
    creator_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    like_count: Optional[int] = None
