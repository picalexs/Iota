import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useChartTheme } from "./use-chart-theme";

function ThemeProbe() {
  const theme = useChartTheme();
  return <output data-testid="chart-theme">{theme.chart1}</output>;
}

describe("useChartTheme", () => {
  const root = document.documentElement;
  let previousClassName = "";
  let previousStyle = "";

  beforeEach(() => {
    previousClassName = root.className;
    previousStyle = root.getAttribute("style") ?? "";
    root.className = "";
    root.removeAttribute("style");
  });

  afterEach(() => {
    cleanup();
    act(() => {
      root.className = previousClassName;
      if (previousStyle.length > 0) {
        root.setAttribute("style", previousStyle);
      } else {
        root.removeAttribute("style");
      }
    });
  });

  it("refreshes chart colors when the root theme variables change", async () => {
    act(() => {
      root.style.setProperty("--chart-1", "#112233");
    });

    render(<ThemeProbe />);
    expect(screen.getByTestId("chart-theme")).toHaveTextContent("#112233");

    act(() => {
      root.classList.add("dark");
      root.style.setProperty("--chart-1", "#ddeeff");
    });

    await waitFor(() => {
      expect(screen.getByTestId("chart-theme")).toHaveTextContent("#ddeeff");
    });
  });
});
