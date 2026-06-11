/*!
 * skills-reference.js
 * Shared static content for all figure painting guides.
 *
 * Injects into three tabs on DOMContentLoaded:
 *   #thinning-ref     — fully builds this tab from window.GUIDE_THINNING config
 *   #airbrush-skills  — injects zenithal sequence, greyscale check, Tip Dry card
 *   #brush-skills     — injects greyscale check tip
 *
 * window.GUIDE_THINNING config (define in guide before this script loads):
 * {
 *   airbrushRows:  [ { technique, nozzle, ratio, behavior } ],  // inserted after zenithal rows
 *   brushRows:     [ { technique, ratio, behavior } ],           // optional; appended after standard rows
 *   thinningCards: [ { title, body } ]                          // optional; appended after static cards
 * }
 */
(function () {
  'use strict';

  // ── HELPERS ──────────────────────────────────────────────────────────────────

  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function rows(arr, cols) {
    return arr.map(function (r) {
      return '<tr>' + cols.map(function (k) { return '<td>' + esc(r[k] || '') + '</td>'; }).join('') + '</tr>';
    }).join('');
  }

  // ── THINNING REFERENCE TAB ───────────────────────────────────────────────────
  // Fully builds #thinning-ref from the GUIDE_THINNING config object.

  function buildThinningRef() {
    var tab = document.getElementById('thinning-ref');
    if (!tab) return;

    var cfg          = window.GUIDE_THINNING  || {};
    var airRows      = cfg.airbrushRows        || [];
    var brushRows    = cfg.brushRows           || [];
    var extraCards   = cfg.thinningCards       || [];

    tab.innerHTML = [

      '<div class="section-header">',
        '<h2>Thinning Reference</h2>',
        '<p>Ratios, flow behavior, and coverage tests for every technique in this guide.',
        ' Ratios and observable behavior only.</p>',
      '</div>',

      // ── Nozzle callout ────────────────────────────────────────────────────────
      '<div class="nozzle-callout">',
        '<h4>🎯 Nozzle Size = Paint Fraction</h4>',
        '<p>',
          '<strong>0.5mm nozzle → 50% paint</strong> (1:1 paint:thinner) &nbsp;·&nbsp; ',
          '<strong>0.3mm nozzle → 30% paint</strong> (~1:2.3 paint:thinner) &nbsp;·&nbsp; ',
          '<strong>0.2mm nozzle → 20% paint</strong> (1:4 paint:thinner)',
          '<br>Starting points only. Adjust for pigment density and humidity.',
          ' Flow test on a card before each session.',
          '<br><strong>Primer exception: Do NOT thin primer.</strong>',
          ' Use undiluted at 30+ PSI, 0.5mm nozzle.',
        '</p>',
      '</div>',

      // ── Airbrush thinning table ───────────────────────────────────────────────
      '<div class="phase-label">Airbrush Thinning</div>',
      '<table class="thin-table">',
        '<thead><tr>',
          '<th>Technique</th><th>Nozzle</th>',
          '<th>Ratio (paint:thinner)</th><th>Behavior</th>',
        '</tr></thead>',
        '<tbody>',
          // Static rows — always present
          '<tr><td>Priming</td><td>0.5mm</td>',
            '<td>Undiluted — do not thin</td>',
            '<td>Full opaque coverage; flows freely at 30+ PSI without clogging.</td></tr>',
          '<tr><td>Zenithal — black prime</td><td>0.5mm</td>',
            '<td>Undiluted (primer)</td>',
            '<td>Full coverage from all angles; black retained fully in recesses and undercuts.</td></tr>',
          '<tr><td>Zenithal — white prime</td><td>0.5mm</td>',
            '<td>Undiluted (primer)</td>',
            '<td>Heavy from directly above; fades to nothing at sides.</td></tr>',
          // Per-guide rows (base coat, skin highlight, etc.)
          rows(airRows, ['technique', 'nozzle', 'ratio', 'behavior']),
          // Static rows — always present after per-guide rows
          '<tr><td>Transparent / glaze layer</td><td>0.2mm</td>',
            '<td>1:6 to 1:10</td>',
            '<td>Near-watercolor; thin color-temperature shift over sealed surface.</td></tr>',
          '<tr><td>Freckling</td><td>0.2mm</td>',
            '<td>1:8 to 1:12</td>',
            '<td>Atomizes to micro-dots at 3–5cm with needle almost closed. Practice on card first.</td></tr>',
          '<tr><td>Speedpaint 2.0 — standard</td><td>0.3mm</td>',
            '<td>Undiluted or 1:1 with Speedpaint Medium</td>',
            '<td>One-pass product. Let flow and leave it — overworking activates self-leveling agent.</td></tr>',
          '<tr><td>Speedpaint 2.0 — filter</td><td>0.3mm</td>',
            '<td>1:3 Speedpaint : Speedpaint Medium</td>',
            '<td>Over fully dried and varnished layer only. Wipe back lightly with damp flat brush for control.</td></tr>',
        '</tbody>',
      '</table>',

      // ── Brush thinning table ──────────────────────────────────────────────────
      '<div class="phase-label">Brush Thinning</div>',
      '<table class="thin-table">',
        '<thead><tr>',
          '<th>Technique</th><th>Ratio (paint:water)</th><th>Behavior</th>',
        '</tr></thead>',
        '<tbody>',
          '<tr><td>Base coat</td><td>2:1</td>',
            '<td>Full coverage in two passes; some brush drag acceptable.</td></tr>',
          '<tr><td>Layering</td><td>1:1</td>',
            '<td>Semi-transparent; builds in thin passes without obscuring underlayer.</td></tr>',
          '<tr><td>Glazing</td><td>1:4 to 1:8</td>',
            '<td>Highly transparent color shift; pools lightly in recesses.</td></tr>',
          '<tr><td>Wash / pin wash</td><td>1:6 to 1:10</td>',
            '<td>Flows into recesses via capillary action; do not brush around once placed.</td></tr>',
          '<tr><td>Wet blending</td><td>1:0.5 (minimal thinner)</td>',
            '<td>Re-wettable window; color pulled while wet using a clean damp brush.</td></tr>',
          '<tr><td>Expert Acrylics — glaze</td><td>1:3 to 1:5</td>',
            '<td>Heavy pigment; needs more thinner than standard acrylics. Test on card first.</td></tr>',
          '<tr><td>Expert Acrylics — drybrush</td><td>Near-undiluted</td>',
            '<td>Heavy-body holds on nearly dry brush; wipe to almost-dry before loading.</td></tr>',
          rows(brushRows, ['technique', 'ratio', 'behavior']),
        '</tbody>',
      '</table>',

      // ── Thinning cards ────────────────────────────────────────────────────────
      '<div class="thinning-grid">',

        '<div class="thinning-card">',
          '<h4>Flow Improver</h4>',
          '<p>Add 5–10% flow improver to airbrush mixes to reduce surface tension and prevent tip dry.',
          ' Do not exceed 15% — reduces adhesion on varnished surfaces.</p>',
        '</div>',

        '<div class="thinning-card">',
          '<h4>Speedpaint 2.0 — Key Rules</h4>',
          '<p>Always thin Speedpaint 2.0 with <strong>Speedpaint Medium</strong>, not water.',
          ' As a filter, apply 1:3 Speedpaint:Speedpaint Medium over a sealed (varnished) surface only',
          ' — never over bare or unsealed acrylics.</p>',
        '</div>',

        '<div class="thinning-card">',
          '<h4>Transparent Red ⚠</h4>',
          '<p>Pro Acryl Transparent Red 047 turns <strong>magenta</strong> when thinned.',
          ' For any thinned or glazed transparent red application (glazes, color filters, washes),',
          ' use <strong>FW Crimson Ink</strong> instead.',
          ' PA Transparent Red 047 is fine undiluted or minimally thinned where full body is maintained.</p>',
        '</div>',

        extraCards.map(function (c) {
          return '<div class="thinning-card"><h4>' + esc(c.title) + '</h4><p>' + esc(c.body) + '</p></div>';
        }).join(''),

      '</div>', // end .thinning-grid

    ].join('');
  }

  // ── AIRBRUSH SKILLS — static injections ──────────────────────────────────────
  // Injects after anchor divs already in the tab; does not replace the full tab.
  //
  // Anchor IDs expected in the guide:
  //   #ab-zenithal-anchor   — placed after Zenithal Sequence phase-label
  //   #ab-greyscale-anchor  — placed after PSI table
  // Existing .trouble-grid — Tip Dry card prepended as first card

  function injectAirbrushStatics() {
    var tab = document.getElementById('airbrush-skills');
    if (!tab) return;

    // Zenithal steps
    var zenAnchor = document.getElementById('ab-zenithal-anchor');
    if (zenAnchor) {
      zenAnchor.insertAdjacentHTML('afterend', [
        '<div class="step">',
          '<span class="step-number airbrush">Airbrush · Zenithal Step 1</span>',
          '<h3>Black Prime</h3>',
          '<p>P-002 Black Primer — undiluted, 0.5mm nozzle, 30+ PSI, 20–25cm.',
          ' Full coverage from all angles. No bare surface showing.</p>',
          '<div class="warning"><strong>⚠ NOTE:</strong> Do NOT thin primer.',
          ' Thinning breaks down its purpose and turns it into paint.',
          ' Use undiluted at 30+ PSI with a 0.5mm nozzle.</div>',
        '</div>',
        '<div class="step">',
          '<span class="step-number airbrush">Airbrush · Zenithal Step 2</span>',
          '<h3>White Zenithal — Top Down</h3>',
          '<p>P-003 White Primer — undiluted, 0.5mm nozzle, 30+ PSI, 20–25cm.',
          ' Heavy from directly above, fading to nothing at the sides.',
          ' Black retained fully in recesses and undercuts.</p>',
          '<div class="tip"><strong>✦ TIP:</strong>',
          ' Photograph and desaturate immediately after this step.',
          ' Confirm full value range before adding any color.</div>',
        '</div>',
      ].join(''));
    }

    // Greyscale check tip
    var gsAnchor = document.getElementById('ab-greyscale-anchor');
    if (gsAnchor) {
      gsAnchor.insertAdjacentHTML('afterend', [
        '<div class="tip">',
          '<strong>✦ GREYSCALE CHECK:</strong>',
          ' After zenithal and before any color, photograph the figure and desaturate.',
          ' Confirm a full value range from near-black in recesses to near-white on top planes.',
          ' If you don\'t have value contrast in greyscale, color won\'t save it.',
        '</div>',
      ].join(''));
    }

    // Tip Dry — prepended as first card in .trouble-grid
    var troubleGrid = tab.querySelector('.trouble-grid');
    if (troubleGrid) {
      troubleGrid.insertAdjacentHTML('afterbegin', [
        '<div class="trouble-card">',
          '<h4>Tip Dry / Spattering</h4>',
          '<p>Paint dries on needle tip causing spits and spatters.',
          ' Cause: paint too thick, low humidity, or pausing too long between passes.',
          ' Fix: add 5–10% flow improver.',
          ' Between passes, remove dried paint from the needle tip using a dry brush lightly dipped',
          ' in airbrush cleaner or thinner — gentle strokes,',
          ' do not let the ferrule enter the airbrush cap.</p>',
        '</div>',
      ].join(''));
    }
  }

  // ── BRUSH SKILLS — greyscale check ───────────────────────────────────────────

  function injectBrushStatics() {
    var tab = document.getElementById('brush-skills');
    if (!tab) return;
    tab.insertAdjacentHTML('beforeend', [
      '<div class="tip">',
        '<strong>✦ GREYSCALE CHECK:</strong>',
        ' At any point during painting, desaturate a photo of the figure in your phone\'s editor.',
        ' It should read clearly in greyscale — visible light source, form, and depth.',
        ' If it looks flat, values are too compressed. Fix values before correcting color.',
      '</div>',
    ].join(''));
  }

  // ── INIT ──────────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    buildThinningRef();
    injectAirbrushStatics();
    injectBrushStatics();
  });

}());
