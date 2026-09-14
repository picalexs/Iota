import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChartEmptyState } from "./chart-empty-state";

describe("ChartEmptyState", () => {
  it("renders an accessible pending placeholder with a spinner", () => {
    render(
      <ChartEmptyState message="No data recorded" pending pendingMessage="Awaiting chart data" />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Awaiting chart data");
  });

  it("keeps static empty states non-live", () => {
    render(<ChartEmptyState message="No data recorded" />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("No data recorded")).toBeInTheDocument();
  });
});
