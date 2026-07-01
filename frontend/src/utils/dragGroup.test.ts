import { describe, it, expect } from "vitest";
import { resolveDragIntent, resolveGroupMergePayload, type DragCard } from "./dragGroup";

const cards: Record<number, DragCard> = {
  1: { id: 1, creator_id: 10, name: "Goblin A", title: "Goblin A" },
  2: { id: 2, creator_id: 10, name: "Goblin B", title: "Goblin B" },
  3: { id: 3, creator_id: 10, name: "Goblin", title: "Goblin", character: "Goblin", variant_count: 4 },
  4: { id: 4, creator_id: 99, name: "Other-creator model" },
  5: { id: 5, creator_id: 10, name: "Orc", title: "Orc", character: "Orc", variant_count: 2 },
};
const byId = (id: number) => cards[id];
const sel = (...ids: number[]) => new Set(ids);

describe("resolveDragIntent", () => {
  it("no-ops on self-drop or unknown cards", () => {
    expect(resolveDragIntent(1, 1, byId, sel()).kind).toBe("none");
    expect(resolveDragIntent(1, 404, byId, sel()).kind).toBe("none");
  });

  it("single drag onto an ungrouped target prompts with the target's name", () => {
    const intent = resolveDragIntent(1, 2, byId, sel());
    expect(intent).toEqual({
      kind: "prompt",
      sourceIds: [1],
      targetId: 2,
      suggestedName: "Goblin B",
      skipped: 0,
    });
  });

  it("single drag onto an existing group applies that group's character", () => {
    const intent = resolveDragIntent(1, 3, byId, sel());
    expect(intent).toEqual({ kind: "apply", sourceIds: [1], character: "Goblin", skipped: 0 });
  });

  it("#137 — dragging a selected card moves the whole selection", () => {
    const intent = resolveDragIntent(1, 3, byId, sel(1, 2));
    expect(intent).toEqual({ kind: "apply", sourceIds: [1, 2], character: "Goblin", skipped: 0 });
  });

  it("#137 — a non-selected drag ignores the selection and moves only itself", () => {
    const intent = resolveDragIntent(1, 3, byId, sel(2, 5));
    expect(intent).toMatchObject({ kind: "apply", sourceIds: [1] });
  });

  it("#137 — cross-creator members in the selection are skipped, not moved", () => {
    const intent = resolveDragIntent(1, 3, byId, sel(1, 2, 4));
    expect(intent).toEqual({ kind: "apply", sourceIds: [1, 2], character: "Goblin", skipped: 1 });
  });

  it("errors when a single drop crosses creators", () => {
    const intent = resolveDragIntent(4, 1, byId, sel());
    expect(intent.kind).toBe("error");
  });

  it("#136 — dragging a group defers to a confirm step", () => {
    const intent = resolveDragIntent(3, 1, byId, sel());
    expect(intent).toEqual({ kind: "group-merge", sourceId: 3, targetId: 1 });
  });

  it("#136 — group merge across creators is rejected", () => {
    const cross: Record<number, DragCard> = {
      ...cards,
      6: { id: 6, creator_id: 10, name: "x", character: "x", variant_count: 3 },
    };
    const intent = resolveDragIntent(6, 4, (id) => cross[id], sel());
    expect(intent.kind).toBe("error");
  });
});

describe("resolveGroupMergePayload (#677)", () => {
  it("targets a durable group: memberIds alone is the full set, groupId/label from target", () => {
    const target: DragCard = {
      id: 20, creator_id: 10, name: "Boss", variant_group_id: 7,
      variant_group: { label: "Boss Fight" },
    };
    const payload = resolveGroupMergePayload(target, [1, 2, 3]);
    expect(payload).toEqual({ ids: [1, 2, 3], groupId: 7, label: "Boss Fight" });
  });

  it("targets a character-only group: target id is folded into the member set, groupId is null", () => {
    const target: DragCard = { id: 20, creator_id: 10, name: "Goblin", character: "Goblin" };
    const payload = resolveGroupMergePayload(target, [1, 2]);
    expect(payload).toEqual({ ids: [1, 2, 20], groupId: null, label: "Goblin" });
  });

  it("targets an ungrouped model: falls back to title, then name, for the label", () => {
    const noCharacter: DragCard = { id: 20, creator_id: 10, name: "Raw Name", title: "Nice Title" };
    expect(resolveGroupMergePayload(noCharacter, [1])).toEqual({
      ids: [1, 20], groupId: null, label: "Nice Title",
    });

    const noTitleEither: DragCard = { id: 21, creator_id: 10, name: "Raw Name" };
    expect(resolveGroupMergePayload(noTitleEither, [1])).toEqual({
      ids: [1, 21], groupId: null, label: "Raw Name",
    });
  });

  it("preserves a member list spanning different character values intact — the #677 core bug", () => {
    // Members were resolved via the group_id-aware /models/variants call, so this
    // list may include ids whose own `character` differs from the target's. The
    // payload must not filter or drop any of them.
    const target: DragCard = {
      id: 20, creator_id: 10, name: "Group", variant_group_id: 9,
      variant_group: { label: "Mixed Group" },
    };
    const memberIds = [1, 2, 3, 4, 5]; // some of these belong to a different `character` than the rep
    const payload = resolveGroupMergePayload(target, memberIds);
    expect(payload.ids).toEqual(memberIds);
    expect(payload.ids).toHaveLength(5);
  });

  it("de-dupes if the target id is somehow already present in memberIds", () => {
    const target: DragCard = { id: 20, creator_id: 10, name: "Goblin", character: "Goblin" };
    const payload = resolveGroupMergePayload(target, [1, 20]);
    expect(payload.ids).toEqual([1, 20]);
  });
});
