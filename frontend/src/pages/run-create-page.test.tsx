import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import { RunCreatePage } from "./run-create-page";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createQueryClient } from "@/state/query-client";
import type { MoleculeResponse } from "@/types/run";
import { ThemeProvider } from "@/context/theme-context";

// Mock API
vi.mock("@/api/molecules", () => ({
  fetchMolecules: vi.fn(),
  fetchBasisSets: vi.fn(),
}));

vi.mock("@/api/backends", () => ({
  fetchBackendCapabilities: vi.fn(),
  forceRefreshBackendCapabilities: vi.fn(),
  getBackendCapabilitiesCached: vi.fn(),
  startBackendCapabilitiesAutoRefresh: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  fetchRunConfigMetadata: vi.fn(),
  createRun: vi.fn(),
}));

vi.mock("@/api/http", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public code: string,
      message: string,
      public status: number,
      public field?: string,
    ) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import * as backendsApi from "@/api/backends";
import * as httpApi from "@/api/http";
import * as moleculesApi from "@/api/molecules";
import * as runsApi from "@/api/runs";

const api = { ...backendsApi, ...httpApi, ...moleculesApi, ...runsApi };

const mockMolecules: MoleculeResponse[] = [
  {
    id: "a1b2c3d4-0000-0000-0000-000000000001",
    name: "H2",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: null,
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
  },
];

function getMockMolecule() {
  const molecule = mockMolecules[0];
  if (!molecule) {
    throw new Error("Expected a mock molecule");
  }
  return molecule;
}

beforeEach(() => {
  vi.clearAllMocks();
  (api.fetchMolecules as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: mockMolecules,
    total: mockMolecules.length,
  });
  (api.fetchBasisSets as ReturnType<typeof vi.fn>).mockResolvedValue({
    default_basis_set: "sto-3g",
    basis_sets: [
      {
        id: "sto-3g",
        label: "STO-3G",
        description: "Minimal basis",
        family: "minimal",
        recommended: true,
        supported_elements: [],
      },
    ],
  });
  (api.fetchBackendCapabilities as ReturnType<typeof vi.fn>).mockResolvedValue({
    backends: [],
  });
  (api.forceRefreshBackendCapabilities as ReturnType<typeof vi.fn>).mockResolvedValue({
    backends: [],
  });
  (api.fetchRunConfigMetadata as ReturnType<typeof vi.fn>).mockResolvedValue({
    catalog_version: "2026-09-11-v21",
    algorithms: ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"],
    backend_targets: ["statevector", "aer_simulator", "ibm_runtime"],
    easy_goals: ["fastest", "balanced", "best_accuracy"],
    easy_goal_presets: [
      { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
      { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
      { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
    ],
    ansatzes: [],
    optimizers: [],
    defaults: {},
    limits: {},
    capabilities: {},
  });
  (api.getBackendCapabilitiesCached as ReturnType<typeof vi.fn>).mockReturnValue(null);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

function buildTestRouter(initialEntry = "/runs/new") {
  const rootRoute = createRootRoute();
  const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs",
    component: () => <div>Runs List</div>,
  });
  const newRunRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/new",
    validateSearch: (search: Record<string, unknown>): { molecule_id?: string } => ({
      molecule_id: typeof search.molecule_id === "string" ? search.molecule_id : undefined,
    }),
    component: RunCreatePage,
  });
  const routeTree = rootRoute.addChildren([runsRoute, newRunRoute]);
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  return createRouter({ routeTree, history });
}

describe("RunCreatePage", () => {
  function renderPage(initialEntry?: string) {
    const queryClient = createQueryClient();
    return render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <TooltipProvider>
            <RouterProvider router={buildTestRouter(initialEntry)} />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>,
    );
  }

  it("renders the page heading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /new simulation run/i })).toBeInTheDocument();
    });
  });

  it("renders a back button", async () => {
    renderPage();
    await waitFor(() => {
      const backBtn = screen.getByRole("button", { name: /go back/i });
      expect(backBtn).toBeInTheDocument();
    });
  });

  it("renders the run form fields", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Create Simulation Run")).toBeInTheDocument();
      expect(screen.getByRole("group", { name: /algorithm selection/i })).toBeInTheDocument();
    });
  });

  it("preselects a molecule from the route search", async () => {
    renderPage(`/runs/new?molecule_id=${getMockMolecule().id}`);
    await waitFor(() => {
      expect(document.getElementById("molecule-combobox")).toHaveTextContent("H2");
      expect(screen.getByText("View molecule info")).toBeInTheDocument();
    });
  });

  it("refreshes the selected molecule when the route search changes", async () => {
    const queryClient = createQueryClient();
    const router = buildTestRouter();

    render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <TooltipProvider>
            <RouterProvider router={router} />
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /new simulation run/i })).toBeInTheDocument();
    });

    await act(async () => {
      await router.navigate({
        to: "/runs/new",
        search: { molecule_id: getMockMolecule().id },
      });
    });

    await waitFor(() => {
      expect(document.getElementById("molecule-combobox")).toHaveTextContent("H2");
      expect(screen.getByText("View molecule info")).toBeInTheDocument();
    });
  });
});
