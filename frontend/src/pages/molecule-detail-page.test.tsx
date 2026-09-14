import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
  type AnyRouter,
} from "@tanstack/react-router";
import { MoleculeDetailPage } from "./molecule-detail-page";
import type { MoleculeResponse } from "@/types/run";
import { ViewerPreferencesProvider } from "@/context/viewer-preferences-context";
import { ThemeProvider } from "@/context/theme-context";
import { createQueryClient } from "@/state/query-client";

// Mock API
vi.mock("@/api/molecules", () => ({
  getMolecule: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
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
  Group: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Separator: () => <hr />,
}));

import * as api from "@/api/molecules";

const mockMolecule: MoleculeResponse = {
  id: "a1b2c3d4-0000-0000-0000-000000000001",
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
  pubchem_cid: null,
  iupac_name: null,
  description: null,
  synonyms: null,
  smiles: null,
  inchi: null,
  inchi_key: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockMolecule);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

function buildTestRouter() {
  const rootRoute = createRootRoute();
  const moleculesRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/molecules",
    component: () => <div>Molecules List</div>,
  });
  const moleculeDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/molecules/$moleculeId",
    component: MoleculeDetailPage,
  });
  const routeTree = rootRoute.addChildren([moleculesRoute, moleculeDetailRoute]);
  const history = createMemoryHistory({
    initialEntries: ["/molecules/a1b2c3d4-0000-0000-0000-000000000001"],
  });
  return createRouter({ routeTree, history });
}

function buildStatefulRouter() {
  const rootRoute = createRootRoute();
  const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/new",
    component: () => <div>Run Create</div>,
  });
  const moleculesRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/molecules",
    component: () => <div>Molecules List</div>,
  });
  const moleculeDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/molecules/$moleculeId",
    component: MoleculeDetailPage,
  });
  const routeTree = rootRoute.addChildren([runsRoute, moleculesRoute, moleculeDetailRoute]);
  const history = createMemoryHistory({
    initialEntries: ["/runs/new"],
  });
  return createRouter({ routeTree, history });
}

function renderWithProviders(router: AnyRouter) {
  queryClient.clear();
  return render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ViewerPreferencesProvider>
          <RouterProvider router={router} />
        </ViewerPreferencesProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

const queryClient = createQueryClient();

describe("MoleculeDetailPage", () => {
  it("renders the page heading with molecule name", async () => {
    const router = buildTestRouter();
    renderWithProviders(router);

    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });
  });

  it("renders a back button", async () => {
    const router = buildTestRouter();
    renderWithProviders(router);

    await waitFor(() => {
      const backBtn = screen.getByRole("button", { name: /go back/i });
      expect(backBtn).toBeInTheDocument();
    });
  });

  it("falls back to the molecules list when opened from the run form molecule link", async () => {
    const router = buildStatefulRouter();
    await router.navigate({
      to: "/molecules/$moleculeId",
      params: { moleculeId: mockMolecule.id },
      state: (prev) => ({ ...prev, __source: "run-create-molecule-info" }),
    });
    renderWithProviders(router);
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /go back/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /go back/i }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/molecules");
    });
  });

  it("renders the MoleculeDetail component", async () => {
    const router = buildTestRouter();
    renderWithProviders(router);

    await waitFor(() => {
      expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
    });
  });

  describe("responsive layoutSnapShots", () => {
    it("renders with responsive constraints on mobile (375px)", async () => {
      // Set mobile viewport
      Object.defineProperty(globalThis, "innerWidth", {
        writable: true,
        configurable: true,
        value: 375,
      });

      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      expect(container).toMatchSnapshot("mobile-375px");
    });

    it("renders with responsive constraints on tablet (768px)", async () => {
      // Set tablet viewport
      Object.defineProperty(globalThis, "innerWidth", {
        writable: true,
        configurable: true,
        value: 768,
      });

      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      expect(container).toMatchSnapshot("tablet-768px");
    });

    it("renders with responsive constraints on desktop (1280px)", async () => {
      // Set desktop viewport
      Object.defineProperty(globalThis, "innerWidth", {
        writable: true,
        configurable: true,
        value: 1280,
      });

      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      expect(container).toMatchSnapshot("desktop-1280px");
    });

    it("applies max-w-7xl to constrain width", async () => {
      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      const wrapper = container.querySelector(".max-w-7xl");
      expect(wrapper).toBeInTheDocument();
    });

    it("applies mx-auto to center content horizontally", async () => {
      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      const wrapper = container.querySelector(".mx-auto");
      expect(wrapper).toBeInTheDocument();
    });

    it("applies responsive padding (px-2 sm:px-4 lg:px-6)", async () => {
      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      const wrapper = container.querySelector(String.raw`.px-2.sm\:px-4.lg\:px-6`);
      expect(wrapper).toBeInTheDocument();
    });

    it("applies w-full to take full available width", async () => {
      const router = buildTestRouter();
      const { container } = renderWithProviders(router);

      await waitFor(() => {
        expect(screen.getByTestId("molecule-detail")).toBeInTheDocument();
      });

      const wrapper = container.querySelector(".w-full");
      expect(wrapper).toBeInTheDocument();
    });
  });
});
