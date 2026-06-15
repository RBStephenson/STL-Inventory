import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GuideMetaForm from "./GuideMetaForm";

describe("GuideMetaForm", () => {
  it("requires a title before submitting", async () => {
    const onSubmit = vi.fn();
    render(<GuideMetaForm submitLabel="Create guide" onSubmit={onSubmit} onCancel={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Create guide" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/title is required/i)).toBeInTheDocument();
  });

  it("derives a slug from the title when left blank", async () => {
    const onSubmit = vi.fn();
    render(<GuideMetaForm submitLabel="Create guide" onSubmit={onSubmit} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Title *"), "RoboCop (1987)");
    await userEvent.click(screen.getByRole("button", { name: "Create guide" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ title: "RoboCop (1987)", slug: "robocop-1987" })
    );
  });

  it("collects tags, paint lines and creator credit; nulls blank fields", async () => {
    const onSubmit = vi.fn();
    render(<GuideMetaForm submitLabel="Create guide" onSubmit={onSubmit} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Title *"), "Geralt");
    await userEvent.type(screen.getByLabelText("Technique tags"), "wet-blend{enter}");
    await userEvent.type(screen.getByLabelText("Paint lines used"), "Pro Acryl{enter}");
    await userEvent.type(screen.getByLabelText("Name"), "Vince Venturella");
    await userEvent.click(screen.getByRole("button", { name: "Create guide" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        technique_tags: ["wet-blend"],
        paint_lines_used: [{ name: "Pro Acryl" }],
        creator_credit: { name: "Vince Venturella", url: null, link_text: null },
        subtitle: null,
      })
    );
  });

  it("hides the slug field and prefills values when editing", () => {
    render(
      <GuideMetaForm
        submitLabel="Save changes"
        lockSlug
        initial={{ title: "RoboCop", slug: "robocop", franchise: "RoboCop" }}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Title *")).toHaveValue("RoboCop");
    expect(screen.queryByLabelText("Slug")).toBeNull();
    expect(screen.getByLabelText("Franchise")).toHaveValue("RoboCop");
  });
});
