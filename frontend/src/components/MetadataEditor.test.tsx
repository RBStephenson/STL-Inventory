import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import MetadataEditor from "./MetadataEditor";

vi.mock("../api/client", () => ({
  api: {
    models: {
      tags: vi.fn(async () => []),
      update: vi.fn(async () => ({ ok: true })),
    },
    scrape: { fetchUrl: vi.fn() },
  },
}));
vi.mock("../context/ToastContext", () => ({ useToast: () => ({ toast: vi.fn() }) }));

// Minimal ModelDetail stand-in — only the fields the editor reads.
const baseModel = {
  id: 5,
  title: "RoboCop",
  description: "",
  notes: "",
  source_url: "",
  source_site: "",
  license: "",
  category: "",
  creator: { name: "CA3D" },
  tags: ["figure"],          // stale server snapshot
  auto_tags: ["statue"],
  nsfw: false,
  thumbnail_url: "",
} as unknown as Parameters<typeof MetadataEditor>[0]["model"];

const renderEditor = (currentTags?: string[]) =>
  render(
    <MetadataEditor
      model={baseModel}
      currentTags={currentTags}
      onSaved={vi.fn()}
      onCancel={vi.fn()}
    />
  );

describe("MetadataEditor tag initialization (#299)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("initializes tags from currentTags when provided, not the stale model.tags", () => {
    // Parent promoted "statue" via the + button before the model was refetched.
    renderEditor(["figure", "statue"]);
    expect(screen.getByText("figure")).toBeInTheDocument();
    expect(screen.getByText("statue")).toBeInTheDocument();
  });

  it("falls back to model.tags when currentTags is not supplied", () => {
    renderEditor(undefined);
    expect(screen.getByText("figure")).toBeInTheDocument();
    expect(screen.queryByText("statue")).not.toBeInTheDocument();
  });
});
