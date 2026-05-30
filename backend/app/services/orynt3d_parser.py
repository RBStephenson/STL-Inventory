"""
Parse config.orynt3d files (version 6 format).

Thumbnail resolution:
  modelmeta.cover is a GUID filename e.g. "42744c2d-dbf5-45dc-904b-541552319364.jpg"
  Orynt3D stores thumbnails in its own cache at:
    <orynt3d_package>/LocalCache/Roaming/orynt3d/User Storage/Cache/orynt3dThumbnails/
  Multiple sizes exist per GUID: <guid>.jpg, <guid>_128.jpg, <guid>_512.jpg, <guid>_1024.jpg
  We mount that cache directory into the container and resolve GUIDs from there.

Two distinct uses:
  1. Creator-level config  — lives at <root>/<creator>/config.orynt3d
     Carries scancfg.attributes.include with propagated attributes like
     {"key": "creator", "value": "..."} and {"key": "store front", "value": "..."}

  2. Model-level config — lives inside a model folder (any depth)
     Carries modelmeta.tags, modelmeta.attributes, modelmeta.name, modelmeta.cover

The scanner calls parse_creator_config() on creator directories and
parse_model_config() on model directories.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ORYNT3D_FILENAME = "config.orynt3d"

STORE_FRONT_SITES = {
    "gumroad": "gumroad",
    "thingiverse": "thingiverse",
    "printables": "printables",
    "prusa": "printables",
    "myminifactory": "myminifactory",
    "mmf": "myminifactory",
    "cults3d": "cults3d",
    "cults": "cults3d",
    "thangs": "thangs",
    "makerworld": "makerworld",
    "patreon": "patreon",
    "cgtrader": "cgtrader",
    "turbosquid": "turbosquid",
}


def _load(folder_path: str) -> Optional[dict]:
    p = Path(folder_path) / ORYNT3D_FILENAME
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to parse {p}: {e}")
        return None


def _attrs_to_dict(attr_list: list) -> dict[str, str]:
    """Convert [{"key": "x", "value": "y"}, ...] → {"x": "y"}."""
    return {a["key"].lower(): a["value"] for a in attr_list if "key" in a and "value" in a}


def parse_creator_config(folder_path: str) -> Optional[dict]:
    """
    Extract propagated attributes from a creator-level config.orynt3d.
    Returns a dict with normalised creator metadata, or None if no config found.
    """
    raw = _load(folder_path)
    if not raw:
        return None

    scancfg = raw.get("scancfg", {})
    include_attrs = _attrs_to_dict(scancfg.get("attributes", {}).get("include", []))

    creator_name = include_attrs.get("creator")
    store_front = include_attrs.get("store front") or include_attrs.get("storefront")
    source_site = _normalise_site(store_front)

    # Also check modelmeta in case a creator folder has name set
    modelmeta = raw.get("modelmeta", {})
    meta_name = modelmeta.get("name")

    return {
        "creator_name": creator_name or meta_name,
        "store_front": store_front,
        "source_site": source_site,
        "raw_attributes": include_attrs,
    }


def parse_model_config(folder_path: str) -> Optional[dict]:
    """
    Extract model metadata from a model-level config.orynt3d.
    Returns normalised dict or None if no config found.
    """
    raw = _load(folder_path)
    if not raw:
        return None

    modelmeta = raw.get("modelmeta", {})
    meta_attrs = _attrs_to_dict(modelmeta.get("attributes", []))

    # scancfg may carry additional propagated attributes at model level
    scancfg = raw.get("scancfg", {})
    scan_attrs = _attrs_to_dict(scancfg.get("attributes", {}).get("include", []))

    # Merge: model-level attrs take precedence
    all_attrs = {**scan_attrs, **meta_attrs}

    tags = modelmeta.get("tags") or []
    cover_guid = modelmeta.get("cover")  # GUID filename e.g. "abc123.jpg" or None
    cover_path = resolve_cover_guid(cover_guid) if cover_guid else None

    return {
        "name": modelmeta.get("name"),
        "notes": modelmeta.get("notes") or "",
        "tags": tags,
        "cover_guid": cover_guid,
        "cover_path": cover_path,  # resolved absolute path or None
        "collections": modelmeta.get("collections") or [],
        "attributes": all_attrs,
        # Well-known attribute keys
        "gender": all_attrs.get("gender"),
        "scale": all_attrs.get("scale"),
        "source_url": all_attrs.get("url") or all_attrs.get("source url") or all_attrs.get("source_url"),
        "store_front": all_attrs.get("store front") or all_attrs.get("storefront"),
        "source_site": _normalise_site(
            all_attrs.get("store front") or all_attrs.get("storefront")
        ),
        "is_leaf": scancfg.get("modelMode") == 2,  # modelMode 2 = leaf model node
    }


def resolve_cover_guid(guid_filename: str) -> Optional[str]:
    """
    Resolve an Orynt3D GUID thumbnail filename to an absolute path.
    Prefers _1024 > _512 > base size for best quality.
    Returns None if the cache directory is not configured or the file is missing.
    """
    from app.config import settings
    cache_dir = settings.orynt3d_thumbnail_cache
    if not cache_dir:
        return None

    stem = Path(guid_filename).stem  # strip .jpg
    cache = Path(cache_dir)

    for suffix in (f"{stem}_1024.jpg", f"{stem}_512.jpg", f"{stem}.jpg"):
        candidate = cache / suffix
        if candidate.exists():
            return str(candidate)

    return None


def _normalise_site(store_front: Optional[str]) -> Optional[str]:
    if not store_front:
        return None
    key = store_front.lower().strip()
    for fragment, site in STORE_FRONT_SITES.items():
        if fragment in key:
            return site
    return "other"
