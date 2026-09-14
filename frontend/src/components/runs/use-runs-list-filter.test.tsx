import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useRunsListFilter } from "./use-runs-list-filter";
import type { RunSummaryResponse } from "@/types/run";

const navigate = vi.fn();
let search: Record<string, unknown> = {};

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
  useSearch: () => search,
}));

const baseRun: RunSummaryResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "11111111-0000-0000-0000-000000000001",
  molecule_name: "Hydrogen",
  status: "COMPLETED",
  algorithm: "vqe",
  backend_target: "statevector",
  chemical_accurate: true,
  metadata: null,
  latest_estimate: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T01:00:00Z",
};

function runFixture(overrides: Partial<RunSummaryResponse>): RunSummaryResponse {
  return { ...baseRun, ...overrides };
}

const rawRuns: RunSummaryResponse[] = [
  baseRun,
  runFixture({
    id: "bbbbbbbb-0000-0000-0000-000000000001",
    molecule_id: "22222222-0000-0000-0000-000000000001",
    status: "RUNNING",
    algorithm: "kqd",
    backend_target: "aer_simulator",
    chemical_accurate: false,
    metadata: { runtime_seconds: 5 },
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T01:00:00Z",
    latest_estimate: {
      source: "worker",
      algorithm: "kqd",
      estimated_total_iterations: 10,
      estimated_remaining_iterations: 4,
      estimated_total_seconds: 100,
      estimated_remaining_seconds: 40,
      confidence: 0.8,
      updated_at: "2026-01-02T01:00:00Z",
    },
  }),
  runFixture({
    id: "cccccccc-0000-0000-0000-000000000001",
    molecule_id: "33333333-0000-0000-0000-000000000001",
    status: "FAILED",
    algorithm: null,
    backend_target: null,
    chemical_accurate: null,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T01:00:00Z",
  }),
];

const moleculeItems = [
  { id: "11111111-0000-0000-0000-000000000001", name: "Hydrogen" },
  { id: "22222222-0000-0000-0000-000000000001", name: "Lithium hydride" },
  { id: "33333333-0000-0000-0000-000000000001", name: "Beryllium" },
];

describe("useRunsListFilter", () => {
  afterEach(() => {
    search = {};
    navigate.mockReset();
  });

  it("filters by URL-backed status, molecule, method, backend, and accuracy", () => {
    search = {
      statuses: ["RUNNING"],
      molecule_ids: ["22222222-0000-0000-0000-000000000001"],
      methods: ["kqd"],
      backend_target: "aer_simulator",
      chemical_accurate: false,
      sort: "molecule",
      order: "asc",
      page: 3,
    };

    const { result } = renderHook(() => useRunsListFilter({ rawRuns, moleculeItems }));

    expect(result.current.runs).toHaveLength(1);
    expect(result.current.runs[0]?.id).toBe("bbbbbbbb-0000-0000-0000-000000000001");
    expect(result.current.hasActiveRuns).toBe(true);
    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.page).toBe(3);
    expect(result.current.moleculeMap.get("22222222-0000-0000-0000-000000000001")).toBe(
      "Lithium hydride",
    );
  });

  it("sorts by runtime and keeps runs with missing runtime at the end", () => {
    search = { sort: "runtime", order: "asc" };

    const { result } = renderHook(() => useRunsListFilter({ rawRuns, moleculeItems }));

    expect(result.current.runs.map((run) => run.id)).toEqual([
      "bbbbbbbb-0000-0000-0000-000000000001",
      "aaaaaaaa-0000-0000-0000-000000000001",
      "cccccccc-0000-0000-0000-000000000001",
    ]);
    expect(result.current.hasActiveFilters).toBe(false);
    expect(result.current.page).toBe(1);
  });

  it.each([
    [
      "algorithm",
      "desc",
      ["aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000001"],
    ],
    [
      "backend",
      "desc",
      ["aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000001"],
    ],
    [
      "status",
      "asc",
      ["aaaaaaaa-0000-0000-0000-000000000001", "cccccccc-0000-0000-0000-000000000001"],
    ],
    [
      "updated_at",
      "desc",
      ["cccccccc-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000001"],
    ],
    [
      "molecule",
      "asc",
      ["cccccccc-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000001"],
    ],
    [
      "created_at",
      "asc",
      ["aaaaaaaa-0000-0000-0000-000000000001", "bbbbbbbb-0000-0000-0000-000000000001"],
    ],
    [
      "runtime",
      "desc",
      ["bbbbbbbb-0000-0000-0000-000000000001", "aaaaaaaa-0000-0000-0000-000000000001"],
    ],
  ] as const)("sorts runs by %s %s", (sort, order, expectedPrefix) => {
    search = { sort, order };

    const { result } = renderHook(() => useRunsListFilter({ rawRuns, moleculeItems }));

    expect(result.current.runs.map((run) => run.id).slice(0, 2)).toEqual(expectedPrefix);
  });

  it("writes filter and pagination updates through router navigation callbacks", () => {
    search = {
      statuses: ["RUNNING"],
      molecule_ids: ["22222222-0000-0000-0000-000000000001"],
      methods: ["kqd"],
      backend_target: "aer_simulator",
      chemical_accurate: false,
      sort: "created_at",
      order: "asc",
    };

    const { result } = renderHook(() => useRunsListFilter({ rawRuns, moleculeItems }));

    act(() => {
      result.current.handleSort("created_at");
      result.current.toggleStatus("RUNNING");
      result.current.toggleMolecule("11111111-0000-0000-0000-000000000001");
      result.current.toggleMethod("vqe");
      result.current.toggleBackendTarget("aer_simulator");
      result.current.toggleChemicalAccurate(false);
      result.current.goToPage(1);
      result.current.clearFilters();
    });

    const calls = navigate.mock.calls.map(([call]) => call);
    expect(calls).toHaveLength(8);
    expect(calls.every((call) => call.to === "/runs")).toBe(true);

    const prev = {
      sort: "status",
      order: "desc",
      page: 2,
      statuses: ["RUNNING"],
      molecule_ids: ["22222222-0000-0000-0000-000000000001"],
      methods: ["kqd"],
      backend_target: "aer_simulator",
      chemical_accurate: false,
    };

    expect(calls[0].search(prev)).toMatchObject({ sort: "created_at", order: "desc", page: 2 });
    expect(calls[1].search(prev)).toMatchObject({ statuses: undefined, page: undefined });
    expect(calls[2].search(prev)).toMatchObject({
      molecule_ids: [
        "22222222-0000-0000-0000-000000000001",
        "11111111-0000-0000-0000-000000000001",
      ],
      page: undefined,
    });
    expect(calls[3].search(prev)).toMatchObject({ methods: ["kqd", "vqe"], page: undefined });
    expect(calls[4].search(prev)).toMatchObject({ backend_target: undefined, page: undefined });
    expect(calls[5].search(prev)).toMatchObject({ chemical_accurate: undefined });
    expect(calls[6].search(prev)).toMatchObject({ page: undefined });
    expect(calls[7].search(prev)).toMatchObject({
      statuses: undefined,
      molecule_ids: undefined,
      methods: undefined,
      backend_target: undefined,
      chemical_accurate: undefined,
    });
  });
});
