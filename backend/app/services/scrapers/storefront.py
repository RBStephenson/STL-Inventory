"""
Storefront scrapers — given a creator's profile/store URL, return
a list of all their products with thumbnail + metadata.

Supported:
  MyMiniFactory  https://www.myminifactory.com/users/{username}
  Gumroad        https://{creator}.gumroad.com  or  gumroad.com/{creator}
  Cults3D        https://cults3d.com/en/users/{username}/creations
"""
import re
import json
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class StorefrontProduct:
    title: str
    source_url: str
    source_site: str
    external_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)


def detect_site(url: str) -> Optional[str]:
    u = url.lower()
    if "myminifactory.com" in u:
        return "myminifactory"
    if "gumroad.com" in u:
        return "gumroad"
    if "cults3d.com" in u:
        return "cults3d"
    return None


async def scrape_storefront(url: str) -> list[StorefrontProduct]:
    site = detect_site(url)
    if site == "myminifactory":
        return await _scrape_mmf(url)
    if site == "gumroad":
        return await _scrape_gumroad(url)
    if site == "cults3d":
        return await _scrape_cults(url)
    return []


# ---------------------------------------------------------------------------
# MyMiniFactory
# ---------------------------------------------------------------------------
_MMF_OBJECT_RE = re.compile(r"myminifactory\.com/object/([\w-]+)", re.I)
_MMF_ID_RE = re.compile(r"-(\d+)$")

async def _scrape_mmf(url: str) -> list[StorefrontProduct]:
    """
    Scrape a MMF user profile page.
    MMF paginates via ?page=N — we keep going until a page returns no products.
    """
    # Normalise to profile URL
    # e.g. https://www.myminifactory.com/users/CA3DStudios
    products: list[StorefrontProduct] = []
    page = 1

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        while True:
            try:
                r = await client.get(url, params={"page": page})
                r.raise_for_status()
            except Exception as e:
                logger.error(f"MMF storefront page {page} failed: {e}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(
                ".object-card, [class*='object-card'], "
                "article[data-id], [class*='grid-item']"
            )
            if not cards:
                break

            for card in cards:
                link = card.select_one("a[href*='/object/']")
                if not link:
                    continue
                href = link.get("href", "")
                product_url = href if href.startswith("http") else f"https://www.myminifactory.com{href}"
                title_el = card.select_one("h3, h2, .object-name, [class*='name']")
                img_el = card.select_one("img[src], img[data-src]")
                thumb = (img_el.get("src") or img_el.get("data-src")) if img_el else None
                slug_m = _MMF_OBJECT_RE.search(product_url)
                ext_id = None
                if slug_m:
                    id_m = _MMF_ID_RE.search(slug_m.group(1))
                    ext_id = id_m.group(1) if id_m else slug_m.group(1)

                products.append(StorefrontProduct(
                    title=title_el.get_text(strip=True) if title_el else href,
                    source_url=product_url,
                    source_site="myminifactory",
                    external_id=ext_id,
                    thumbnail_url=thumb,
                ))

            # Check for next page
            next_btn = soup.select_one("a[rel='next'], .pagination .next a, [class*='next']")
            if not next_btn:
                break
            page += 1
            await asyncio.sleep(0.5)

    return products


# ---------------------------------------------------------------------------
# Gumroad
# ---------------------------------------------------------------------------

# Gumroad is a client-side React app — no product HTML in the initial page.
# However, GET /creator with Accept: application/json returns a list of
# permalink slugs. We then fetch each product page concurrently to extract
# title + og:image from server-rendered meta tags.
_GUMROAD_MAX_PRODUCTS = 200  # cap to keep response time reasonable

