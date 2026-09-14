import { render, type RenderResult } from "@testing-library/react";
import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { RunDetail } from "./run-detail";
import { createQueryClient } from "@/state/query-client";
import type {
  MoleculeResponse,
  RunEventListResponse,
  RunResponse,
  RunResultResponse,
} from "@/types/run";

const runDetailMocks = vi.hoisted(() => ({
  api: {
    getRun: vi.fn(),
    getMolecule: vi.fn(),
    cancelRun: vi.fn(),
    pauseRun: vi.fn(),
    resumeRun: vi.fn(),
    restartRun: vi.fn(),
    getRunResult: vi.fn(),
    getRunEvents: vi.fn(),
    subscribeToRunEvents: vi.fn(),
    fetchBackendCapabilities: vi.fn(),
    getBackendCapabilitiesCached: vi.fn(),
  },
}));

const mockLocationState = vi.hoisted(() => ({ current: null as unknown }));
const mockRouterBack = vi.hoisted(() => vi.fn());
const mockRouterNavigate = vi.hoisted(() => vi.fn());
const mockNavigate = vi.hoisted(() => vi.fn());

vi.mock("@/api/runs", () => ({
  getRun: runDetailMocks.api.getRun,
  getRunResult: runDetailMocks.api.getRunResult,
  getRunEvents: runDetailMocks.api.getRunEvents,
  cancelRun: runDetailMocks.api.cancelRun,
  pauseRun: runDetailMocks.api.pauseRun,
  resumeRun: runDetailMocks.api.resumeRun,
  restartRun: runDetailMocks.api.restartRun,
}));

vi.mock("@/api/molecules", () => ({
  getMolecule: runDetailMocks.api.getMolecule,
}));

vi.mock("@/api/backends", () => ({
  fetchBackendCapabilities: runDetailMocks.api.fetchBackendCapabilities,
  getBackendCapabilitiesCached: runDetailMocks.api.getBackendCapabilitiesCached,
}));

vi.mock("@/api/sse", () => ({
  subscribeToRunEvents: runDetailMocks.api.subscribeToRunEvents,
}));

/* Keep one local object so existing run-detail tests can configure the owners. */
export const api = {
  ...runDetailMocks.api,
};

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: ReactNode; to?: string }) => (
    <a href={to ?? "#"}>{children}</a>
  ),
  useNavigate: () => mockNavigate,
  useLocation: ({ select }: { select: (location: { state: unknown }) => unknown }) =>
    select({ state: mockLocationState.current }),
  useRouter: () => ({
    history: { back: mockRouterBack, canGoBack: () => false },
    navigate: mockRouterNavigate,
  }),
}));

export const routerMocks = {
  historyBack: mockRouterBack,
  navigate: mockRouterNavigate,
  navigateHook: mockNavigate,
};
export const setRunDetailLocationState = (state: unknown) => {
  mockLocationState.current = state;
};

export const RUN_ID = "aaaaaaaa-0000-0000-0000-000000000001";
export const MOLECULE_ID = "bbbbbbbb-0000-0000-0000-000000000001";

export const baseRun: RunResponse = {
  id: RUN_ID,
  molecule_id: MOLECULE_ID,
  status: "RUNNING",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "aer_simulator",
  config_json: {
    algorithm: "vqe",
    mode: "advanced",
    backend_target: "aer_simulator",
    advanced_config: {
      algorithm: "vqe",
      ansatz_name: "UCCSD",
      optimizer_name: "COBYLA",
      max_iterations: 100,
    },
  },
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

export const molecule: MoleculeResponse = {
  id: MOLECULE_ID,
  name: "H2",
  atoms: [],
  basis_set: "sto-3g",
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:00:00Z",
};

export const result: RunResultResponse = {
  run_id: RUN_ID,
  energy: -1.13727,
  iterations: 42,
  optimal_parameters: [0.1, 0.2],
  converged: true,
  created_at: "2025-06-01T10:05:00Z",
};

export const emptyEvents: RunEventListResponse = { events: [], last_sequence: 0 };

export const abortControllerMock = {
  abort: vi.fn(),
  signal: {} as AbortSignal,
};

const queryClient = createQueryClient();

export function renderRunDetail(runId = RUN_ID): RenderResult {
  return render(
    <QueryClientProvider client={queryClient}>
      <RunDetail runId={runId} />
    </QueryClientProvider>,
  );
}

export function setupRunDetailMocks(runOverride: Partial<RunResponse> = {}) {
  const run = { ...baseRun, ...runOverride };
  vi.mocked(api.getRun).mockResolvedValue(run);
  vi.mocked(api.getMolecule).mockResolvedValue(molecule);
  vi.mocked(api.getRunEvents).mockResolvedValue(emptyEvents);
  vi.mocked(api.getRunResult).mockResolvedValue(result);
  vi.mocked(api.cancelRun).mockResolvedValue({ id: RUN_ID, status: "CANCELLED" });
  vi.mocked(api.pauseRun).mockResolvedValue({ id: RUN_ID, status: "PAUSED" });
  vi.mocked(api.resumeRun).mockResolvedValue({ id: RUN_ID, status: "QUEUED" });
  vi.mocked(api.restartRun).mockResolvedValue({
    ...run,
    id: "aaaaaaaa-0000-0000-0000-000000000099",
  });
  vi.mocked(api.subscribeToRunEvents).mockReturnValue(abortControllerMock);
  vi.mocked(api.fetchBackendCapabilities).mockResolvedValue({ backends: [] });
  vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue({ backends: [] });
}

export function resetRunDetailMocks() {
  vi.clearAllMocks();
  abortControllerMock.abort.mockReset();
  mockLocationState.current = null;
  mockRouterBack.mockReset();
  mockRouterNavigate.mockReset();
  mockNavigate.mockReset();
  localStorage.clear();
  queryClient.clear();
}
