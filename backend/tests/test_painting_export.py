"""Static-HTML exporter (M2, #260): serialize a stored guide back to the
legacy self-contained HTML shape (spec §9.5/§9.6).

The DOM emitted here is the canonical legacy contract the importer (#261) will
be written to match, so these tests pin the class-name mapping from spec §9.6.
"""
import re

import pytest

from tests.test_painting_guides import guide_body, mk_paint


@pytest.fixture
def line(client):
    brand = client.post("/painting/brands", json={"name": "Monument Hobbies"}).json()
    return client.post(
        "/painting/lines", json={"brand_id": brand["id"], "name": "Pro Acryl"}
    ).json()


@pytest.fixture
def paint(client, line):
    return mk_paint(client, line["id"])


def _export(client, guide_id):
    r = client.get(f"/painting/guides/{guide_id}/export")
    assert r.status_code == 200, r.text
    return r


class TestExportEndpoint:
    def test_unknown_guide_404(self, client):
        assert client.get("/painting/guides/999/export").status_code == 404

    def test_download_headers_and_content_type(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        r = _export(client, g["id"])
        assert r.headers["content-type"].startswith("text/html")
        assert 'filename="robocop-1987.html"' in r.headers["content-disposition"]

    def test_self_contained_document_shell(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert "<title>RoboCop — Painting Guide</title>" in html
        assert 'rel="stylesheet"' in html  # links shared guide.css


class TestHeroAndChrome:
    def test_hero_carries_title_and_brief(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert '<header class="hero"' in html
        assert "<h1>RoboCop</h1>" in html
        assert '<div class="subtitle">value first</div>' in html

    def test_franchise_and_creator_credit(self, client, paint):
        body = guide_body(
            paint["id"],
            franchise="RoboCop (1987)",
            creator_credit={"name": "Big Sculptor", "url": "https://example.com/s"},
        )
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<div class="film-ref">RoboCop (1987)</div>' in html
        assert '<div class="creator-credit"><a href="https://example.com/s">Big Sculptor</a></div>' in html

    def test_paint_bar_pills(self, client, paint):
        body = guide_body(paint["id"], paint_lines_used=["Pro Acryl", "Speedpaint 2.0"])
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<span class="paint-pill">Pro Acryl</span>' in html
        assert '<span class="paint-pill">Speedpaint 2.0</span>' in html

    def test_category_label_in_hero(self, client, paint):
        cat = client.post(
            "/painting/categories", json={"slug": "comics", "display_name": "Comics"}
        ).json()
        body = guide_body(paint["id"], slug="x1", category_id=cat["id"])
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<div class="category">Comics</div>' in html

    def test_series_badge(self, client, paint):
        series = client.post(
            "/painting/series", json={"slug": "robo", "display_name": "RoboCop Trilogy"}
        ).json()
        body = guide_body(paint["id"], series_id=series["id"])
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<div class="series-badge">' in html
        assert 'class="series-chip active">RoboCop Trilogy<' in html

    def test_no_series_badge_when_absent(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert "series-badge" not in html


class TestTabsAndSteps:
    def test_tab_button_and_content_ids_match(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        # "Metals" tab -> id "metals", first tab is active.
        assert "showTab('metals')" in html
        assert '<button class="tab-btn active" data-tab="metals"' in html
        assert '<section class="tab-content active" id="metals">' in html

    def test_phase_label_and_step_number_technique(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert '<div class="phase-label">Base</div>' in html
        # technique_tag rides on the .step-number class; steps are numbered.
        assert '<div class="step-number airbrush">1</div>' in html
        assert '<h3 class="step-title">Gloss black base</h3>' in html

    def test_swatch_name_code_brand_value(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert '<span class="swatch-dot" style="background:#2A2A2A"></span>' in html
        # name + trailing code (spec §9.6 split target).
        assert '<span class="swatch-name">Coal Black 002</span>' in html
        assert '<span class="swatch-brand">Monument Hobbies</span>' in html
        assert '<span class="swatch-value">~10% value — shadow base</span>' in html

    def test_tip_and_warning_prefixes(self, client, paint):
        body = guide_body(paint["id"])
        body["tabs"][0]["phases"][0]["steps"][0]["warning"] = "Don't overthin."
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<div class="tip">✦ TIP: Thin to milk.</div>' in html
        assert '<div class="warning">⚠ NOTE: Don\'t overthin.</div>' in html

    def test_ratio_box_verbatim(self, client, paint):
        body = guide_body(paint["id"])
        body["tabs"][0]["phases"][0]["steps"][0]["ratio_box"] = "1:1 Warm Flesh + Peach — thin"
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert '<div class="ratio-box">1:1 Warm Flesh + Peach — thin</div>' in html

    def test_value_map_chips(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert '<div class="value-map">' in html
        assert '<span class="chip-swatch" style="background:#101010"></span>' in html
        assert '<span class="chip-val">10%</span>' in html
        assert '<span class="chip-label">deep shadow</span>' in html


class TestThemeAndThinning:
    def test_theme_vars_inline_and_hero_gradient(self, client, paint):
        body = guide_body(
            paint["id"],
            theme={"accent": "#c0a060", "bg": "#101015",
                   "hero_gradient": "linear-gradient(90deg, #111, #222)"},
        )
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert "--accent: #c0a060" in html
        assert "--bg: #101015" in html
        assert 'class="hero" style="background:linear-gradient(90deg, #111, #222)"' in html

    def test_thinning_tab_and_guide_thinning_js(self, client, paint):
        body = guide_body(
            paint["id"],
            thinning_config={
                "airbrush_rows": [
                    {"technique": "Base", "nozzle": "0.4mm", "ratio": "2:1",
                     "behavior": "milk"},
                ],
                "brush_rows": [{"technique": "Glaze", "ratio": "1:4"}],
                "thinning_cards": [{"title": "Tip-Dry", "body": "Wipe often."}],
            },
        )
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        # rendered tab
        assert "showTab('thinning')" in html
        assert '<section class="tab-content" id="thinning">' in html
        assert "Tip-Dry" in html
        # JS block in camelCase for skills-reference.js
        m = re.search(r"window\.GUIDE_THINNING = (\{.*?\});", html)
        assert m, "GUIDE_THINNING block missing"
        assert '"airbrushRows"' in m.group(1)
        assert '"brushRows"' in m.group(1)

    def test_no_thinning_tab_when_config_empty(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        html = _export(client, g["id"]).text
        assert "id=\"thinning\"" not in html
        # block still present but empty (script is a harmless no-op overwrite).
        assert '"airbrushRows": []' in html or '"airbrushRows":[]' in html


class TestEscapingAndStability:
    def test_html_in_text_is_escaped(self, client, paint):
        body = guide_body(paint["id"], title="Robo<script>alert(1)</script>")
        g = client.post("/painting/guides", json=body).json()
        html = _export(client, g["id"]).text
        assert "<script>alert(1)</script>" not in html
        assert "Robo&lt;script&gt;" in html

    def test_export_is_deterministic(self, client, paint):
        g = client.post("/painting/guides", json=guide_body(paint["id"])).json()
        first = _export(client, g["id"]).text
        second = _export(client, g["id"]).text
        assert first == second
