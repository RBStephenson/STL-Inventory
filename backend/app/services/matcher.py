"""
Fuzzy name matching between scraped storefront products and local models.

We use a token-based similarity score rather than edit distance because
model names tend to vary in word order and include extra tokens like
scale, version, creator name, etc.

e.g.  local:    "1-6scale Akuma CA3D"
      scraped:  "Akuma Street Fighter 1/6 Scale Figure"
      → high overlap on "akuma" + "1" + "6" + "scale"
"""
import re
from dataclasses import dataclass
from typing import Optional

from app.services.scrapers.storefront import StorefrontProduct


@dataclass
class MatchCandidate:
    local_model_id: int
    local_name: str
    local_folder: str
    product: StorefrontProduct
    score: float          # 0–1
    confidence: str       # "high" | "medium" | "low"


_STRIP_RE = re.compile(r"[^\w\s]")
_SCALE_RE = re.compile(r"\b1[-/:]?(\d{1,2})\b")


def _tokens(text: str) -> set[str]:
    text = _STRIP_RE.sub(" ", text.lower())
    # Normalise scale expressions so "1-6" and "1/6" both become "1 6"
    text = _SCALE_RE.sub(lambda m: f"1 {m.group(1)}", text)
    return {t for t in text.split() if len(t) > 1}


def _score(local_name: str, product_title: str) -> float:
    a = _tokens(local_name)
    b = _tokens(product_title)
    if not a or not b:
        return 0.0
    intersection = a & b
    # Jaccard similarity weighted toward recall (local tokens matched)
    jaccard = len(intersection) / len(a | b)
    recall  = len(intersection) / len(a)
    return round(0.4 * jaccard + 0.6 * recall, 3)


def _confidence(score: float) -> str:
    if score >= 0.55:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def match_products_to_models(
    products: list[StorefrontProduct],
    models: list[dict],           # [{"id": int, "name": str, "folder_path": str, ...}]
    min_score: float = 0.20,
) -> list[MatchCandidate]:
    """
    For each local model, find the best-matching storefront product.
    Returns one candidate per local model (best match only), filtered
    by min_score. Sorted by score descending.
    """
    candidates: list[MatchCandidate] = []

    for m in models:
        best_score = 0.0
        best_product: Optional[StorefrontProduct] = None

        # Also score against folder name as fallback
        names_to_try = [m.get("name", ""), m.get("title") or ""]

        for product in products:
            for name in names_to_try:
                if not name:
                    continue
                s = _score(name, product.title)
                if s > best_score:
                    best_score = s
                    best_product = product

        if best_product and best_score >= min_score:
            candidates.append(MatchCandidate(
                local_model_id=m["id"],
                local_name=m.get("title") or m.get("name", ""),
                local_folder=m.get("folder_path", ""),
                product=best_product,
                score=best_score,
                confidence=_confidence(best_score),
            ))

    return sorted(candidates, key=lambda c: -c.score)
