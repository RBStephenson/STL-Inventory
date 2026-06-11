"""Static-HTML export: serialize a structured guide back to the legacy
self-contained HTML file format (spec §9.5, §9.6).

This is half of the golden-fixture round-trip (#261): import a hand-built
guide -> export it here -> diff against the original. Because the real
``painting-guides/by-category/**/*.html`` corpus isn't in this repo, the DOM
emitted here is the *canonical* legacy shape, reconstructed from the spec's
class-name contract (§9.1) and importer mapping table (§9.6). The importer is
written to match this output; divergences in the round-trip point precisely at
the gap (spec §9.6 "round-trip golden test").

Driven by the same data the React reader (#259) consumes, so the two stay in
lockstep. HTML is an output, never the source of truth (spec §9.1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from sqlalchemy.orm import Session

from app.painting.models import (
    Guide, GuideCategory, GuideSeries, Paint, PaintBrand, PaintLine,
)

# Shared assets the legacy single-file guides link to (spec §9.5: "linking the
# shared assets"). Relative so an exported file sits next to its siblings in the
# by-category/ archive.
GUIDE_CSS_HREF = "../../assets/guide.css"
SKILLS_JS_SRC = "../../assets/skills-reference.js"

# Callout prefixes the importer strips back off (spec §9.6).
TIP_PREFIX = "✦ TIP: "       # ✦ TIP:
WARNING_PREFIX = "⚠ NOTE: "  # ⚠ NOTE:


def _t(value) -> str:
    """Escape a text node — only & < > (quote=False), so literal apostrophes
    and quotes survive verbatim as the hand-built legacy files keep them.
    Attribute values still use escape(..., quote=True)."""
    return escape(str(value), quote=False)


@dataclass
class PaintInfo:
    """The denormalized paint facts a swatch needs to render."""
    name: str
    code: str
    brand: str
    line: str
    hex: str | None


def _paint_lookup(db: Session, guide: Guide) -> dict[int, PaintInfo]:
    """Resolve every paint referenced by a swatch/mix into render facts."""
    ids: set[int] = set()
    for tab in guide.tabs:
        for phase in tab.phases:
            for step in phase.steps:
                ids.update(s.paint_id for s in step.swatches)
                ids.update(m.paint_id for m in step.mix_components)
    if not ids:
        return {}
    rows = (
        db.query(Paint, PaintLine, PaintBrand)
        .join(PaintLine, Paint.paint_line_id == PaintLine.id)
        .join(PaintBrand, PaintLine.brand_id == PaintBrand.id)
        .filter(Paint.id.in_(ids))
        .all()
    )
    return {
        paint.id: PaintInfo(
            name=paint.name, code=paint.code, brand=brand.name,
            line=line.name, hex=paint.hex,
        )
        for paint, line, brand in rows
    }


def _slugify(text: str) -> str:
    """A stable DOM id for a tab name ('Skin Tones' -> 'skin-tones')."""
    out = "".join(c.lower() if c.isalnum() else "-" for c in text)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "tab"


def _theme_style(theme: dict | None) -> str:
    """Per-guide :root vars as inline custom properties on the page root
    (spec §9.2 — the theme block becomes inline CSS variables)."""
    if not theme:
        return ""
    var_map = {
        "bg": "--bg", "surface": "--surface", "surface2": "--surface-2",
        "surface3": "--surface-3", "border": "--border", "text": "--text",
        "text_muted": "--text-muted", "text_dim": "--text-dim",
        "accent": "--accent",
    }
    parts = [
        f"{css}: {escape(str(theme[key]), quote=True)}"
        for key, css in var_map.items()
        if theme.get(key)
    ]
    return ";".join(parts)


class _Buf:
    """Tiny ordered HTML buffer — keeps the renderer deterministic."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def add(self, html: str) -> None:
        self._parts.append(html)

    def __str__(self) -> str:
        return "".join(self._parts)


