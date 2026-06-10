import { describe, it, expect } from "vitest";
import { nextTagParams } from "./tagFilter";

describe("nextTagParams – tag chip tri-state cycle (#205)", () => {
  it("off → include", () => {
    expect(nextTagParams("statue", "", "")).toEqual({ tag: "statue", exclude_tag: "" });
  });

  it("include → exclude", () => {
    expect(nextTagParams("statue", "statue", "")).toEqual({ tag: "", exclude_tag: "statue" });
  });

  it("exclude → off", () => {
    expect(nextTagParams("statue", "", "statue")).toEqual({ tag: "", exclude_tag: "" });
  });

  it("clicking a different tag while one is included switches the include", () => {
    expect(nextTagParams("bust", "statue", "")).toEqual({ tag: "bust", exclude_tag: "" });
  });

  it("clicking a different tag while one is excluded switches to include and clears the exclude", () => {
    expect(nextTagParams("bust", "", "statue")).toEqual({ tag: "bust", exclude_tag: "" });
  });

  it("never returns both params set (mutual exclusion)", () => {
    for (const [active, excluded] of [["", ""], ["statue", ""], ["", "statue"], ["bust", ""], ["", "bust"]]) {
      const next = nextTagParams("statue", active, excluded);
      expect(next.tag && next.exclude_tag).toBeFalsy();
    }
  });
});
