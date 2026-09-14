import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SelectableCard } from "./selectable-card";

describe("SelectableCard", () => {
  it("uses distinct hover and selected state tokens", () => {
    render(
      <>
        <SelectableCard>Idle</SelectableCard>
        <SelectableCard selected>Selected</SelectableCard>
      </>,
    );

    const idle = screen.getByRole("button", { name: "Idle" });
    const selected = screen.getByRole("button", { name: "Selected" });

    expect(idle).toHaveAttribute("data-selected", "false");
    expect(selected).toHaveAttribute("data-selected", "true");
    expect(idle.className).toContain("bg-surface-raised");
    expect(idle.className).toContain("hover:bg-interactive-hover");
    expect(idle.className).toContain("hover:border-interactive-hover-border");
    expect(idle.className).toContain("hover:shadow-[var(--shadow-interactive-hover)]");
    expect(idle.className).toContain("data-[selected=true]:bg-interactive-selected");
    expect(idle.className).toContain("data-[selected=true]:border-interactive-selected-border");
    expect(idle.className).toContain(
      "data-[selected=true]:shadow-[var(--shadow-interactive-selected)]",
    );
    expect(idle.className).toContain("focus-visible:ring-focus-strong");
    expect(idle.className).not.toContain("hover:-translate");
    expect(selected.className).toContain("data-[selected=true]:bg-interactive-selected");
  });
});