def _swatch_value(value_pct: int | None, role_label: str | None) -> str:
    """'~NN% value — role', either part optional (spec §9.6)."""
    bits: list[str] = []
    if value_pct is not None:
        bits.append(f"~{value_pct}% value")
    if role_label:
        bits.append(role_label)
    return " — ".join(bits)


def _render_swatch(buf: _Buf, swatch, paints: dict[int, PaintInfo]) -> None:
    info = paints.get(swatch.paint_id)
    if info is None:  # defensive: CRUD validates paint ids, so this is rare
        return
    buf.add('<div class="swatch">')
    dot_style = f"background:{escape(info.hex, quote=True)}" if info.hex else ""
    buf.add(f'<span class="swatch-dot" style="{dot_style}"></span>')
    name = f"{info.name} {info.code}".strip()
    buf.add(f'<span class="swatch-name">{_t(name)}</span>')
    buf.add(f'<span class="swatch-brand">{_t(info.brand)}</span>')
    value = _swatch_value(swatch.value_pct, swatch.role_label)
    if value:
        buf.add(f'<span class="swatch-value">{_t(value)}</span>')
    buf.add("</div>")


def _render_step(buf: _Buf, step, number: int, paints: dict[int, PaintInfo]) -> None:
    buf.add('<div class="step">')
    tag = step.technique_tag or ""
    tag_class = f"step-number {tag}".strip()
    buf.add(f'<div class="{escape(tag_class, quote=True)}">{number}</div>')
    buf.add(f'<h3 class="step-title">{_t(step.title)}</h3>')

    for swatch in step.swatches:
        _render_swatch(buf, swatch, paints)

    if step.ratio_box:
        buf.add(f'<div class="ratio-box">{_t(step.ratio_box)}</div>')
    if step.body:
        buf.add(f'<p class="step-body">{_t(step.body)}</p>')
    if step.value_intent:
        buf.add(f'<p class="value-intent">{_t(step.value_intent)}</p>')
    if step.tip:
        buf.add(f'<div class="tip">{_t(TIP_PREFIX + step.tip)}</div>')
    if step.warning:
        buf.add(f'<div class="warning">{_t(WARNING_PREFIX + step.warning)}</div>')
    buf.add("</div>")


def _render_value_map(buf: _Buf, value_map: dict | None) -> None:
    chips = (value_map or {}).get("chips") or []
    if not chips:
        return
    buf.add('<div class="value-map">')
    for chip in chips:
        buf.add('<div class="value-chip">')
        bg = escape(str(chip.get("hex", "")), quote=True)
        buf.add(f'<span class="chip-swatch" style="background:{bg}"></span>')
        buf.add(f'<span class="chip-val">{_t(str(chip.get("value_pct", "")))}%</span>')
        buf.add(f'<span class="chip-label">{_t(str(chip.get("zone_label", "")))}</span>')
        buf.add("</div>")
    buf.add("</div>")


def _render_method_cards(buf: _Buf, skin_config: dict | None) -> None:
    """Skin tab method cards (spec §9.6 .method-card / .recommended).

    Method `steps` are opaque display dicts (kept verbatim for lossless
    round-trip, see schemas note); rendered title-only here. The full method
    body lands with the importer's golden fixtures (#261)."""
    methods = (skin_config or {}).get("methods") or []
    if not methods:
        return
    for method in methods:
        klass = "method-card recommended" if method.get("recommended") else "method-card"
        buf.add(f'<div class="{klass}">')
        buf.add(f'<h4 class="method-title">{_t(str(method.get("title", "")))}</h4>')
        buf.add("</div>")


def _render_tab_body(buf: _Buf, tab, paints: dict[int, PaintInfo]) -> None:
    _render_value_map(buf, tab.value_map)
    _render_method_cards(buf, tab.skin_config)
    number = 0
    for phase in tab.phases:
        buf.add(f'<div class="phase-label">{_t(phase.label)}</div>')
        for step in phase.steps:
            number += 1
            _render_step(buf, step, number, paints)


