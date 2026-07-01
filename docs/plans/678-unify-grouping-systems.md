# Plan — #678: converge the two variant-grouping systems onto durable groups

**Parent:** #674 (flaky manual grouping)
**Related (done):** #675, #676, #677, #686 (dual-write bridges — the short-term mitigation this plan retires)
**Type:** structural refactor + data migration. **Multi-PR — do not land in one shot.**

---

## The actual shape of the problem

It is not two symmetric systems. It is **three roles** that got tangled, two of which share the
`character` column:

1. **Auto durable groups** — `variant_group_id` → `VariantGroup(source="auto")`, derived by
   `grouping.regroup_creator` from hash / filename / name-key signals. Runs for every creator on every
   scan ([scanner.py:762](../../backend/app/services/scanner.py)). Covers the bulk of real variants.
2. **Manual durable groups** — `VariantGroup(source="manual")`, written by `mergeGroup` (BulkTagBar,
   drag-merge via #686). The scanner never touches these.
3. **User character overrides** — `GroupOverride(path, character)` → applied to `model.character` at scan
   time ([scanner.py:1007](../../backend/app/services/scanner.py)). This is the legacy manual-grouping
   mechanism, and it is **invisible to the durable engine**: `regroup_creator` explicitly excludes any
   model whose folder has a `GroupOverride` row ([grouping.py:117](../../backend/app/services/grouping.py)).
   So these groups exist **only** as the `ch:` fallback in the read-path key.

The read path unifies (1)+(2) under `vg:` and (3) under `ch:`
([`_group_key_sql`, models.py:201](../../backend/app/routers/models.py)):

```
vg:<variant_group_id>            if variant_group_id is set        (roles 1 & 2)
ch:<creator_id>:<character>      else, if character is set         (role 3, + any scanner-derived character)
```

Two extra wrinkles:

- **`character` is also a plain scanner attribute.** Even with no override, the name parser sets
  `model.character` from the folder name, and the engine's "name key" signal
  ([grouping.py:201](../../backend/app/services/grouping.py)) is the *same derivation*. So auto groups and
  the `ch:` fallback often encode the *same* intent by two mechanisms — redundant, and the source of
  "sometimes it groups, sometimes it doesn't" when only one of the two is present.
- **`GroupOverride` with `character=None`** is a meaningful signal: "explicitly ungrouped, keep it out of
  any group across rescans." That role must survive whatever we do.

## Target end-state

- **All manual grouping is durable.** Merge / split / rename / drag / per-model regroup all write
  `VariantGroup` rows. `mergeGroup` / `splitGroup` / `patchGroup` become the only manual-grouping API.
- **`character` becomes a read-only scanner-derived attribute** — a display/label input and a grouping
  *signal* for the engine, never a grouping key on its own.
- **The `ch:` fallback is removed** from `_group_key_sql` / `_group_key_py`. `variant_group_id` is the sole
  grouping key.
- **`GroupOverride` is retired as a grouping tool.** Its one surviving job — "explicitly ungrouped, sticky
  across rescans" — moves to an explicit durable mechanism (see Phase decisions).

## Why phased (and why not all at once)

Removing the `ch:` fallback the moment it has live dependents makes every existing user-character group
vanish until something regroups it durably. And the frontend has ~10 character-system call sites across
4 components (VariantGroup.tsx alone has 6). A single PR here is how you lose a weekend of someone's
carefully curated collection. Each phase below is independently shippable and leaves grouping correct.

---

## Phase 0 — Freeze & characterize (tests only, no behavior change)

Lock current grouping behavior in tests before touching it, so each later phase has a regression net.

- Golden tests over `_group_key_sql`: auto group, manual group, user-character group, explicit-ungroup,
  and a model with scanner-derived `character` but no override.
- Backend test: a user `batchSetGroup` character group of models the engine would NOT auto-group (distinct
  names, no shared hash/filename) — confirm it currently collapses via `ch:` and record member count.

**Files:** `backend/tests/test_grouping.py`, `test_api_models.py`. **Risk:** none.

## Phase 1 — Migration: backfill durable groups from user character overrides

One-time Alembic data migration (+ a re-runnable service fn for safety): for each creator, every set of
≥2 non-excluded models that share a **user-set** `character` (i.e. a `GroupOverride` row with non-null
character) and have no `variant_group_id` → create a `VariantGroup(source="manual", label=character)` and
point them at it. Preserve `rep_model_id` heuristics. Leave `GroupOverride(character=None)` rows alone.

- New migration `0019_backfill_manual_groups_from_overrides` (head is currently 0018 — confirm before
  writing).
- Extract the backfill as a service fn so it can be unit-tested on a seeded DB and re-run idempotently.

**Files:** `backend/alembic/versions/0019_*.py`, `backend/app/services/grouping.py` (backfill fn), tests.
**Risk:** medium — must be idempotent and must not merge distinct auto groups. Gate on `source` and
null `variant_group_id`. **Decision needed:** does the backfill also cover scanner-*derived* character
(no override row) that currently only groups via `ch:`? Recommend **no** — those are the engine's job;
let `regroup_creator` own them (Phase 2). Only migrate explicit user overrides.

## Phase 2 — Make the engine own scanner-character grouping; stop excluding overrides

So that removing the `ch:` fallback loses nothing:

- Drop the `override_paths` exclusion in `regroup_creator` ([grouping.py:117](../../backend/app/services/grouping.py))
  **for character overrides specifically** — instead, feed a user override in as a *forced* grouping
  signal (strongest, like a manual pin) so the engine emits a durable group for it. Keep excluding
  `character=None` (explicit ungroup) and `source="manual"` members.
- Verify the engine's name-key signal already covers scanner-derived character (it uses the same
  `character_key`) — add tests proving a scanner-character trio becomes a durable auto group without any
  `ch:` fallback.

