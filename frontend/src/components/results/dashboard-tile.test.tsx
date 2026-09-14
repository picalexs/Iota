import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DashboardTile } from "./dashboard-tile";

vi.mock("@/components/ui/fullscreen-panel", () => ({
  FullscreenPanel: () => null,
}));

describe("DashboardTile", () => {
  it("uses the sidebar surface styling for movable dashboard panels", () => {
    render(<DashboardTile title="Summary">Tile body</DashboardTile>);

    const tile = screen.getByText("Tile body").closest("[data-dashboard-tile]");
    const expandButton = screen.getByRole("button", { name: /expand summary fullscreen/i });

    expect(tile?.className).toContain("bg-sidebar");
    expect(tile?.className).toContain("border-sidebar-border/85");
    expect(tile?.className).toContain("shadow-[var(--shadow-surface-panel)]");
    expect(expandButton.className).toContain("hover:bg-sidebar-accent");
  });
});