def _render_thinning_tab(buf: _Buf, thinning: dict | None) -> None:
    """The Thinning Reference tab (skills-reference.js content, now data-driven
    — spec §9.3). Rendered statically AND emitted as the GUIDE_THINNING JS block
    so the legacy script stays a no-op overwrite."""
    airbrush = (thinning or {}).get("airbrush_rows") or []
    brush = (thinning or {}).get("brush_rows") or []
    cards = (thinning or {}).get("thinning_cards") or []

    if airbrush:
        buf.add('<table class="thinning-table airbrush"><tbody>')
        for row in airbrush:
            buf.add("<tr>")
            buf.add(f'<td class="technique">{_t(str(row.get("technique", "")))}</td>')
            buf.add(f'<td class="nozzle">{_t(str(row.get("nozzle") or ""))}</td>')
            buf.add(f'<td class="ratio">{_t(str(row.get("ratio", "")))}</td>')
            buf.add(f'<td class="behavior">{_t(str(row.get("behavior") or ""))}</td>')
            buf.add("</tr>")
        buf.add("</tbody></table>")
    if brush:
        buf.add('<table class="thinning-table brush"><tbody>')
        for row in brush:
            buf.add("<tr>")
            buf.add(f'<td class="technique">{_t(str(row.get("technique", "")))}</td>')
            buf.add(f'<td class="ratio">{_t(str(row.get("ratio", "")))}</td>')
            buf.add(f'<td class="behavior">{_t(str(row.get("behavior") or ""))}</td>')
            buf.add("</tr>")
        buf.add("</tbody></table>")
    for card in cards:
        buf.add('<div class="thinning-card">')
        buf.add(f'<h4>{_t(str(card.get("title", "")))}</h4>')
        buf.add(f'<p>{_t(str(card.get("body", "")))}</p>')
        buf.add("</div>")


def _guide_thinning_js(thinning: dict | None) -> str:
    """The window.GUIDE_THINNING block skills-reference.js reads. snake_case
    data keys map to the script's camelCase (spec §9.3)."""
    t = thinning or {}
    payload = {
        "airbrushRows": t.get("airbrush_rows") or [],
        "brushRows": t.get("brush_rows") or [],
        "cards": t.get("thinning_cards") or [],
    }
    # </script> can't appear in an inline script body; escape the slash.
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


# showTab/showSubTab ported to inert inline JS so a single exported file still
# works offline without the shared script (spec §9.3 — no global state/storage).
_TAB_JS = """
function showTab(id){
  document.querySelectorAll('.tab-content').forEach(function(el){
    el.classList.toggle('active', el.id === id);
  });
  document.querySelectorAll('.tab-btn').forEach(function(btn){
    btn.classList.toggle('active', btn.dataset.tab === id);
  });
}
function showSubTab(id){
  document.querySelectorAll('.subtab-content').forEach(function(el){
    el.classList.toggle('active', el.id === id);
  });
}
"""