**Files:** `grouping.py`, `test_grouping.py`. **Risk:** high — this is the behavioral heart. Phase 0
goldens + Phase 1 migration must be green first.

## Phase 3 — Remove the `ch:` fallback from the read path

Once Phases 1–2 guarantee durable coverage:

- Simplify `_group_key_sql` / `_group_key_py` to `vg:` only. A model with no `variant_group_id` is
  ungrouped, full stop.
- Delete the now-dead vc_map "ch:" branch in the list endpoint
  ([models.py:359](../../backend/app/routers/models.py)) and the `variants` endpoint's character path
  ([models.py](../../backend/app/routers/models.py)) — or keep the character arg as a pure filter, decide
  during impl.

**Files:** `models.py`, tests. **Risk:** high — but de-risked by prior phases. This is the payoff commit.

## Phase 4 — Frontend convergence

Route every manual-grouping action through the durable API. Enumerated call sites (main):

- `Library.tsx` — the two residual legacy drags (deferred here from #677): `prompt`/`confirmMerge` and the
  char-only `apply` branch → `mergeIntoDurableGroup`.
- `ModelCard.tsx:133` — inline rename via `batchSetGroup` → `patchGroup` / `mergeGroup`.
- `ModelDetail.tsx:383,403` — `setGroupOverride`/`clearGroupOverride` (single model) → durable
  join/leave. Needs a "which group?" affordance or a create-single-member-group semantics call.
- `VariantGroup.tsx` — 6 `applyGroup` sites (rename, remove, bulk move, ungroup): rename → `patchGroup`;
  remove/ungroup → `splitGroup`; bulk move → `mergeGroup`.

Do this **component by component**, each its own PR, after the backend (Phases 1–3) can represent every
action durably. **Risk:** medium, spread thin by slicing per component.

## Phase 5 — Retire `GroupOverride` as a grouping tool

- Replace the surviving `character=None` "explicit ungroup, sticky" role with a durable equivalent — e.g.
  a per-model `grouping_locked`/`no_group` flag, or a reserved sentinel. **Decision needed:** new column
  vs. reuse. Recommend a small explicit boolean over overloading a nullable string.
- Repoint the scanner's exclusion logic and the reorganize repath
  ([reorganize_apply.py:364](../../backend/app/services/reorganize_apply.py)) off `GroupOverride`.
- Migration to drop the table once nothing reads it. Keep `character` the column (scanner attribute).

**Risk:** medium. Purely a cleanup once Phases 1–4 land; can trail well behind.

---

## Cross-cutting decisions (LOCKED)

1. **Explicit-ungroup mechanism** (Phase 5): **new `Model.no_group` boolean.** Self-documenting; kills the
   nullable-string `GroupOverride(character=None)` overload.
2. **Backfill scope** (Phase 1): **user overrides only.** Scanner-derived character grouping stays the
   engine's job (Phase 2); only explicit `GroupOverride` rows with non-null character are migrated.
3. **Single-model grouping UX** (`ModelDetail`, Phase 4): still open — simplest is "remove from group"
   (`splitGroup`) + "merge into…" picker; defer creating-from-one until the UX is designed. Not blocking
   Phases 0–3.

## Sequencing & shippability

Phase 0 → 1 → 2 → 3 are backend and must go in order (each green before the next). Phase 4 can begin
component-by-component as soon as Phase 3 ships. Phase 5 trails. Every phase leaves the app with correct,
consistent grouping — that is the whole point of slicing it this way.

## Out of scope

- Changing the auto-grouping *signal* thresholds (hash/filename/name-key tuning) — that's grouping-quality
  work (#639 lineage), orthogonal to unifying the systems.
- Any change to tags, collections, or pack-overrides (`PackOverride` is a separate concern despite the
  parallel shape).
