import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClientProvider } from "@tanstack/react-query";
import { MoleculeDetail } from "./molecule-detail";
import { calculateResponsiveLayout, calculateResponsiveColumns } from "@/lib/responsive-columns";
import type { MoleculeResponse } from "@/types/run";
import { ViewerPreferencesProvider } from "@/context/viewer-preferences-context";
import { ThemeProvider } from "@/context/theme-context";
import { createQueryClient } from "@/state/query-client";
import type { LayoutItem } from "react-grid-layout";

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock("@/api/molecules", () => ({
  getMolecule: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    to,
    search,
  }: {
    readonly children: React.ReactNode;
    readonly to?: string;
    readonly search?: Record<string, string | undefined>;
  }) => {
    const basePath = to ?? "/";
    const params = new URLSearchParams();
    Object.entries(search ?? {}).forEach(([key, value]) => {
      if (value != null) params.set(key, value);
    });
    const query = params.toString();
    const href = query.length > 0 ? `${basePath}?${query}` : basePath;
    return <a href={href}>{children}</a>;
  },
}));

vi.mock("3dmol", () => ({
  default: {
    createViewer: vi.fn(() => ({
      addModel: vi.fn(),
      setStyle: vi.fn(),
      zoomTo: vi.fn(),
      render: vi.fn(),
      clear: vi.fn(),
    })),
  },
}));

vi.mock("react-resizable-panels", () => ({
  Group: ({ children }: { readonly children: React.ReactNode }) => <div>{children}</div>,
  Panel: ({ children }: { readonly children: React.ReactNode }) => <div>{children}</div>,
  Separator: () => <hr />,
}));

import * as api from "@/api/molecules";

function Wrapper({ children }: { readonly children: React.ReactNode }) {
  const queryClient = createQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

function renderWithProviders(ui: React.ReactElement) {
  return render(ui, { wrapper: Wrapper });
}

function verifyLayoutBounds(layout: LayoutItem[], gridCols: number): void {
  for (const item of layout) {
    const x = item.x ?? 0;
    const w = item.w ?? 1;
    const rightEdge = x + w;

    if (x < 0) {
      throw new Error(`Item ${item.i} has invalid x position: ${x} (must be >= 0)`);
    }

    if (rightEdge > gridCols) {
      throw new Error(
        `Item ${item.i} extends beyond grid bounds: x=${x}, w=${w}, gridCols=${gridCols} ` +
          `(right edge ${rightEdge} > ${gridCols})`,
      );
    }
  }
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

const MOLECULE_ID = "a1b2c3d4-0000-0000-0000-000000000001";

const mockH2: MoleculeResponse = {
  id: MOLECULE_ID,
  name: "H2",
  atoms: [
    { symbol: "H", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0, z: 0.74 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2025-06-01T00:00:00Z",
  updated_at: "2025-06-01T00:00:00Z",
  pubchem_cid: 783,
  iupac_name: "molecular hydrogen",
  description: "Hydrogen is the lightest element.",
  synonyms: ["H2", "dihydrogen"],
  smiles: "[HH]",
  inchi: "InChI=1S/H2/h1H",
  inchi_key: "UFHFLCQGNIYNRP-UHFFFAOYSA-N",
};

const mockWater: MoleculeResponse = {
  id: "a1b2c3d4-0000-0000-0000-000000000002",
  name: "Water",
  atoms: [
    { symbol: "O", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0.757, y: 0.586, z: 0 },
    { symbol: "H", x: -0.757, y: 0.586, z: 0 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: { n_electrons: 8, n_orbitals: 6 },
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-05-02T00:00:00Z",
  pubchem_cid: 962,
  iupac_name: "oxidane",
  description: "Water is a polar inorganic compound.",
  synonyms: ["water", "H2O"],
  smiles: "O",
  inchi: "InChI=1S/H2O/h1H2",
  inchi_key: "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
};

beforeEach(() => {
  vi.clearAllMocks();
  (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockH2);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("MoleculeDetail — loading state", () => {
  it("shows skeleton while loading", () => {
    (api.getMolecule as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    expect(screen.getByLabelText("Loading molecule details")).toBeInTheDocument();
  });
});

describe("MoleculeDetail — error state", () => {
  it("shows error message when API fails", async () => {
    (api.getMolecule as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Not found"));
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/not found/i)).toBeInTheDocument();
    });
  });
});

describe("MoleculeDetail — loaded state", () => {
  it("renders molecule name as heading", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "H2" })).toBeInTheDocument();
    });
  });

  it("renders the Properties card", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Properties")).toBeInTheDocument();
    });
  });

  it("shows charge as Neutral for zero charge", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Neutral (0)")).toBeInTheDocument();
    });
  });

  it("renders the atoms coordinates table", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("table", { name: /atom coordinates/i })).toBeInTheDocument();
    });
  });

  it("shows each atom symbol in table", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getAllByText("H").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows CID badge when pubchem_cid is set", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("CID 783")).toBeInTheDocument();
    });
  });

  it("renders View on PubChem link when pubchem_cid is set", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      const link = screen.getByTestId("pubchem-link");
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", "https://pubchem.ncbi.nlm.nih.gov/compound/783");
    });
  });

  it("links to a new run with the current molecule preselected", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /new run/i });
      expect(link).toHaveAttribute("href", `/runs/new?molecule_id=${MOLECULE_ID}`);
    });
  });

  it("renders Description panel with PubChem description", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getAllByText("Description").length).toBeGreaterThan(0);
      expect(screen.getByText(/hydrogen is the lightest/i)).toBeInTheDocument();
    });
  });

  it("renders Identifiers panel with SMILES", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Identifiers")).toBeInTheDocument();
      expect(screen.getByText("[HH]")).toBeInTheDocument();
    });
  });
});

