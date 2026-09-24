import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BenchmarkRunsPage } from "./benchmark-runs-page";
import type { SavedBenchmarkRun } from "./benchmark/benchmark-storage";
import type { RunAlgorithm } from "@/types/run";

const navigate = vi.fn();
const queryClient = {
  setQueriesData: vi.fn(),
};
const invalidateBenchmarkRunQueries = vi.fn().mockResolvedValue(undefined);
const invalidateRunsQueries = vi.fn().mockResolvedValue(undefined);
const useListBenchmarkRuns = vi.fn();
const pauseRun = vi.fn();
const resumeRun = vi.fn();
const restartRun = vi.fn();
const cancelRun = vi.fn();
const updateBenchmarkRun = vi.fn();
const createBenchmarkRun = vi.fn();
const deleteBenchmarkRun = vi.fn();
const listBenchmarkRunSummaries = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => queryClient,
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigate,
}));

vi.mock("@/hooks/use-query-hooks", () => ({
  useListBenchmarkRuns: (...args: unknown[]) => useListBenchmarkRuns(...args),
  useListBenchmarkRunSummaries: (...args: unknown[]) => useListBenchmarkRuns(...args),
  invalidateBenchmarkRunQueries: (...args: unknown[]) => invalidateBenchmarkRunQueries(...args),
  invalidateRunsQueries: (...args: unknown[]) => invalidateRunsQueries(...args),
}));

vi.mock("@/api/benchmarks", () => ({
  createBenchmarkRun: (...args: unknown[]) => createBenchmarkRun(...args),
  deleteBenchmarkRun: (...args: unknown[]) => deleteBenchmarkRun(...args),
  listBenchmarkRuns: vi.fn(),
  listBenchmarkRunSummaries: (...args: unknown[]) => listBenchmarkRunSummaries(...args),
  updateBenchmarkRun: (...args: unknown[]) => updateBenchmarkRun(...args),
}));

vi.mock("@/api/runs", () => ({
  cancelRun: (...args: unknown[]) => cancelRun(...args),
  pauseRun: (...args: unknown[]) => pauseRun(...args),
  restartRun: (...args: unknown[]) => restartRun(...args),
  resumeRun: (...args: unknown[]) => resumeRun(...args),
}));

function savedRun(
  overrides: Partial<SavedBenchmarkRun> & Pick<SavedBenchmarkRun, "id" | "name">,
): SavedBenchmarkRun {
  const { id, name, ...rest } = overrides;
  return {
    id,
    name,
    createdAt: "2026-06-04T12:00:00.000Z",
    updatedAt: "2026-06-04T12:05:00.000Z",
    selectedMoleculeKeys: ["h2"],
    selectedAlgorithms: ["vqe"] as RunAlgorithm[],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    entries: [],
    ...rest,
  };
}

function getNewBenchmarkButton() {
  const button = screen.getAllByRole("button", { name: /new benchmark/i })[0];
  if (!button) {
    throw new Error("Expected a new benchmark button");
  }
  return button;
}

