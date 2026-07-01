# Plan — #677: `confirmGroupMerge` must resolve full group membership on drag-merge

**Parent:** #674 (flaky manual grouping)
**Related:** #665 (variants endpoint `group_id` param), #686 (merged — preserve manual groups), #678 (two-systems tech debt)

---

## ⚠️ Key finding — the literal fix already landed in #686

#677 asked for one change: pass `source.variant_group_id` as the third arg to `api.models.variants`
in `confirmGroupMerge`. **That change is already on `main`** ([Library.tsx:653](../../frontend/src/pages/Library.tsx)):

```ts
const members = await api.models.variants(
  source.creator_id!,
  source.character || "",
  source.variant_group_id,        // ← the #677 fix, shipped in #686
);
```

#686 went further and introduced `mergeIntoDurableGroup`, routing drag-merges through the durable
`mergeGroup` endpoint instead of the legacy `batchSetGroup` character path. So the corruption #677
described (partial membership + orphaned durable group) is fixed in the code.

**What #686 did NOT add: any test.** `dragGroup.test.ts` covers only the pure `resolveDragIntent`
decision. Nothing exercises `confirmGroupMerge`, `mergeIntoDurableGroup`, or `confirmMerge`. If someone
drops the third arg, or flips a branch back to `applyGroup`, **no test catches it** — the exact
regression #677 warns about would silently return.

So #677 is not "write the fix" — it's **lock the fix in and close the residual gaps.**

## Goal

1. Add regression coverage that fails if drag-merge stops resolving full membership or stops using the
   durable path.
2. Decide the two residual legacy-character-path drags (below) — fix here or defer to #678.

---

## Current drag-merge decision tree (post-#686)

`onDragEnd` → `resolveDragIntent` → one of four intents:

| Intent | Trigger | Handler | System | Correct? |
|---|---|---|---|---|
| `group-merge` | dragged card **is a group** (`variant_count > 1`) | `confirmGroupMerge` → `mergeIntoDurableGroup` | durable | ✅ #686 |
| `apply` (target has `variant_group_id`) | single card → durable group | `mergeIntoDurableGroup` | durable | ✅ #686 |
| `apply` (target char-only, no `variant_group_id`) | single card → **legacy character group** | `applyGroup` → `batchSetGroup` | character | ⚠️ residual |
| `prompt` | single card(s) → **ungrouped** target | `confirmMerge` → `applyGroup` | character | ⚠️ residual |

The two ⚠️ rows still create/extend **character** groups, not durable ones. They don't corrupt anything
(no durable group is involved), but they perpetuate the two-systems split (#678): a brand-new group made
by dragging two loose models together is a character group, while the Merge button makes a durable one.

## Scope decision (LOCKED)

**#677 stays tight — regression tests only. The two residual legacy-character-path drags are deferred to
#678** (captured there for the next work session). Rationale: #677 is specifically the "membership
resolution on group-merge" bug, which is already fixed in code; the residual paths are the two-systems
reconciliation problem #678 owns. Folding them in would expand a medium bug into a refactor that
front-runs #678's design.

---

## Approach (recommended scope)

The blocker for testing is architectural: the merge-execution logic lives inline in `confirmGroupMerge` /
`confirmMerge`, reachable only by simulating a dnd-kit drag — which is precisely why `resolveDragIntent`
was extracted as a pure function ([dragGroup.ts:1](../../frontend/src/utils/dragGroup.ts)). Follow that
established pattern: extract the **merge-execution decision** into a pure helper and unit-test it.

### New pure helper in `dragGroup.ts`

```ts
/** Given a resolved group-merge (source group dropped on target) plus the source
 *  group's full membership, decide the payload for the durable mergeGroup call.
 *  Pure so it can be tested without a dnd-kit drag. */
export function resolveGroupMergePayload(
  source: DragCard,
  target: DragCard,
  memberIds: number[],
): { ids: number[]; groupId: number | null; label: string } {
  const label = target.variant_group?.label || target.character || target.title || target.name;
  const ids = target.variant_group_id
    ? memberIds
    : [...new Set([...memberIds, target.id])];
  return { ids, groupId: target.variant_group_id ?? null, label };
}
```

`confirmGroupMerge` then becomes a thin caller: fetch members (with `groupId`), call
`resolveGroupMergePayload`, hand off to `mergeIntoDurableGroup`. The `variants(..., variant_group_id)`
call stays; the test locks in that it is passed.

### Tests

**`dragGroup.test.ts`** (pure, no jsdom drag):
1. `resolveGroupMergePayload` — target is a durable group → `groupId` set, `ids` = members only (target
   already in the group), label from target group.
2. — target is a char-only group (no `variant_group_id`) → `groupId` null, target id folded into `ids`.
3. — members list spanning **different character values** is preserved intact (the #677 core: no member
   dropped because its `character` differs from the rep's).

**`Library.merge.test.tsx`** (new component test, mock `api.models`):
4. Assert `confirmGroupMerge` calls `api.models.variants` with the source group's `variant_group_id` as
   the third arg (locks in the #677/#686 fix — a revert to the 2-arg call fails this).
5. Assert it then calls `api.models.mergeGroup` with the full member id set, not a subset.

   Driving the confirm modal without a real drag: the modal renders from `pendingGroupMerge` state. Either
   (a) expose a tiny test seam to open it, or (b) trigger via the keyboard drag path already covered in
   `VariantGroup.keyboard.test.tsx`'s harness style. Prefer (a) minimal seam if (b) is too heavy — decide
   during implementation.

If the component test proves too costly for the value, the pure-helper tests (1–3) alone still lock in
the membership logic; test 4–5 are the belt-and-suspenders on the wiring.

## Files

- **`frontend/src/utils/dragGroup.ts`** — add `resolveGroupMergePayload` pure helper; `DragCard` may need
  `id`/`variant_group_id`/`variant_group` fields it doesn't yet carry (confirm and extend the interface).
- **`frontend/src/pages/Library.tsx`** — refactor `confirmGroupMerge` to call the helper (behavior-neutral).
- **`frontend/src/utils/dragGroup.test.ts`** — tests 1–3.
- **`frontend/src/pages/Library.merge.test.tsx`** — tests 4–5 (new file).

## Risks

- **`DragCard` widening.** The helper needs `variant_group_id` / `variant_group.label` on the card type.
  `resolveDragIntent`'s existing `DragCard` is intentionally minimal; extend it without pulling in the full
  `Model` type, or the pure-helper boundary erodes.
- **Behavior-neutral refactor.** Extracting the payload logic must not change what `confirmGroupMerge`
  sends. The component test (4–5) guards this; run it before and confirm identical calls.
- **Scope creep into #678.** Resist routing the `prompt`/`apply-char` paths through durable merge here —
  that's the deferred decision above.

## Out-of-scope (explicitly)

- #678 — converging the character and durable grouping systems (the two ⚠️ residual paths).
- Backend changes — none needed; `variants` already accepts `group_id` (#665) and `mergeGroup` exists.

## Sequencing

1. Extend `DragCard`; add `resolveGroupMergePayload` pure helper.
2. Refactor `confirmGroupMerge` to use it (behavior-neutral).
3. Tests 1–3 (pure) + 4–5 (component wiring).
4. `tsc --noEmit`, `vitest run`, PR, request review, arm auto-merge per your call.
