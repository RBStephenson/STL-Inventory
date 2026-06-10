import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Navbar from "./Navbar";
import { AppSettingsProvider } from "../context/AppSettingsContext";

vi.mock("../api/client", () => ({
  api: {
    models: {
      stats: vi.fn().mockResolvedValue({ needs_review: 0, queued: 0 }),
    },
    settings: {
      get: vi.fn().mockResolvedValue({ painting_guides_enabled: false }),
      update: vi.fn(),
    },
  },
}));

function renderNavbar() {
  return render(
    <MemoryRouter>
      <AppSettingsProvider>
        <Navbar />
      </AppSettingsProvider>
    </MemoryRouter>
  );
}

describe("Navbar – painting nav gating (#180/#181)", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("hides Guides and Paint Shelf when painting guides are disabled", async () => {
    const { api } = await import("../api/client");
    vi.mocked(api.settings.get).mockResolvedValue({ painting_guides_enabled: false });

    renderNavbar();

    // Wait for the settings fetch to settle, then assert absence.
    expect(await screen.findByText("Library")).toBeInTheDocument();
    expect(screen.queryByText("Guides")).toBeNull();
    expect(screen.queryByText("Paint Shelf")).toBeNull();
  });

  it("shows Guides and Paint Shelf when painting guides are enabled", async () => {
    const { api } = await import("../api/client");
    vi.mocked(api.settings.get).mockResolvedValue({ painting_guides_enabled: true });

    renderNavbar();

    expect(await screen.findByText("Guides")).toBeInTheDocument();
    expect(screen.getByText("Paint Shelf")).toBeInTheDocument();
    expect(screen.getByText("Guides").closest("a")).toHaveAttribute("href", "/painting/guides");
    expect(screen.getByText("Paint Shelf").closest("a")).toHaveAttribute("href", "/painting/shelf");
  });
});