def render_guide_html(db: Session, guide: Guide) -> str:
    """Serialize a guide to a self-contained legacy HTML document."""
    paints = _paint_lookup(db, guide)
    theme = guide.theme or {}
    buf = _Buf()

    buf.add("<!DOCTYPE html>\n")
    root_style = _theme_style(theme)
    style_attr = f' style="{root_style}"' if root_style else ""
    buf.add(f'<html lang="en"{style_attr}>')
    buf.add("<head>")
    buf.add('<meta charset="utf-8">')
    buf.add('<meta name="viewport" content="width=device-width, initial-scale=1">')
    buf.add(f"<title>{_t(guide.title)} — Painting Guide</title>")
    buf.add(f'<link rel="stylesheet" href="{GUIDE_CSS_HREF}">')
    buf.add("</head>")
    buf.add("<body>")

    # --- hero --------------------------------------------------------------
    category = db.get(GuideCategory, guide.category_id) if guide.category_id else None
    hero_grad = theme.get("hero_gradient")
    hero_style = f' style="background:{escape(hero_grad, quote=True)}"' if hero_grad else ""
    buf.add(f'<header class="hero"{hero_style}>')
    if category:
        buf.add(f'<div class="category">{_t(category.display_name)}</div>')
    buf.add(f"<h1>{_t(guide.title)}</h1>")
    brief = guide.character_brief or {}
    if brief.get("philosophy"):
        buf.add(f'<div class="subtitle">{_t(brief["philosophy"])}</div>')
    if guide.franchise:
        buf.add(f'<div class="film-ref">{_t(guide.franchise)}</div>')
    credit = guide.creator_credit or {}
    if credit.get("name"):
        if credit.get("url"):
            buf.add(
                f'<div class="creator-credit">'
                f'<a href="{escape(credit["url"], quote=True)}">{_t(credit["name"])}</a></div>'
            )
        else:
            buf.add(f'<div class="creator-credit">{_t(credit["name"])}</div>')
    buf.add("</header>")

    # --- series badge ------------------------------------------------------
    series = db.get(GuideSeries, guide.series_id) if guide.series_id else None
    if series:
        buf.add('<div class="series-badge">')
        buf.add(f'<span class="series-chip active">{_t(series.display_name)}</span>')
        buf.add("</div>")

    # --- paint bar ---------------------------------------------------------
    if guide.paint_lines_used:
        buf.add('<div class="paint-bar">')
        for line in guide.paint_lines_used:
            buf.add(f'<span class="paint-pill">{_t(str(line))}</span>')
        buf.add("</div>")

    # --- character brief ---------------------------------------------------
    if brief.get("light_source") or brief.get("priority_materials"):
        buf.add('<div class="char-brief">')
        if brief.get("light_source"):
            buf.add(f'<p class="light-source">{_t(brief["light_source"])}</p>')
        for mat in brief.get("priority_materials") or []:
            buf.add(f'<span class="priority-material">{_t(str(mat))}</span>')
        buf.add("</div>")

    # --- tab buttons -------------------------------------------------------
    has_thinning = bool(
        (guide.thinning_config or {}).get("airbrush_rows")
        or (guide.thinning_config or {}).get("brush_rows")
        or (guide.thinning_config or {}).get("thinning_cards")
    )
    tab_ids = [_slugify(tab.name) for tab in guide.tabs]
    buf.add('<nav class="tabs">')
    for i, (tab, tab_id) in enumerate(zip(guide.tabs, tab_ids)):
        active = " active" if i == 0 else ""
        buf.add(
            f'<button class="tab-btn{active}" data-tab="{escape(tab_id, quote=True)}" '
            f"onclick=\"showTab('{escape(tab_id, quote=True)}')\">{_t(tab.name)}</button>"
        )
    if has_thinning:
        buf.add(
            '<button class="tab-btn" data-tab="thinning" '
            "onclick=\"showTab('thinning')\">Thinning Reference</button>"
        )
    buf.add("</nav>")

    # --- tab content -------------------------------------------------------
    for i, (tab, tab_id) in enumerate(zip(guide.tabs, tab_ids)):
        active = " active" if i == 0 else ""
        buf.add(f'<section class="tab-content{active}" id="{escape(tab_id, quote=True)}">')
        _render_tab_body(buf, tab, paints)
        buf.add("</section>")
    if has_thinning:
        buf.add('<section class="tab-content" id="thinning">')
        _render_thinning_tab(buf, guide.thinning_config)
        buf.add("</section>")

    # --- scripts -----------------------------------------------------------
    buf.add(f"<script>window.GUIDE_THINNING = {_guide_thinning_js(guide.thinning_config)};</script>")
    buf.add(f'<script src="{SKILLS_JS_SRC}"></script>')
    buf.add(f"<script>{_TAB_JS}</script>")

    buf.add("</body></html>")
    return str(buf)
