import { describe, it, expect } from "vitest";
import { isRecentlyAdded } from "./recentlyAdded";

const NOW = new Date("2026-06-10T12:00:00Z");

describe("isRecentlyAdded (#170)", () => {
  it("true inside the window, false outside", () => {
    expect(isRecentlyAdded("2026-06-08T12:00:00", 7, NOW)).toBe(true);
    expect(isRecentlyAdded("2026-06-01T00:00:00", 7, NOW)).toBe(false);
  });

  it("boundary: exactly N days old is still new", () => {
    expect(isRecentlyAdded("2026-06-03T12:00:00", 7, NOW)).toBe(true);
    expect(isRecentlyAdded("2026-06-03T11:59:59", 7, NOW)).toBe(false);
  });

  it("treats naive timestamps as UTC and respects explicit zones", () => {
    // 8 days ago in UTC, but only ~6.7 days ago if misread as UTC+8 local time.
    expect(isRecentlyAdded("2026-06-02T11:00:00", 7, NOW)).toBe(false);
    expect(isRecentlyAdded("2026-06-08T12:00:00Z", 7, NOW)).toBe(true);
    expect(isRecentlyAdded("2026-06-08T14:00:00+02:00", 7, NOW)).toBe(true);
  });

  it("handles garbage input safely", () => {
    expect(isRecentlyAdded(null, 7, NOW)).toBe(false);
    expect(isRecentlyAdded(undefined, 7, NOW)).toBe(false);
    expect(isRecentlyAdded("not-a-date", 7, NOW)).toBe(false);
    expect(isRecentlyAdded("2026-06-08T12:00:00", 0, NOW)).toBe(false);
  });
});