describe("MoleculeDetail — active space", () => {
  it("does not show active-space rows when active_space is null", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.queryByText("Electrons")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /expand active space fullscreen/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("renders active-space details inside Properties when active_space is present", async () => {
    (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockWater);
    renderWithProviders(<MoleculeDetail moleculeId={mockWater.id} />);
    await waitFor(() => {
      expect(screen.getByText("Properties")).toBeInTheDocument();
      expect(screen.getByText("Active Space")).toBeInTheDocument();
      expect(screen.getByText("Electrons")).toBeInTheDocument();
      expect(screen.getByText("Orbitals")).toBeInTheDocument();
      expect(screen.getByText("8")).toBeInTheDocument();
      expect(screen.getByText("6")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /expand active space fullscreen/i }),
      ).not.toBeInTheDocument();
    });
  });
});

describe("MoleculeDetail — responsive layout", () => {
  it("calculates 1 column for mobile (< 640px)", () => {
    expect(calculateResponsiveColumns(375)).toBe(1);
    expect(calculateResponsiveColumns(320)).toBe(1);
    expect(calculateResponsiveColumns(639)).toBe(1);
  });

  it("calculates 6 columns for small tablet (640px-799px)", () => {
    expect(calculateResponsiveColumns(640)).toBe(6);
    expect(calculateResponsiveColumns(768)).toBe(6);
    expect(calculateResponsiveColumns(799)).toBe(6);
  });

  it("calculates 8 columns for tablet (800px-1023px)", () => {
    expect(calculateResponsiveColumns(800)).toBe(8);
    expect(calculateResponsiveColumns(900)).toBe(8);
    expect(calculateResponsiveColumns(1023)).toBe(8);
  });

  it("calculates 12 columns for desktop (>= 1024px)", () => {
    expect(calculateResponsiveColumns(1024)).toBe(12);
    expect(calculateResponsiveColumns(1280)).toBe(12);
    expect(calculateResponsiveColumns(1920)).toBe(12);
  });

  it("generates mobile layout (1 column) for containerWidth < 640px", () => {
    const layout = calculateResponsiveLayout(375);

    expect(layout).toHaveLength(5); // viewer, properties, description, identifiers, atoms
    const firstLayoutItem = layout[0];
    if (!firstLayoutItem) {
      throw new Error("Expected the molecule viewer layout item");
    }
    expect(firstLayoutItem.i).toBe("viewer");
    expect(layout[0]).toEqual({ i: "viewer", x: 0, y: 0, w: 1, h: 7, minW: 1, minH: 4 });
    expect(layout[1]).toEqual({ i: "properties", x: 0, y: 7, w: 1, h: 5, minW: 1, minH: 3 });
    expect(layout[2]).toEqual({ i: "description", x: 0, y: 12, w: 1, h: 5, minW: 1, minH: 3 });
    expect(layout[3]).toEqual({ i: "identifiers", x: 0, y: 17, w: 1, h: 5, minW: 1, minH: 3 });
    expect(layout[4]).toEqual({ i: "atoms", x: 0, y: 22, w: 1, h: 5, minW: 1, minH: 3 });
  });

  it("generates small-tablet layout (6 columns) for containerWidth 640px-799px", () => {
    const layout = calculateResponsiveLayout(768);

    expect(layout).toHaveLength(5);
    expect(layout[0]).toEqual({ i: "viewer", x: 0, y: 0, w: 6, h: 7, minW: 3, minH: 4 });
    expect(layout[1]).toEqual({ i: "properties", x: 0, y: 7, w: 3, h: 5, minW: 2, minH: 3 });
    expect(layout[2]).toEqual({ i: "description", x: 3, y: 7, w: 3, h: 5, minW: 2, minH: 3 });
    expect(layout[3]).toEqual({ i: "identifiers", x: 0, y: 12, w: 3, h: 5, minW: 2, minH: 3 });
    expect(layout[4]).toEqual({ i: "atoms", x: 3, y: 12, w: 3, h: 5, minW: 2, minH: 3 });
  });

  it("generates tablet layout (8 columns) for containerWidth 800px-1023px", () => {
    const layout = calculateResponsiveLayout(900);

    expect(layout).toHaveLength(5);
    expect(layout[0]).toEqual({ i: "viewer", x: 0, y: 0, w: 8, h: 7, minW: 4, minH: 4 });
    expect(layout[1]).toEqual({ i: "properties", x: 0, y: 7, w: 4, h: 5, minW: 2, minH: 3 });
    expect(layout[2]).toEqual({ i: "description", x: 4, y: 7, w: 4, h: 5, minW: 2, minH: 3 });
    expect(layout[3]).toEqual({ i: "identifiers", x: 0, y: 12, w: 4, h: 5, minW: 2, minH: 3 });
    expect(layout[4]).toEqual({ i: "atoms", x: 4, y: 12, w: 4, h: 5, minW: 2, minH: 3 });
  });

  it("generates desktop layout (12 columns) for containerWidth >= 1024px", () => {
    const layout = calculateResponsiveLayout(1280);

    expect(layout).toHaveLength(5);
    expect(layout[0]).toEqual({ i: "viewer", x: 0, y: 0, w: 8, h: 7, minW: 3, minH: 4 });
    expect(layout[1]).toEqual({ i: "properties", x: 8, y: 0, w: 4, h: 7, minW: 2, minH: 3 });
    expect(layout[2]).toEqual({ i: "description", x: 0, y: 7, w: 4, h: 5, minW: 2, minH: 3 });
    expect(layout[3]).toEqual({ i: "identifiers", x: 4, y: 7, w: 4, h: 5, minW: 2, minH: 3 });
    expect(layout[4]).toEqual({ i: "atoms", x: 8, y: 7, w: 4, h: 5, minW: 2, minH: 3 });
  });

  it("verifies all items fit within grid bounds for mobile (1 column)", () => {
    const layout = calculateResponsiveLayout(375);
    expect(() => verifyLayoutBounds(layout, 1)).not.toThrow();
  });

  it("verifies all items fit within grid bounds for small tablet (6 columns)", () => {
    const layout = calculateResponsiveLayout(768);
    expect(() => verifyLayoutBounds(layout, 6)).not.toThrow();
  });

  it("verifies all items fit within grid bounds for tablet (8 columns)", () => {
    const layout = calculateResponsiveLayout(900);
    expect(() => verifyLayoutBounds(layout, 8)).not.toThrow();
  });

  it("verifies all items fit within grid bounds for desktop (12 columns)", () => {
    const layout = calculateResponsiveLayout(1280);
    expect(() => verifyLayoutBounds(layout, 12)).not.toThrow();
  });

  it("renders correctly on mobile viewport", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Properties")).toBeInTheDocument();
    });
    expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
  });

  it("renders correctly on tablet viewport", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Properties")).toBeInTheDocument();
    });
    expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
  });

  it("renders correctly on desktop viewport", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByText("Properties")).toBeInTheDocument();
    });
    expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
  });
});

