import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HelpParametersPage } from "./help-parameters-page";

describe("HelpParametersPage", () => {
  it("renders the glossary heading", () => {
    render(<HelpParametersPage />);

    expect(
      screen.getByRole("heading", { name: /run configuration glossary/i }),
    ).toBeInTheDocument();
  });

  it("renders the key anchor sections used by form help links", () => {
    render(<HelpParametersPage />);

    expect(document.getElementById("molecule")).toBeInTheDocument();
    expect(document.getElementById("algorithm")).toBeInTheDocument();
    expect(document.getElementById("basis_set")).toBeInTheDocument();
    expect(document.getElementById("chemical_accuracy_target_ha")).toBeInTheDocument();
    expect(document.getElementById("time_grid_type")).toBeInTheDocument();
  });
});
