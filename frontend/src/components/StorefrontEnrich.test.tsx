import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StorefrontEnrich from "./StorefrontEnrich";

const MATCH = {
  local_model_id: 1,
  local_name: "Dragon",
  local_folder: "/x/dragon",
  score: 0.9,
  confidence: "high",
  product: {
    title: "Dragon Deluxe",
    source_url: "https://www.myminifactory.com/object/dragon-1",
    source_site: "myminifactory",
    external_id: "1",
    thumbnail_url: null,
  },
};

function mockFetch(applyBody: object) {
  return vi.fn(async (url: string) => {
    if (url.includes("/enrich/storefront/match")) {
      return { ok: true, json: async () => [MATCH] } as Response;
    }
    if (url.includes("/enrich/storefront/apply")) {
      return { ok: true, json: async () => applyBody } as Response;
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
}

async function runAndApply() {
  await userEvent.type(
    screen.getByPlaceholderText(/myminifactory\.com\/users/i),
    "https://www.myminifactory.com/users/someone",
  );
  await userEvent.click(screen.getByRole("button", { name: /^Match$/ }));
  // High-confidence match auto-selects; apply it.
  await userEvent.click(await screen.findByRole("button", { name: /Apply 1 match/i }));
}

describe("StorefrontEnrich – apply result counts", () => {
  beforeEach(() => { vi.useRealTimers(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it("reports deep + shallow counts after apply", async () => {
    vi.stubGlobal("fetch", mockFetch({ ok: true, applied: 3, enriched_deep: 2, fallback_shallow: 1 }));
    render(<StorefrontEnrich creatorId={5} creatorName="Acme" onDone={() => {}} />);

    await runAndApply();

    const banner = await screen.findByText(/Applied to 3 models/i);
    expect(banner).toHaveTextContent("2 fully enriched");
    expect(banner).toHaveTextContent("1 basic");
    expect(banner).toHaveTextContent(/couldn't fetch full detail/i);
  });

  it("omits the shallow note when everything enriched deeply", async () => {
    vi.stubGlobal("fetch", mockFetch({ ok: true, applied: 1, enriched_deep: 1, fallback_shallow: 0 }));
    render(<StorefrontEnrich creatorId={5} creatorName="Acme" onDone={() => {}} />);

    await runAndApply();

    const banner = await screen.findByText(/Applied to 1 model/i);
    expect(banner).toHaveTextContent("1 fully enriched");
    expect(banner).not.toHaveTextContent("basic");
  });
});
