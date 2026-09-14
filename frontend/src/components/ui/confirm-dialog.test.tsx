import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ConfirmDialog } from "./confirm-dialog";

describe("ConfirmDialog", () => {
  it("shows spinner feedback while loading", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Delete"
        description="Are you sure?"
        confirmText="Delete"
        onConfirm={vi.fn()}
        loading
      />,
    );

    const confirmButton = screen.getByRole("button", { name: /delete/i });

    expect(confirmButton).toBeDisabled();
    expect(confirmButton.className).toContain("shadow-[var(--shadow-button-primary)]");
    expect(confirmButton.querySelector("[data-slot='spinner']")).toBeInTheDocument();
  });

  it("shows spinner while async confirmation is running", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn(() => new Promise<void>(() => {}));

    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Delete"
        confirmText="Delete"
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: /delete/i }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(document.querySelector("[data-slot='spinner']")).toBeInTheDocument();
  });

  it("renders a live status line when provided", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Delete"
        status="Deleting 3 of 8..."
        confirmText="Delete"
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Deleting 3 of 8...");
  });

  it("uses responsive action sizing so long button labels do not overflow narrow dialogs", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Submit benchmark to IBM Quantum?"
        confirmText="Submit to IBM backend"
        cancelText="Review benchmark"
        onConfirm={vi.fn()}
      />,
    );

    const reviewButton = screen.getByRole("button", { name: /review benchmark/i });
    const submitButton = screen.getByRole("button", { name: /submit to ibm backend/i });
    const actions = reviewButton.parentElement;

    expect(actions?.className).toContain("sm:grid-cols-2");
    expect(reviewButton.className).toContain("w-full");
    expect(reviewButton.className).toContain("whitespace-normal");
    expect(submitButton.className).toContain("w-full");
    expect(submitButton.className).toContain("whitespace-normal");
  });
});