describe("BenchmarkRunsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useListBenchmarkRuns.mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    pauseRun.mockResolvedValue({ id: "run-1", status: "PAUSED" });
    resumeRun.mockResolvedValue({ id: "run-1", status: "QUEUED" });
    restartRun.mockResolvedValue({ id: "run-1", status: "QUEUED" });
    cancelRun.mockResolvedValue({ id: "run-1", status: "CANCELLED" });
    updateBenchmarkRun.mockImplementation(async (id: string, data: { entries: unknown[] }) =>
      savedRun({
        id,
        name: `Updated ${id}`,
        entries: data.entries as SavedBenchmarkRun["entries"],
      }),
    );
  });

  it("shows a loading skeleton while the benchmark list is loading", () => {
    useListBenchmarkRuns.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    });

    const { container } = render(<BenchmarkRunsPage />);

    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });

  it("requests and renders benchmark histories larger than the old page limit", () => {
    const items = Array.from({ length: 60 }, (_, index) =>
      savedRun({ id: `benchmark-${index + 1}`, name: `Benchmark ${index + 1}` }),
    );
    useListBenchmarkRuns.mockReturnValue({
      data: { items, total: items.length },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<BenchmarkRunsPage />);

    expect(screen.getByText("Benchmark 60")).toBeInTheDocument();
    expect(useListBenchmarkRuns).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ limit: 50, offset: 0 }),
    );
  });

  it("shows the benchmark history error state and retries loading", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn().mockResolvedValue(undefined);
    useListBenchmarkRuns.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: {
        name: "ApiError",
        message: "Gateway timeout",
        status: 503,
      },
      refetch,
    });

    render(<BenchmarkRunsPage />);

    expect(screen.getByText("The API is unavailable right now")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The frontend is still running, but the benchmark history cannot load live data until the backend responds again.",
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledTimes(1);
    });
  });

  it("creates a new benchmark draft and navigates to its dashboard", async () => {
    const user = userEvent.setup();
    createBenchmarkRun.mockResolvedValue({ id: "benchmark-1" });

    render(<BenchmarkRunsPage />);

    await user.click(getNewBenchmarkButton());

    await waitFor(() => {
      expect(createBenchmarkRun).toHaveBeenCalledWith(
        expect.objectContaining({
          selectedMoleculeKeys: [],
          selectedAlgorithms: expect.arrayContaining(["vqe", "sqd", "kqd", "qfd", "qse", "skqd"]),
          selectedBackendMode: "statevector",
        }),
      );
    });
    expect(invalidateBenchmarkRunQueries).toHaveBeenCalledWith(queryClient);
    expect(navigate).toHaveBeenCalledWith({
      to: "/benchmarks/$benchmarkId",
      params: { benchmarkId: "benchmark-1" },
    });
  });

  it("surfaces create failures inline", async () => {
    const user = userEvent.setup();
    createBenchmarkRun.mockRejectedValue(new Error("backend offline"));

    render(<BenchmarkRunsPage />);

    await user.click(getNewBenchmarkButton());

    expect(
      await screen.findByText("The draft was not saved. Try again once the backend is reachable."),
    ).toBeInTheDocument();
    expect(screen.getByText("backend offline")).toBeInTheDocument();
  });

  it("keeps failed selections and reports partial delete failures", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({ id: "run-1", name: "Benchmark A" }),
          savedRun({ id: "run-2", name: "Benchmark B" }),
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    deleteBenchmarkRun
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("delete failed"));

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select benchmark a/i }));
    await user.click(screen.getByRole("checkbox", { name: /select benchmark b/i }));
    await user.click(screen.getByRole("button", { name: /delete \(2\)/i }));
    await user.click(screen.getByRole("button", { name: /delete benchmarks/i }));

    await waitFor(() => {
      expect(deleteBenchmarkRun).toHaveBeenCalledTimes(2);
      expect(invalidateBenchmarkRunQueries).toHaveBeenCalledWith(queryClient);
    });
    expect(
      await screen.findByText(/deleted 1 benchmark, 1 failed\. delete failed/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /select benchmark b/i })).toBeChecked();
  });

  it("can delete selected benchmarks with their associated runs", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({
            id: "run-1",
            name: "Benchmark A",
            entries: [
              {
                id: "entry-1",
                preset: {
                  key: "h2",
                  name: "H2",
                  formula: "H2",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -1.116, fci: -1.137, source: "test" },
                },
                algorithm: "vqe",
                status: "completed",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000001",
                energy: -1.137,
                currentEnergy: -1.137,
                converged: true,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: 12,
                latestEventSequence: 1,
              },
            ],
          }),
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    deleteBenchmarkRun.mockResolvedValue(undefined);

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select benchmark a/i }));
    await user.click(screen.getByRole("button", { name: /delete \(1\)/i }));
    await user.click(screen.getByRole("checkbox", { name: /also delete associated runs/i }));
    await user.click(screen.getByRole("button", { name: /delete benchmark/i }));

    await waitFor(() => {
      expect(deleteBenchmarkRun).toHaveBeenCalledWith("run-1", { deleteAssociatedRuns: true });
      expect(invalidateRunsQueries).toHaveBeenCalledWith(queryClient);
    });
  });

  it("filters saved benchmarks by aggregate status and backend", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({
            id: "run-1",
            name: "Running IBM benchmark",
            selectedBackendMode: "ibm_runtime",
            entries: [
              {
                id: "entry-1",
                preset: {
                  key: "h2",
                  name: "H2",
                  formula: "H2",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -1.116, fci: -1.137, source: "test" },
                },
                algorithm: "vqe",
                status: "running",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000001",
                energy: null,
                currentEnergy: null,
                converged: null,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: null,
                latestEventSequence: 0,
              },
            ],
          }),
          savedRun({
            id: "run-2",
            name: "Paused Aer benchmark",
            selectedBackendMode: "aer_simulator",
            entries: [
              {
                id: "entry-2",
                preset: {
                  key: "lih",
                  name: "LiH",
                  formula: "LiH",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -7.0, fci: -7.1, source: "test" },
                },
                algorithm: "vqe",
                status: "paused",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000002",
                energy: null,
                currentEnergy: null,
                converged: null,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: null,
                latestEventSequence: 0,
              },
            ],
          }),
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /filter by status/i }));
    await user.click(screen.getAllByText("Paused").at(-1)!);

    expect(screen.getByText("Paused Aer benchmark")).toBeInTheDocument();
    expect(screen.queryByText("Running IBM benchmark")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /filter by backend/i }));
    await user.click(screen.getAllByText("Aer").at(-1)!);

    expect(screen.getByText("Backend: Aer")).toBeInTheDocument();
  });

  it("sorts benchmarks from the table headers", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({ id: "run-2", name: "Benchmark B" }),
          savedRun({ id: "run-1", name: "Benchmark A" }),
        ],
        total: 2,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /sort by name/i }));

    const names = screen
      .getAllByText(/Benchmark [AB]/)
      .map((element) => element.textContent)
      .slice(0, 2);
    expect(names).toEqual(["Benchmark A", "Benchmark B"]);
  });

  it("lets the user clear filters when they hide every saved benchmark", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({
            id: "run-1",
            name: "Running IBM benchmark",
            selectedBackendMode: "ibm_runtime",
            entries: [
              {
                id: "entry-1",
                preset: {
                  key: "h2",
                  name: "H2",
                  formula: "H2",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -1.116, fci: -1.137, source: "test" },
                },
                algorithm: "vqe",
                status: "running",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000001",
                energy: null,
                currentEnergy: null,
                converged: null,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: null,
                latestEventSequence: 0,
              },
            ],
          }),
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /filter by status/i }));
    await user.click(screen.getAllByText("Paused").at(-1)!);

    expect(screen.getByText("No benchmarks match these filters")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /clear filters/i }));

    expect(screen.getByText("Running IBM benchmark")).toBeInTheDocument();
    expect(screen.queryByText("No benchmarks match these filters")).not.toBeInTheDocument();
  });

  it("pauses selected benchmarks from the bulk action bar", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({
            id: "run-1",
            name: "Benchmark A",
            entries: [
              {
                id: "entry-1",
                preset: {
                  key: "h2",
                  name: "H2",
                  formula: "H2",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -1.116, fci: -1.137, source: "test" },
                },
                algorithm: "vqe",
                status: "running",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000001",
                energy: null,
                currentEnergy: null,
                converged: null,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: null,
                latestEventSequence: 0,
              },
            ],
          }),
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    updateBenchmarkRun.mockResolvedValue(
      savedRun({
        id: "run-1",
        name: "Benchmark A",
        entries: [
          {
            id: "entry-1",
            preset: {
              key: "h2",
              name: "H2",
              formula: "H2",
              description: "Test molecule",
              atoms: [],
              charge: 0,
              multiplicity: 1,
              active_space: { n_electrons: 2, n_orbitals: 2 },
              basis: "sto-3g",
              references: { hf: -1.116, fci: -1.137, source: "test" },
            },
            algorithm: "vqe",
            status: "paused",
            moleculeId: null,
            runId: "aaaaaaaa-0000-0000-0000-000000000001",
            energy: null,
            currentEnergy: null,
            converged: null,
            errorMessage: null,
            classicalRefs: null,
            elapsedSeconds: null,
            latestEventSequence: 0,
          },
        ],
      }),
    );

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select benchmark a/i }));
    await user.click(screen.getByRole("button", { name: /pause \(1\)/i }));
    await user.click(screen.getByRole("button", { name: /pause benchmarks/i }));

    await waitFor(() => {
      expect(pauseRun).toHaveBeenCalledWith("aaaaaaaa-0000-0000-0000-000000000001");
    });
    expect(updateBenchmarkRun).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        entries: [
          expect.objectContaining({
            id: "entry-1",
            status: "paused",
          }),
        ],
      }),
    );
  });

  it("resumes a benchmark from the row actions menu", async () => {
    const user = userEvent.setup();
    useListBenchmarkRuns.mockReturnValue({
      data: {
        items: [
          savedRun({
            id: "run-1",
            name: "Benchmark A",
            entries: [
              {
                id: "entry-1",
                preset: {
                  key: "h2",
                  name: "H2",
                  formula: "H2",
                  description: "Test molecule",
                  atoms: [],
                  charge: 0,
                  multiplicity: 1,
                  active_space: { n_electrons: 2, n_orbitals: 2 },
                  basis: "sto-3g",
                  references: { hf: -1.116, fci: -1.137, source: "test" },
                },
                algorithm: "vqe",
                status: "paused",
                moleculeId: null,
                runId: "aaaaaaaa-0000-0000-0000-000000000001",
                energy: null,
                currentEnergy: null,
                converged: null,
                errorMessage: null,
                classicalRefs: null,
                elapsedSeconds: null,
                latestEventSequence: 0,
              },
            ],
          }),
        ],
        total: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    updateBenchmarkRun.mockResolvedValue(
      savedRun({
        id: "run-1",
        name: "Benchmark A",
        entries: [
          {
            id: "entry-1",
            preset: {
              key: "h2",
              name: "H2",
              formula: "H2",
              description: "Test molecule",
              atoms: [],
              charge: 0,
              multiplicity: 1,
              active_space: { n_electrons: 2, n_orbitals: 2 },
              basis: "sto-3g",
              references: { hf: -1.116, fci: -1.137, source: "test" },
            },
            algorithm: "vqe",
            status: "queued",
            moleculeId: null,
            runId: "aaaaaaaa-0000-0000-0000-000000000001",
            energy: null,
            currentEnergy: null,
            converged: null,
            errorMessage: null,
            classicalRefs: null,
            elapsedSeconds: null,
            latestEventSequence: 0,
          },
        ],
      }),
    );

    render(<BenchmarkRunsPage />);

    await user.click(screen.getByRole("button", { name: /benchmark actions for benchmark a/i }));
    await user.click(screen.getByRole("button", { name: /resume benchmark/i }));

    await waitFor(() => {
      expect(resumeRun).toHaveBeenCalledWith("aaaaaaaa-0000-0000-0000-000000000001");
    });
    expect(updateBenchmarkRun).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        entries: [
          expect.objectContaining({
            id: "entry-1",
            status: "queued",
          }),
        ],
      }),
    );
  });
});