describe("MoleculeDetail — viewer controls", () => {
  it("renders bond toggle button", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /bonds/i })).toBeInTheDocument();
    });
  });

  it("toggles bond display when bond button is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => screen.getByRole("button", { name: /hide bonds/i }));

    const bondBtn = screen.getByRole("button", { name: /hide bonds/i });
    await user.click(bondBtn);
    expect(screen.getByRole("button", { name: /show bonds/i })).toBeInTheDocument();
  });

  it("renders viewer style select", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /viewer style/i })).toBeInTheDocument();
    });
  });

  it("renders expand button", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      const buttons = screen.queryAllByRole("button", { name: /expand/i });
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it("opens expand dialog when expand button clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);

    await waitFor(() => {
      const buttons = screen.queryAllByRole("button", { name: /expand/i });
      expect(buttons.length).toBeGreaterThan(0);
    });

    const expandButtons = screen.getAllByRole("button", { name: /expand/i });
    const firstExpandButton = expandButtons[0];
    if (!firstExpandButton) {
      throw new Error("Expected an expand button");
    }
    await user.click(firstExpandButton);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("renders image download button in the viewer card", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /download 3d structure image/i }),
      ).toBeInTheDocument();
    });
  });

  it("renders XYZ download button in the atom coordinates card", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /download xyz coordinates/i })).toBeInTheDocument();
    });
  });

  it("renders Reset Layout button in the header", async () => {
    const user = userEvent.setup();
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /edit layout/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /edit layout/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reset layout/i })).toBeInTheDocument();
    });
  });

  it("renders Reset Camera button when in 3D mode", async () => {
    renderWithProviders(<MoleculeDetail moleculeId={MOLECULE_ID} />);
    await waitFor(() => {
      const resetButtons = screen.queryAllByRole("button", { name: /reset/i });
      const resetCameraBtn = resetButtons.find((btn) =>
        btn.getAttribute("aria-label")?.includes("camera"),
      );
      expect(resetCameraBtn).toBeTruthy();
    });
  });
});
