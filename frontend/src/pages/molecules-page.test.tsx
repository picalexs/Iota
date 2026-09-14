import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MoleculesPage } from "./molecules-page";
import { clearListCache } from "@/state/list-cache";

vi.mock("../components/molecules/molecules-list", () => ({
  MoleculesList: () => <div data-testid="molecules-list-mock">Molecules List Mock</div>,
}));

describe("MoleculesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearListCache();
  });

  it("renders page heading and molecule list section", () => {
    render(<MoleculesPage />);

    expect(screen.getByRole("heading", { name: /Molecule Library/i })).toBeInTheDocument();

    expect(screen.getByLabelText("Molecules list")).toBeInTheDocument();

    expect(screen.getByTestId("molecules-list-mock")).toBeInTheDocument();
  });
});
