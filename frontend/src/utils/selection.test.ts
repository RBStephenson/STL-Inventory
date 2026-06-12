import { describe, it, expect } from "vitest";
import { nextSelection } from "./selection";

const ORDER = [10, 20, 30, 40, 50];

describe("nextSelection (#164)", () => {
  it("adds a single id on a plain click", () => {
    const result = nextSelection(new Set(), ORDER, null, 30, false);
    expect([...result]).toEqual([30]);
  });

  it("removes an already-selected id on a plain click (toggle off)", () => {
    const result = nextSelection(new Set([30]), ORDER, 30, 30, false);
    expect(result.has(30)).toBe(false);
  });

  it("selects an inclusive forward range on shift-click from the anchor", () => {
    const result = nextSelection(new Set([20]), ORDER, 20, 40, true);
    expect([...result].sort((a, b) => a - b)).toEqual([20, 30, 40]);
  });

  it("selects a backward range regardless of click direction", () => {
    const result = nextSelection(new Set([40]), ORDER, 40, 10, true);
    expect([...result].sort((a, b) => a - b)).toEqual([10, 20, 30, 40]);
  });

  it("merges a shift-range into an existing selection", () => {
    const result = nextSelection(new Set([50]), ORDER, 10, 30, true);
    expect([...result].sort((a, b) => a - b)).toEqual([10, 20, 30, 50]);
  });

  it("falls back to a single toggle when shift-clicking with no anchor", () => {
    const result = nextSelection(new Set(), ORDER, null, 30, true);
    expect([...result]).toEqual([30]);
  });

  it("toggles a single id when the anchor equals the clicked id under shift", () => {
    const result = nextSelection(new Set(), ORDER, 30, 30, true);
    expect([...result]).toEqual([30]);
  });

  it("does not mutate the input set", () => {
    const prev = new Set([10]);
    nextSelection(prev, ORDER, null, 20, false);
    expect([...prev]).toEqual([10]);
  });
});
