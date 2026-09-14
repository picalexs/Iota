import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { RunsList } from "@/features/runs/RunsList";
import { createQueryClient } from "@/state/query-client";
import { MOBILE_BREAKPOINT } from "@/lib/layout-constants";
import type {
  MoleculeSummaryListResponse,
  MoleculeSummaryResponse,
  RunSummaryListResponse,
  RunSummaryResponse,
} from "@/types/run";

interface RunsListMocks {
  readonly api: {
    readonly cancelRun: ReturnType<typeof vi.fn>;
    readonly deleteRun: ReturnType<typeof vi.fn>;
    readonly pauseRun: ReturnType<typeof vi.fn>;
    readonly restartRun: ReturnType<typeof vi.fn>;
    readonly resumeRun: ReturnType<typeof vi.fn>;
  };
  readonly hooks: {
    readonly useListRunSummaries: ReturnType<typeof vi.fn>;
    readonly useAllMoleculeSummaries: ReturnType<typeof vi.fn>;
    readonly useInvalidateRunsList: ReturnType<typeof vi.fn>;
    readonly useInvalidateMoleculesList: ReturnType<typeof vi.fn>;
    readonly useInvalidateRun: ReturnType<typeof vi.fn>;
  };
  readonly navigate: ReturnType<typeof vi.fn>;
  search: Record<string, unknown>;
}

const runsListMocks: RunsListMocks = vi.hoisted(() => ({
  api: {
    cancelRun: vi.fn(),
    deleteRun: vi.fn(),
    pauseRun: vi.fn(),
    restartRun: vi.fn(),
    resumeRun: vi.fn(),
  },
  hooks: {
    useListRunSummaries: vi.fn(),
    useAllMoleculeSummaries: vi.fn(),
    useInvalidateRunsList: vi.fn(),
    useInvalidateMoleculesList: vi.fn(),
    useInvalidateRun: vi.fn(),
  },
  navigate: vi.fn(),
  search: {},
}));

vi.mock("@/hooks", () => ({
  ...runsListMocks.hooks,
}));

export const api = runsListMocks.api;
vi.mock("@/api/runs", () => ({
  ...runsListMocks.api,
}));

export const mockNavigate = runsListMocks.navigate;
vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    children,
    ...props
  }: {
    readonly to: string;
    readonly children: ReactNode;
    readonly [key: string]: unknown;
  }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => runsListMocks.navigate,
  useSearch: () => runsListMocks.search,
}));

export const hooks = runsListMocks.hooks;
export function setRunsListSearch(search: Record<string, unknown>) {
  runsListMocks.search = search;
}

export const mockRun1: RunSummaryResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "COMPLETED" as const,
  algorithm: "vqe" as const,
  backend_target: "statevector" as const,
  backend_name: null,
  converged: true,
  chemical_accurate: true,
  metadata: { runtime_seconds: 300 },
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

export const mockRun2: RunSummaryResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000002",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000002",
  status: "RUNNING" as const,
  algorithm: "qse" as const,
  backend_target: "statevector" as const,
  backend_name: null,
  converged: null,
  chemical_accurate: null,
  metadata: { run_started_at: "2025-06-02T08:25:00Z" },
  latest_estimate: null,
  created_at: "2025-06-02T08:00:00Z",
  updated_at: "2025-06-02T08:30:00Z",
};

export const mockRunListResponse: RunSummaryListResponse = {
  items: [mockRun1, mockRun2],
  total: 2,
  limit: 50,
  offset: 0,
};

const mockMolecules: MoleculeSummaryResponse[] = [
  {
    id: "bbbbbbbb-0000-0000-0000-000000000001",
    name: "H2",
    charge: 0,
    atom_count: 2,
    formula: "H2",
    iupac_name: null,
    run_count: 0,
  },
  {
    id: "bbbbbbbb-0000-0000-0000-000000000002",
    name: "LiH",
    charge: 0,
    atom_count: 2,
    formula: "HLi",
    iupac_name: null,
    run_count: 0,
  },
];

export const mockMoleculeListResponse: MoleculeSummaryListResponse = {
  items: mockMolecules,
  total: 2,
};

const queryClient = createQueryClient();

export function renderWithQuery(component: ReactElement = <RunsList />): RenderResult {
  return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>);
}

export function setRunsListViewport(width: number) {
  vi.stubGlobal("innerWidth", width);
  vi.stubGlobal("matchMedia", (query: string) => {
    const maxWidthMatch = query.match(/max-width:\s*(\d+)px/);
    const minWidthMatch = query.match(/min-width:\s*(\d+)px/);
    const maxWidth = maxWidthMatch ? Number(maxWidthMatch[1]) : null;
    const minWidth = minWidthMatch ? Number(minWidthMatch[1]) : null;
    const matches =
      (maxWidth === null || width <= maxWidth) && (minWidth === null || width >= minWidth);

    return {
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
  });
}

export function resetRunsListMocks() {
  vi.clearAllMocks();
  runsListMocks.search = {};
  queryClient.clear();
  setRunsListViewport(MOBILE_BREAKPOINT + 256);
  runsListMocks.hooks.useInvalidateRunsList.mockReturnValue(vi.fn().mockResolvedValue(undefined));
  runsListMocks.api.cancelRun.mockResolvedValue({ id: "run", status: "CANCELLED" });
  runsListMocks.api.deleteRun.mockResolvedValue(undefined);
  runsListMocks.api.pauseRun.mockResolvedValue({ id: "run", status: "PAUSED" });
  runsListMocks.api.restartRun.mockResolvedValue({ id: "run", status: "QUEUED" });
  runsListMocks.api.resumeRun.mockResolvedValue({ id: "run", status: "QUEUED" });
}
