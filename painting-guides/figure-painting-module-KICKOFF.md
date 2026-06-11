# Kickoff Brief — Painting Guides module for STL-Inventory

**For:** Code (you already know the STL-Inventory codebase)
**From:** Brent
**Full spec:** `figure-painting-webapp-spec.md` (this folder) — read Sections 3, 6, 7, 9 first; the rest is reference.
**This brief covers:** the first build phase only — **M0 → M2**. AI generation, color-match, and the public site come later; don't build them yet.

---

## 1. Mission (2 sentences)

Add a **Painting Guides** module *inside* STL-Inventory that lets Brent author value-first miniature/figure painting guides as structured data and export them as PDFs. This phase delivers the data foundation, the Paint Shelf (paint inventory), a faithful guide renderer/print view, the model↔guide link, and an HTML importer that doubles as the renderer's acceptance test.

---

## 2. Decisions already locked (do not re-litigate)

- **It's a module inside STL-Inventory**, not a new app. Same FastAPI app, same React/Vite/Tailwind frontend, same **SQLite** DB, same Docker/binary/backup/CI. Add a `painting/` backend package and new frontend routes.
- **SQLite** (the host DB). No Postgres. JSON columns for the display blocks. Painting tables namespaced `paint_*` / `guide_*`; one cross-module FK only: `guide.model_id → model`.
- **Figure-only** for now. The `wargaming` guide type is designed (spec §6.6) but **not built** this phase.
- **Bring-your-own-key, opt-in.** No API keys in the repo or build. Not relevant to M0–M2 (no AI yet) but keep the module behind an "Enable Painting Guides" setting from the start.
- **Public site is deferred.** Build the reader as an in-app component (for live preview + print/PDF), not a public website.
- **Naming:** paint inventory = **"Paint Shelf"** (avoid colliding with STL-Inventory's model "Library").

---

## 3. Confirm these against the actual repo before coding

These are assumptions from the README; verify in the codebase and adjust:

1. **Schema/migration mechanism** — how STL-Inventory creates/updates tables on startup/upgrade (it supports backup/restore of the .db). Use that same mechanism for the painting tables; don't introduce Alembic if the app doesn't use it.
2. **Primary-key convention** — integer vs UUID on existing tables. Match it for the painting tables.
3. **The `model` table** — exact name + PK + how folder images are stored/served (the reference-image link and image-source reuse depend on this).
4. **Image storage path/volume** — reuse the existing local image volume for reference images.
5. **Frontend data-fetching** — what the app already uses (add TanStack Query only if absent).
6. **Where global nav + Settings + Help are defined** — you'll add entries to each.

---

## 4. Build order

### M0 — Wire the module in (½ sprint)
- Create `backend/painting/` package (layout in spec §8.2); include its router in the host app under `/api/painting/...`.
- Create the painting tables in the existing SQLite DB via the host's schema mechanism (tables from spec §6.2 + the JSON-block columns §6.4). Confirm they ride along in backup/restore.
- Add an **"Enable Painting Guides"** toggle in Settings (off by default in public builds); gate the nav entries on it.
- Add empty **"Guides"** and **"Paint Shelf"** route shells in the React app.
- Extend the pytest suite; CI green.
- **Exit:** app boots, shows empty Guides + Paint Shelf, backups include the new (empty) tables.

### M1 — Paint Shelf (1 sprint) — *the foundation everything stands on*
- `brand` / `paint_line` / `paint` models (spec §6.2), including the derived **`matchable`** flag (from `finish`).
- Paint Shelf table UI reusing STL-Inventory's grid/filter/pagination patterns; render **color chips** from `paint.hex`.
- **PaintRack CSV import with diff** (added/removed/changed preview, confirm-to-apply — never blind overwrite) + **CSV export** in the same format. Seed from Brent's PaintRack export.
- **Code-convention validation** on entry (per-line `code_pattern`).
- **Exit:** real inventory in the DB, round-trips to CSV, renders chips, rejects bad codes.

### M2 — Guide model + renderer + print + model link + golden fixtures (1–2 sprints)
- Full guide schema (spec §6.2–6.5): `Guide → Tab → Phase → Step → Swatch/MixComponent` relational core + JSON blocks (`character_brief`, `theme`, `value_map`, `skin_config`, `metals_config`, `thinning_config`).
- **React reader components** that emit the **existing `guide.css` class names** (`.hero`, `.paint-bar`, `.swatch`, `.ratio-box`, `.phase-label`, `.tip`, `.warning`, value-map, method-cards…). Port `showTab`/`showSubTab` to React state; rebuild the Thinning Reference as a **data-driven component** from `thinning_config` + shared static content (spec §9.3). Reuse `guide.css` as-is, scoped — do **not** re-style guides into Tailwind.
- **Print view** — all tabs/sub-tabs expanded, in order — using the existing `print.css`. (This is the PDF source later.)
- **Static-HTML exporter** — serialize a guide back to the current file format (spec §9.5).
- **Model↔guide link** — `guide.model_id` FK; `ModelLink` component; "Create/View painting guide" on the model detail page; "has guide" badge on model cards.
- **HTML importer + 3–5 golden fixtures** (spec §9.6–9.7) — see §5 below.
- **Exit:** a guide renders identically to a current hand-built HTML guide; **golden fixtures round-trip clean**; print view is complete; guides link to/from their STL model.

---

## 5. The golden-fixture workflow (M2's acceptance test — do this early, not last)

The 38 existing guides in `painting-guides/by-category/**/*.html` are machine-generated from one template, so the DOM is regular and deterministically parseable (mapping table in spec §9.6).

1. Pick **3–5 diverse guides** as fixtures: skin-heavy (`comics/cassie-hack`), metal-heavy/TMM (`film-tv/robocop-1987`), one with OSL/blood, one NMM, one minimal.
2. Write the importer (BeautifulSoup) → `GuideDraft` (Appendix A) + an **import report** (`unresolved_paints`, `ambiguous_codes`, `unmapped_nodes`). Import lands as **`draft`**, never auto-published.
3. **Round-trip test:** import → re-render via the static-HTML exporter → diff against the original file. A clean diff proves the **schema is complete** AND the **renderer is faithful**. Divergences point exactly at the gap — fix the schema/renderer, repeat.
4. Treat the importer as the **acceptance test for the rendering layer**. Build the schema *against these real guides*, not in the abstract.

(Full 38-guide import + inventory-gap/validator-calibration cleanup is M5 — not now.)

---

## 6. Do NOT build this phase

- ❌ AI draft generation (M4) — but design the guide tables so the future `GuideDraft` slots in unchanged (Appendix A).
- ❌ Color-match studio (M4).
- ❌ PDF rendering / Playwright (M3) — M2 stops at the **print view**; PDF wraps it next.
- ❌ The validator's full rule set (M3) — but `paint.exists` + `code_pattern` checks belong in M1.
- ❌ Public website (deferred).
- ❌ Wargaming guide type (designed, not built).

---

## 7. Definition of done for this phase

- `docker compose up` (and the standalone binary build) run with the module present; CI green; painting tests in the suite.
- Paint Shelf holds Brent's real inventory, round-trips to PaintRack CSV, renders chips, validates codes.
- A guide authored as data renders pixel-faithfully to the current style, prints complete, and exports to the legacy HTML format.
- 3–5 golden guides import and round-trip clean.
- A guide links to/from its STL-Inventory model.
- The whole module sits behind the "Enable Painting Guides" setting and ships **no keys or personal data**.

---

## 8. Spec section map (where to look)

| Need | Spec section |
|---|---|
| Why-a-module, reuse table, model↔guide link, naming | §3 |
| Data model + JSON blocks + `GuideDraft` | §6 + **Appendix A** |
| API surface | §7 |
| Backend package layout, validation rules (later), color-match (later) | §8 + **Appendix B** |
| Rendering strategy, importer, golden fixtures | §9 |
| Frontend components | §10 |
| Deployment, secrets, feature flags | §4.7, §14 |
| Milestones | §15 |
| Open questions (hosting, wargaming, etc.) | §17 |

---

*Start with §3 of the full spec, confirm the §3-of-this-brief repo facts, then M0. Ping Brent on any repo-fact surprise before building on an assumption.*
