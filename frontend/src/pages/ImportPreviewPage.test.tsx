import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ImportPreviewPage from "./ImportPreviewPage";

vi.mock("../api/client", () => ({
  api: {
    import: {
      sourceContents: vi.fn(),
      libraries: vi.fn(),
      getMapping: vi.fn(),
      setMapping: vi.fn().mockResolvedValue({ source_path: "/src", library_id: 1 }),
      preview: vi.fn(),
      scanFolder: vi.fn().mockResolvedValue({ running: true, message: "importing" }),
    },
    scan: {
      libraries: vi.fn(),
      status: vi.fn().mockResolvedValue({ running: false, message: "done" }),
    },
    models: {
      bulkEnrich: vi.fn().mockResolvedValue({ ok: true, updated: 2 }),
      bulkTag: vi.fn().mockResolvedValue({ ok: true, updated: 2 }),
    },
  },
}));

const toastMock = vi.fn();
vi.mock("../context/ToastContext", () => ({ useToast: () => ({ toast: toastMock }) }));

import { api } from "../api/client";

const PACK = {
  name: "PackA", source_path: "/src/PackA", file_count: 0, model_ids: [1, 2],
  creator_name: null, title: null, character: null, notes: null, source_url: null, tags: [],
};

function setup(opts: { mapping?: { source_path: string; library_id: number } | null } = {}) {
  vi.mocked(api.import.sourceContents).mockResolvedValue({
    source: "/src", is_flat: false,
    entries: [{ name: "PackA", path: "/src/PackA", already_imported: false }],
  });
  vi.mocked(api.scan.libraries).mockResolvedValue([
    { id: 1, path: "/lib", name: "minis", is_writable: true, write_enabled: false },
  ]);
  vi.mocked(api.import.getMapping).mockResolvedValue(opts.mapping ?? null);
  vi.mocked(api.import.preview).mockResolvedValue({ source: "/src", library_id: null, packs: [PACK] });

  return render(
    <MemoryRouter initialEntries={["/import/preview?source=/src"]}>
      <ImportPreviewPage />
    </MemoryRouter>
  );
}

describe("ImportPreviewPage (#452 C2)", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders a card per pack from source-contents", async () => {
    setup();
    expect(await screen.findByText("PackA")).toBeInTheDocument();
    expect(screen.getByText("/src/PackA")).toBeInTheDocument();
  });

  it("lists writable libraries in the destination dropdown", async () => {
    setup();
    await screen.findByText("PackA");
    expect(screen.getByRole("option", { name: "minis" })).toBeInTheDocument();
  });

  it("prefills the destination from the saved mapping", async () => {
    setup({ mapping: { source_path: "/src", library_id: 1 } });
    await screen.findByText("PackA");
    expect((screen.getByLabelText("Library") as HTMLSelectElement).value).toBe("1");
  });

  it("Import is disabled until a library is chosen", async () => {
    setup();
    await screen.findByText("PackA");
    expect(screen.getByRole("button", { name: /^import$/i })).toBeDisabled();
  });

  it("persists the mapping when a library is selected", async () => {
    setup();
    await screen.findByText("PackA");
    fireEvent.change(screen.getByLabelText("Library"), { target: { value: "1" } });
    await waitFor(() => expect(api.import.setMapping).toHaveBeenCalledWith("/src", 1));
  });

  it("imports a pack: scan, then enrich the ingested models", async () => {
    setup({ mapping: { source_path: "/src", library_id: 1 } });
    await screen.findByText("PackA");

    // Expand and set a creator so bulkEnrich receives a field.
    fireEvent.click(screen.getByLabelText("Expand"));
    fireEvent.change(await screen.findByPlaceholderText("Creator name"), { target: { value: "Hijos De Pulvo" } });

    fireEvent.click(screen.getByRole("button", { name: /^import$/i }));

    await waitFor(() => expect(api.import.scanFolder).toHaveBeenCalledWith("/src/PackA"));
    await waitFor(
      () => expect(api.models.bulkEnrich).toHaveBeenCalledWith([1, 2], { creator_name: "Hijos De Pulvo" }),
      { timeout: 5000 }
    );
    expect(await screen.findByText("Imported", {}, { timeout: 5000 })).toBeInTheDocument();
  });
});
