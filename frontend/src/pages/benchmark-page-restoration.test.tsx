import "./benchmark-page.test-mocks";

import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import type { BenchmarkEntry } from "./benchmark/benchmark-utils";
import { allowConsoleCall } from "@/test/console-policy";
import type { SavedBenchmarkRun } from "./benchmark-page.test-support";
import {
  benchmarkEntry,
  completedRun,
  fetchBackendCapabilities,
  forceRefreshBackendCapabilities,
  getBenchmarkRun,
  getRun,
  mockBenchmarkDetail,
  moleculeId,
  renderBenchmarkPage,
  resetBenchmarkPageTestState,
  runId,
  savedBenchmarkWithEntries,
  updateBenchmarkRun,
} from "./benchmark-page.test-support";

beforeEach(resetBenchmarkPageTestState);

describe("BenchmarkPage restoration", () => {
  it("opens a saved benchmark run from the benchmark detail route", async () => {
    const savedBenchmark: SavedBenchmarkRun = {
      id: "saved-benchmark-1",
      name: "Saved H2 QSE",
      createdAt: "2026-06-01T16:20:00Z",
      updatedAt: "2026-06-01T16:25:00Z",
      selectedMoleculeKeys: ["h2"],
      selectedAlgorithms: ["qse"],
      selectedBasis: "cc-pvdz",
      selectedBackendMode: "statevector",
      selectedBackendName: null,
      chemicalAccuracyHa: 0.0016,
      customMolecules: [],
      entries: [
        {
          id: "h2:qse",
          preset: {
            key: "h2",
            name: "Hydrogen",
            formula: "H2",
            description: "Hydrogen molecule",
            atoms: [
              { symbol: "H", x: 0, y: 0, z: 0 },
              { symbol: "H", x: 0, y: 0, z: 0.735 },
            ],
            charge: 0,
            multiplicity: 1,
            active_space: { n_electrons: 2, n_orbitals: 2 },
            basis: "sto-3g",
            references: { hf: -1.116, fci: -1.137, source: "test" },
          },
          algorithm: "qse",
          status: "completed",
          moleculeId,
          runId,
          energy: -1.137283,
          currentEnergy: -1.137283,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137 },
          elapsedSeconds: 45,
          latestEventSequence: 2,
        },
      ],
    };
    mockBenchmarkDetail(savedBenchmark);

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => {
      expect(screen.getAllByText("Done").length).toBeGreaterThan(0);
    });

    expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument();
    expect(screen.getByLabelText("Chemically accurate")).toBeInTheDocument();
  });

  it("shows a page skeleton while a saved benchmark dashboard is hydrating", async () => {
    let resolveSavedBenchmark: ((benchmark: SavedBenchmarkRun) => void) | undefined;
    (getBenchmarkRun as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise<SavedBenchmarkRun>((resolve) => {
        resolveSavedBenchmark = resolve;
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect(await screen.findByRole("status")).toHaveAttribute(
      "aria-label",
      "Loading benchmark workspace",
    );
    expect(screen.queryByText("Algorithm Benchmark")).not.toBeInTheDocument();

    expect(resolveSavedBenchmark).toBeDefined();
    resolveSavedBenchmark!(savedBenchmarkWithEntries([]));

    await waitFor(() => expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument());
  });

  it("shows an inline error instead of hanging the skeleton when a saved benchmark fails to load", async () => {
    allowConsoleCall("error", "[benchmark.hydration] Failed to load saved benchmark.");
    (getBenchmarkRun as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Benchmark lookup failed"),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect(await screen.findByRole("status")).toHaveAttribute(
      "aria-label",
      "Loading benchmark workspace",
    );

    await waitFor(() => expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("Benchmark lookup failed");
    expect(screen.queryByLabelText("Loading benchmark workspace")).not.toBeInTheDocument();
  });

  it("keeps the last saved benchmark view visible while reloading the same benchmark route", async () => {
    const savedBenchmark = savedBenchmarkWithEntries([
      benchmarkEntry({
        status: "completed",
        algorithm: "qse",
        energy: -1.137283,
        currentEnergy: -1.137283,
        converged: true,
        classicalRefs: { hf: -1.116, fci: -1.137 },
        elapsedSeconds: 45,
      }),
    ]);
    mockBenchmarkDetail(savedBenchmark);

    const firstRender = renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument());
    expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument();

    firstRender.unmount();

    let resolveSavedBenchmark: ((benchmark: SavedBenchmarkRun) => void) | undefined;
    (getBenchmarkRun as ReturnType<typeof vi.fn>).mockReturnValueOnce(
      new Promise<SavedBenchmarkRun>((resolve) => {
        resolveSavedBenchmark = resolve;
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => {
      expect(
        screen.queryByRole("status", { name: "Loading benchmark workspace" }),
      ).not.toBeInTheDocument();
      expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument();
      expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument();
    });

    await waitFor(() => expect(getBenchmarkRun).toHaveBeenCalledTimes(2));

    expect(resolveSavedBenchmark).toBeDefined();
    resolveSavedBenchmark!(savedBenchmark);

    await waitFor(() => expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument());
  });

  it("does not overwrite a cached completed row with a stale queued snapshot while the same route rehydrates", async () => {
    const completedSavedBenchmark = savedBenchmarkWithEntries([
      benchmarkEntry({
        status: "completed",
        algorithm: "qse",
        energy: -1.137283,
        currentEnergy: -1.137283,
        converged: true,
        classicalRefs: { hf: -1.116, fci: -1.137 },
        elapsedSeconds: 45,
      }),
    ]);
    mockBenchmarkDetail(completedSavedBenchmark);

    const firstRender = renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument());

    firstRender.unmount();

    (getBenchmarkRun as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      savedBenchmarkWithEntries([benchmarkEntry({ status: "queued" })]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(getBenchmarkRun).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument());
    expect(screen.queryByLabelText("Queued")).not.toBeInTheDocument();
  });

  it("warms backend capabilities while opening a saved statevector dashboard", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        name: "Saved statevector dashboard",
        selectedMoleculeKeys: ["h2"],
        selectedAlgorithms: ["vqe"],
        selectedBackendMode: "statevector",
        selectedBackendName: null,
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect(await screen.findByText("Algorithm Benchmark")).toBeInTheDocument();
    await waitFor(() => expect(getBenchmarkRun).toHaveBeenCalledWith("saved-benchmark-1"));
    await waitFor(() => expect(fetchBackendCapabilities).toHaveBeenCalledTimes(1));
  });

  it("loads backend capabilities when the backend selector is opened", async () => {
    renderBenchmarkPage();

    await userEvent.click(await screen.findByRole("combobox", { name: "Backend" }));

    await waitFor(() => expect(forceRefreshBackendCapabilities).toHaveBeenCalledTimes(1));
  });

  it("restores the saved scroll position when returning to a benchmark page", async () => {
    sessionStorage.setItem("benchmark-scroll:saved-benchmark-1", "420");
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry({ status: "completed" })]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() =>
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 420, left: 0, behavior: "auto" }),
    );
    expect(sessionStorage.getItem("benchmark-scroll:saved-benchmark-1")).toBeNull();
  });

  it("refreshes failed benchmark rows when the underlying run was resumed elsewhere", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        benchmarkEntry({
          status: "failed",
          errorMessage: "Solver failed",
          currentEnergy: -1.123,
          latestEventSequence: 2,
        }),
      ]),
    );
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...completedRun,
      status: "RUNNING",
      updated_at: "2026-01-01T00:02:00Z",
    });

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(getRun).toHaveBeenCalledWith(runId));

    await waitFor(
      () => {
        const refreshedCall = (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls.find(
          ([id, patch]) =>
            id === "saved-benchmark-1" &&
            (patch as { entries?: BenchmarkEntry[] }).entries?.some(
              (entry) =>
                entry.id === "h2:vqe" && entry.status === "running" && entry.errorMessage === null,
            ),
        );
        expect(refreshedCall).toBeTruthy();
      },
      { timeout: 5000 },
    );
  });
});
