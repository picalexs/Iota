import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ConvergenceInsight } from "@/lib/results/convergence-status";
import { ConvergenceStatusIndicator } from "./convergence-status-indicator";

vi.mock("@/components/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({
    children,
    align,
    collisionPadding,
    className,
  }: {
    children: React.ReactNode;
    align?: string;
    collisionPadding?: number;
    className?: string;
  }) => (
    <div
      data-testid="tooltip-content"
      data-align={align}
      data-collision-padding={collisionPadding}
      className={className}
    >
      {children}
    </div>
  ),
}));

describe("ConvergenceStatusIndicator", () => {
  it("anchors long insight tooltips inward with viewport padding", () => {
    const insight: ConvergenceInsight = {
      label: "Convergence check",
      value: "The final residual gate is evaluated at the projected solve.",
      helper: "Selected 1 / 12",
      tone: "muted",
    };

    render(
      <ConvergenceStatusIndicator result={null} status="RUNNING" isRunning insight={insight} />,
    );

    expect(screen.getByRole("button", { name: "Convergence status details" })).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();

    const tooltip = screen.getByTestId("tooltip-content");
    expect(tooltip).toHaveAttribute("data-align", "start");
    expect(tooltip).toHaveAttribute("data-collision-padding", "16");
    expect(tooltip.className).toContain("max-w-[min(24rem,calc(100vw-2rem))]");
  });
});