async def _scrape_gumroad(url: str) -> list[StorefrontProduct]:
    """
    Scrape a Gumroad creator store.
    Works for https://creator.gumroad.com or https://gumroad.com/creator.
    """
    # Normalise: we always want the subdomain form for the JSON API
    base_url = url.rstrip("/")

    json_headers = {**_HEADERS, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20, headers=json_headers, follow_redirects=True) as client:
        try:
            r = await client.get(base_url)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Gumroad profile fetch failed: {e}")
            return []

    slugs: list[str] = data.get("links", [])
    if not slugs:
        logger.warning("Gumroad: no permalink slugs found in profile response")
        return []

    # Derive the store base so product URLs stay on the creator's subdomain
    # (some creators have custom domains — use the final URL from the profile)
    slugs = slugs[:_GUMROAD_MAX_PRODUCTS]
    logger.info(f"Gumroad: fetching {len(slugs)} product pages (of {len(data.get('links', []))} total)")

    semaphore = asyncio.Semaphore(20)

    async def fetch_product(client: httpx.AsyncClient, slug: str) -> StorefrontProduct | None:
        product_url = f"{base_url}/l/{slug}"
        async with semaphore:
            try:
                r = await client.get(product_url)
                r.raise_for_status()
            except Exception:
                return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Title: prefer og:title, fall back to <title> (strips "| Gumroad" suffix)
        og_title = soup.find("meta", property="og:title")
        title = (og_title.get("content") if og_title else None) or ""
        if not title:
            t = soup.find("title")
            title = t.get_text(strip=True) if t else ""
        # Strip common Gumroad suffixes
        for suffix in [" | Gumroad", " - Gumroad", " by "]:
            if suffix in title:
                title = title.split(suffix)[0].strip()
        if not title:
            return None

        # Thumbnail from og:image
        og_image = soup.find("meta", property="og:image")
        thumb = og_image.get("content") if og_image else None

        return StorefrontProduct(
            title=title,
            source_url=product_url,
            source_site="gumroad",
            external_id=slug,
            thumbnail_url=thumb,
        )

    async with httpx.AsyncClient(timeout=15, headers=_HEADERS, follow_redirects=True) as client:
        tasks = [fetch_product(client, slug) for slug in slugs]
        results = await asyncio.gather(*tasks)

    products = [p for p in results if p is not None]
    logger.info(f"Gumroad: scraped {len(products)} products successfully")
    return products


# ---------------------------------------------------------------------------
# Cults3D
# ---------------------------------------------------------------------------
_CULTS_CREATION_RE = re.compile(
    r"cults3d\.com/\w+/3d-(?:model|printing-file|modelling)/([\w/-]+)", re.I
)

async def _scrape_cults(url: str) -> list[StorefrontProduct]:
    """
    Scrape a Cults3D user creations page.
    Accepts any Cults3D profile URL — /3d-models, /creations, or bare profile.
    Paginates via ?page=N.
    """
    # Strip any stale /creations suffix; the modern URL pattern is /3d-models
    base = url.rstrip("/")
    if base.endswith("/creations"):
        base = base[: -len("/creations")]

    products: list[StorefrontProduct] = []
    page = 1

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        while True:
            await asyncio.sleep(0.5)  # polite
            try:
                r = await client.get(base, params={"page": page})
                r.raise_for_status()
            except Exception as e:
                logger.error(f"Cults3D storefront page {page} failed: {e}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("article.crea")
            if not cards:
                break

            for card in cards:
                # Link + title: the anchor has both href and title attribute
                link = card.select_one(
                    "a[href*='/3d-model/'], a[href*='/3d-printing-file/'], a[href*='/3d-modelling/']"
                )
                if not link:
                    continue
                href = link.get("href", "")
                product_url = href if href.startswith("http") else f"https://cults3d.com{href}"

                # Title: try the drawer-title strong, then the link's title attribute
                title_el = card.select_one("strong.drawer-title, .tbox-title, h3, h2")
                title = (
                    title_el.get_text(strip=True)
                    if title_el
                    else link.get("title") or href
                )

                # Thumbnail: lazy-loaded images use data-src
                img_el = card.select_one("img[data-src], img[src]")
                thumb = (img_el.get("data-src") or img_el.get("src")) if img_el else None

                m = _CULTS_CREATION_RE.search(product_url)
                products.append(StorefrontProduct(
                    title=title,
                    source_url=product_url,
                    source_site="cults3d",
                    external_id=m.group(1) if m else None,
                    thumbnail_url=thumb,
                ))

            # Next page: span.paginate.next > a
            next_btn = soup.select_one("span.paginate.next a, a[rel='next']")
            if not next_btn:
                break
            page += 1

    return products
