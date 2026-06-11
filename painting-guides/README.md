# Painting-guide corpus

The hand-built / machine-generated painting guides that the Painting module's
renderer and importer are developed against. These are the **ground truth** for
the rendering layer (spec §9.7): the static-HTML exporter (#260) must reproduce
this DOM, and the HTML importer (#261) parses it back into structured guides.
The round-trip — import → export → diff against the original here — is the
renderer's acceptance test.

```
painting-guides/
  assets/                     shared stylesheet + scripts every guide links
    guide.css                 design tokens / layout
    print.css                 print + PDF layout
    guide.js                  showTab() tab switching
    skills-reference.js       injects the Thinning Ref / skills tabs from
                              window.GUIDE_THINNING
  by-category/<category>/<slug>-painting-guide.html
```

All guides share one template, so the DOM is highly regular and deterministically
parseable. The corpus is also the seed/demo content and the AI house-style
reference (spec §8.3).

Notes:
- Reference images (`img/`) were intentionally left out — only the HTML/asset
  structure is needed for the round-trip diff, and the binaries bloat the repo.
  The `<img src="img/…">` paths remain in the HTML.
- The full-corpus import is M5; M2 uses a diverse handful as golden fixtures.
