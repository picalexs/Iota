import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="COMPLETED" />);
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("maps COMPLETED to the success badge variant", () => {
    render(<StatusBadge status="COMPLETED" />);
    expect(screen.getByLabelText("Status: COMPLETED")).toHaveAttribute("data-variant", "success");
  });

  it("maps FAILED to the destructive badge variant", () => {
    render(<StatusBadge status="FAILED" />);
    expect(screen.getByLabelText("Status: FAILED")).toHaveAttribute("data-variant", "destructive");
  });

  it("renders timed out failures with a timeout label and warning variant", () => {
    render(
      <StatusBadge
        status="FAILED"
        metadata={{ error_type: "JobTimeoutException", timeout_seconds: 3600 }}
      />,
    );

    expect(screen.getByLabelText("Status: TIMED OUT")).toHaveAttribute("data-variant", "warning");
  });

  it("maps RUNNING to the warning badge variant without motion classes", () => {
    render(<StatusBadge status="RUNNING" />);
    const badge = screen.getByLabelText("Status: RUNNING");
    expect(badge).toHaveAttribute("data-variant", "warning");
    expect(badge.className).not.toContain("animate");
  });

  it("maps CANCELLED to a non-red info badge variant", () => {
    render(<StatusBadge status="CANCELLED" />);
    expect(screen.getByLabelText("Status: CANCELLED")).toHaveAttribute("data-variant", "info");
  });

  it("sets aria-label with status text", () => {
    render(<StatusBadge status="RUNNING" />);
    expect(screen.getByLabelText("Status: RUNNING")).toBeInTheDocument();
  });
});
