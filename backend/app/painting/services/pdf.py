"""PDF export: guide HTML -> Playwright/Chromium -> print-ready PDF (spec §9.4).

Single-guide only (series bundling, async-job caching and reward stamping are
deferred — see #320). The PDF reuses the exact static-HTML export the round-trip
importer consumes (`rendering.render_guide_html`), but with the four corpus
assets (guide.css / print.css / guide.js / skills-reference.js) **inlined** so
the document is fully self-contained — the corpus `painting-guides/assets/`
directory isn't shipped in the Docker image or the standalone binary, only the
copies bundled under this package's `data/assets/` are.

Rendering runs the guide through headless Chromium with print media emulated, so
the same `@media print` rules that drive the in-browser print view (#262) shape
the PDF. JS runs, so the skills tabs and thinning tables that skills-reference.js
injects at runtime appear in the output.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.painting.models import Guide
from app.painting.services.rendering import (
    GUIDE_CSS_HREF,
    GUIDE_JS_SRC,
    PRINT_CSS_HREF,
    SKILLS_JS_SRC,
    render_guide_html,
)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "data" / "assets"


class ChromiumNotInstalledError(RuntimeError):
    """Raised when Playwright's Chromium browser isn't installed.

    In Docker/CI it's installed at build time; the standalone binary needs a
    one-time `playwright install chromium` on first use (PyInstaller can't bundle
    the browser). The router maps this to a 503 with remediation guidance.
    """


def _read_asset(name: str) -> str:
    return (_ASSETS_DIR / name).read_text(encoding="utf-8")


def render_guide_pdf_html(db: Session, guide: Guide) -> str:
    """The static-HTML export with all four corpus assets inlined.

    Built by post-processing `render_guide_html` output: the emitted asset tags
    are deterministic (constructed from the rendering module's href constants),
    so we reconstruct each exact tag and swap it for an inline equivalent. This
    keeps `render_guide_html` byte-identical for the #261 round-trip while making
    the PDF source self-contained.
    """
    html = render_guide_html(db, guide)

    guide_css = _read_asset("guide.css")
    print_css = _read_asset("print.css")
    guide_js = _read_asset("guide.js")
    skills_js = _read_asset("skills-reference.js")

    replacements = {
        f'  <link rel="stylesheet" href="{GUIDE_CSS_HREF}">':
            f"  <style>\n{guide_css}\n  </style>",
        f'  <link rel="stylesheet" href="{PRINT_CSS_HREF}" media="print">':
            f'  <style media="print">\n{print_css}\n  </style>',
        f'<script src="{GUIDE_JS_SRC}"></script>':
            f"<script>\n{guide_js}\n</script>",
        f'<script src="{SKILLS_JS_SRC}"></script>':
            f"<script>\n{skills_js}\n</script>",
    }
    for tag, inline in replacements.items():
        if tag not in html:
            raise RuntimeError(f"expected asset tag not found in export HTML: {tag!r}")
        html = html.replace(tag, inline, 1)
    return html


async def render_guide_pdf(db: Session, guide: Guide) -> bytes:
    """Render a guide to a print-ready PDF via headless Chromium.

    Uses Playwright's async API (the FastAPI request handler runs on the event
    loop, so the sync API would error). Print media is emulated and backgrounds
    are printed so swatch chips / value maps / theme colors come out right.
    """
    # Imported lazily: Playwright pulls in heavy native bits, and importing it is
    # pointless on code paths that never render a PDF (e.g. the test suite when
    # Chromium isn't installed).
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    html = render_guide_pdf_html(db, guide)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="networkidle")
                await page.emulate_media(media="print")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
                )
            finally:
                await browser.close()
    except PlaywrightError as exc:
        # Launch fails this way when the browser binary is missing.
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            raise ChromiumNotInstalledError(str(exc)) from exc
        raise
