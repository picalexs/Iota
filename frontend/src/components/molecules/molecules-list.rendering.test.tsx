import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMoleculeSummary,
  hooks,
  renderWithQuery,
  resetMoleculesListMocks,
} from "./molecules-list.test-utils";

beforeEach(resetMoleculesListMocks);

describe("MoleculesList row rendering", () => {
  it("uses fixed grid tracks and truncation metadata for long row content", async () => {
    const longName = "MoleculeWithVeryVeryLongNameForTruncation";
    const response = {
      items: [createMoleculeSummary({ name: longName, formula: "C2H2ClFNOSi" })],
      total: 1,
    };

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: response,
    });

    renderWithQuery();

    const row = await screen.findByRole("link", { name: longName });
    expect(row.className).toContain("grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px]");

    const cells = within(row).getAllByText(/.+/);
    expect(cells).toHaveLength(3);
    expect(cells[0]).toHaveClass("truncate");
    expect(cells[0]).toHaveAttribute("title");
  });

  it("keeps the library table focused on molecule identity instead of algorithm tags", async () => {
    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        items: [createMoleculeSummary({ name: "Nitrogen", formula: "N2", atom_count: 2 })],
        total: 1,
      },
    });

    renderWithQuery();

    await screen.findByRole("link", { name: "Nitrogen" });
    expect(screen.queryByRole("columnheader", { name: "Status" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /filter by charge/i })).not.toBeInTheDocument();
    expect(screen.queryByText("VQE")).not.toBeInTheDocument();
    expect(screen.queryByText("Large active space")).not.toBeInTheDocument();
  });

  // Performance: Verify rows render without staggered entrance animations
  it("molecule list rows render immediately without entrance animation delays", async () => {
    const molecules = [
      createMoleculeSummary({ id: "mol-1", name: "H2" }),
      createMoleculeSummary({ id: "mol-2", name: "H2O", formula: "H2O", atom_count: 3 }),
      createMoleculeSummary({ id: "mol-3", name: "CO2", formula: "CO2", atom_count: 3 }),
      createMoleculeSummary({ id: "mol-4", name: "NH3", formula: "H3N", atom_count: 4 }),
      createMoleculeSummary({ id: "mol-5", name: "CH4", formula: "CH4", atom_count: 5 }),
    ];

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        items: molecules,
        total: 5,
      },
    });

    const { container } = renderWithQuery();

    // Wait for molecule rows to be present
    await waitFor(() => {
      const rows = container.querySelectorAll("a[aria-label]");
      expect(rows.length).toBe(molecules.length);
    });

    // Find all molecule rows
    const rows = container.querySelectorAll("a[aria-label]");
    expect(rows.length).toBe(molecules.length);

    // Verify rows do NOT have staggered animation delays
    rows.forEach((row) => {
      // Should not have the staggered entrance animation classes
      expect(row.className).not.toContain("animate-in");
      expect(row.className).not.toContain("fade-in-0");
      expect(row.className).not.toContain("slide-in-from-bottom-2");
    });
  });

  it("large molecule lists render all rows immediately without cascading delays", async () => {
    const molecules = Array.from({ length: 15 }, (_, i) =>
      createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
    );

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        items: molecules,
        total: 15,
      },
    });

    const { container } = renderWithQuery();

    // Wait for all molecule rows to be present
    await waitFor(() => {
      const rows = container.querySelectorAll("a[aria-label]");
      expect(rows.length).toBe(15);
    });

    const rows = container.querySelectorAll("a[aria-label]");
    expect(rows.length).toBe(15);

    // Verify no row has staggered animation delays
    rows.forEach((row) => {
      expect(row.className).not.toContain("animate-in");
    });
  });
});
