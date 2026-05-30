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
async def _scrape_gumroad(url: str) -> list[StorefrontProduct]:
    """
    Scrape a Gumroad creator store.
    Works for both https://creator.gumroad.com and https://gumroad.com/creator
    """
    products: list[StorefrontProduct] = []

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
            final_url = str(r.url)
        except Exception as e:
            logger.error(f"Gumroad storefront failed: {e}")
            return []

    soup = BeautifulSoup(html, "html.parser")

    # Try JSON embedded in page (Gumroad often embeds product data as JSON)
    for script in soup.find_all("script", type="application/json"):
        try:
            data = json.loads(script.string or "")
            # Gumroad embeds products under various keys
            items = (
                data.get("products")
                or data.get("items")
                or (data.get("creator", {}) or {}).get("products", [])
            )
            if items and isinstance(items, list):
                for item in items:
                    name = item.get("name") or item.get("title")
                    permalink = item.get("permalink") or item.get("id")
                    if not name or not permalink:
                        continue
                    product_url = f"https://gumroad.com/l/{permalink}"
                    thumb = (
                        item.get("preview_url")
                        or item.get("thumbnail_url")
                        or item.get("cover_url")
                    )
                    products.append(StorefrontProduct(
                        title=name,
                        source_url=product_url,
                        source_site="gumroad",
                        external_id=permalink,
                        thumbnail_url=thumb,
                        description=item.get("description"),
                    ))
                if products:
                    return products
        except Exception:
            pass

    # Fallback: scrape HTML cards
    for card in soup.select("[data-permalink], .product-card, [class*='product']"):
        permalink = card.get("data-permalink")
        link = card.select_one("a[href*='/l/']")
        href = link.get("href") if link else None
        if not permalink and not href:
            continue
        product_url = (
            f"https://gumroad.com/l/{permalink}"
            if permalink
            else (href if href.startswith("http") else f"https://gumroad.com{href}")
        )
        title_el = card.select_one("h3, h2, .name, [class*='name']")
        img_el = card.select_one("img[src], img[data-src]")
        thumb = (img_el.get("src") or img_el.get("data-src")) if img_el else None
        ext_id = re.search(r"/l/([\w-]+)", product_url)
        products.append(StorefrontProduct(
            title=title_el.get_text(strip=True) if title_el else product_url,
            source_url=product_url,
            source_site="gumroad",
            external_id=ext_id.group(1) if ext_id else None,
            thumbnail_url=thumb,
        ))

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
    Cults paginates via ?page=N.
    """
    # Normalise to /creations sub-page
    base = url.rstrip("/")
    if "/creations" not in base:
        base = f"{base}/creations"

    products: list[StorefrontProduct] = []
    page = 1

    async with httpx.AsyncClient(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        while True:
            await asyncio.sleep(1)  # polite
            try:
                r = await client.get(base, params={"page": page})
                r.raise_for_status()
            except Exception as e:
                logger.error(f"Cults3D storefront page {page} failed: {e}")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("article.creation, [class*='creation-card'], [class*='crea']")
            if not cards:
                break

            for card in cards:
                link = card.select_one(
                    "a[href*='/3d-model/'], a[href*='/3d-printing-file/'], a[href*='/3d-modelling/']"
                )
                if not link:
                    continue
                href = link.get("href", "")
                product_url = href if href.startswith("http") else f"https://cults3d.com{href}"
                title_el = card.select_one("h3, h2, .title, [class*='name']")
                img_el = card.select_one("img[src], img[data-src]")
                thumb = (img_el.get("src") or img_el.get("data-src")) if img_el else None
                m = _CULTS_CREATION_RE.search(product_url)
                products.append(StorefrontProduct(
                    title=title_el.get_text(strip=True) if title_el else href,
                    source_url=product_url,
                    source_site="cults3d",
                    external_id=m.group(1) if m else None,
                    thumbnail_url=thumb,
                ))

            next_btn = soup.select_one("a[rel='next'], .pagination .next, [class*='next-page']")
            if not next_btn:
                break
            page += 1

    return products
