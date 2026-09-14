import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const { logAppError } = vi.hoisted(() => ({
  logAppError: vi.fn(),
}));

vi.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({ theme: "light" as const, resolvedTheme: "light" as const, setTheme: vi.fn() }),
}));
vi.mock("@/lib/app-logger", () => ({
  logAppError,
}));
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { RunDetailPage } from "./run-detail-page";
import type { RunResponse } from "@/types/run";
import { ApiError } from "@/api/http";
import { createQueryClient } from "@/state/query-client";

// Mock API
vi.mock("@/api/runs", () => ({
  getRun: vi.fn(),
  cancelRun: vi.fn(),
  pauseRun: vi.fn(),
  resumeRun: vi.fn(),
  restartRun: vi.fn(),
  getRunResult: vi.fn(),
  getRunEvents: vi.fn(),
}));

vi.mock("@/api/molecules", () => ({
  getMolecule: vi.fn(),
}));

vi.mock("@/api/sse", () => ({
  subscribeToRunEvents: vi.fn(),
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

import * as moleculesApi from "@/api/molecules";
import * as runsApi from "@/api/runs";
import * as sseApi from "@/api/sse";

const api = { ...moleculesApi, ...runsApi, ...sseApi };

const mockRun: RunResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "COMPLETED",
  config_json: {
    ansatz: "UCCSD",
    optimizer: "COBYLA",
    max_iterations: 100,
    backend: "aer_simulator",
  },
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

const mockMolecule = {
  id: "bbbbbbbb-0000-0000-0000-000000000001",
  name: "H2",
  atoms: [],
  basis_set: "sto-3g",
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2025-06-01T00:00:00Z",
  updated_at: "2025-06-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  // Default stubs for APIs added by RunDetail — overridden per-test as needed
  (api.getRunEvents as ReturnType<typeof vi.fn>).mockResolvedValue({
    events: [],
    last_sequence: 0,
  });
  (api.getRunResult as ReturnType<typeof vi.fn>).mockResolvedValue(null);
  (api.subscribeToRunEvents as ReturnType<typeof vi.fn>).mockReturnValue({
    abort: vi.fn(),
    signal: {},
  });
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

const queryClient = createQueryClient();

function renderWithProviders(runId = "aaaaaaaa-0000-0000-0000-000000000001") {
  queryClient.clear();

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={buildTestRouter(runId)} />
    </QueryClientProvider>,
  );
}

function buildTestRouter(runId = "aaaaaaaa-0000-0000-0000-000000000001") {
  const rootRoute = createRootRoute();
  const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs",
    component: () => <div>Runs List</div>,
  });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/$runId",
    component: RunDetailPage,
  });
  const routeTree = rootRoute.addChildren([runsRoute, detailRoute]);
  const history = createMemoryHistory({ initialEntries: [`/runs/${runId}`] });
  return createRouter({ routeTree, history });
}

describe("RunDetailPage", () => {
  it("renders loading skeleton while fetching", async () => {
    (api.getRun as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    (api.getMolecule as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

    const { container } = renderWithProviders();

    await waitFor(() => {
      const skeletons = container.querySelectorAll("[data-slot='skeleton']");
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  it("renders the status badge and summary after loading", async () => {
    (api.getRun as ReturnType<typeof vi.fn>).mockResolvedValue(mockRun);
    (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockMolecule);

    renderWithProviders();

    await waitFor(() => {
      // StatusBadge appears in title row and overview card — getAllByText handles duplicates
      const completedBadges = screen.getAllByText("COMPLETED");
      expect(completedBadges.length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getAllByText("H2").length).toBeGreaterThan(0);
  });

  it("renders molecule name after loading", async () => {
    (api.getRun as ReturnType<typeof vi.fn>).mockResolvedValue(mockRun);
    (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockMolecule);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getAllByText("H2").length).toBeGreaterThan(0);
    });
  });

  it("renders error message if run not found", async () => {
    (api.getRun as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiError("NOT_FOUND", "Run not found", 404),
    );
    (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockMolecule);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Run not found");
    expect(logAppError).toHaveBeenCalledWith(
      "run-detail.load",
      "Failed to load run detail.",
      expect.objectContaining({
        code: "NOT_FOUND",
        message: "Run not found",
        status: 404,
      }),
      { runId: "aaaaaaaa-0000-0000-0000-000000000001" },
    );
  });

  it("renders a back link to /runs", async () => {
    (api.getRun as ReturnType<typeof vi.fn>).mockResolvedValue(mockRun);
    (api.getMolecule as ReturnType<typeof vi.fn>).mockResolvedValue(mockMolecule);

    renderWithProviders();

    // Back link should be visible once router renders the page
    await waitFor(() => {
      const backBtn = screen.getByRole("button", { name: /go back/i });
      expect(backBtn).toBeInTheDocument();
    });
  });
});
