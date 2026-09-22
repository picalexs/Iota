import { render, screen } from "@testing-library/react";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BenchmarkResultsTable } from "./benchmark-results-table";
import type { BenchmarkEntry } from "./benchmark-utils";
import type { MoleculePreset } from "@/lib/benchmark-presets";

function buildGroupedRows(
  rowOverrides: Partial<BenchmarkEntry> = {},
): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const preset: MoleculePreset = {
    key: "n2",
    name: "Clenbuterol clorhidrate",
    formula: "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol;hydrochloride",
    description: "14-electron triple bond. Strong multireference character. Hardest benchmark.",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 10, n_orbitals: 8 },
    basis: "sto-3g",
    references: { hf: -107.49, fci: -107.59, source: "test" },
  };

  return [
    {
      preset,
      rows: [
        {
          id: "n2:vqe",
          preset,
          algorithm: "vqe",
          status: "completed",
          moleculeId: "bbbbbbbb-0000-0000-0000-000000000001",
          runId: "aaaaaaaa-0000-0000-0000-000000000001",
          energy: -107.5885,
          currentEnergy: -107.5885,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -107.49, fci: -107.59 },
          elapsedSeconds: 42.1,
          latestEventSequence: 5,
          ...rowOverrides,
        },
      ],
    },
  ];
}

function renderBenchmarkResultsTable(
  options: {
    grouped?: Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }>;
    onBeforeOpenRun?: () => void;
    onRunAction?: (
      entry: BenchmarkEntry,
      action: "pause" | "resume" | "restart" | "retry" | "cancel",
    ) => void;
    onMoleculeAction?: (
      entries: readonly BenchmarkEntry[],
      action: "pause" | "resume" | "restart" | "retry" | "cancel",
    ) => void;
  } = {},
) {
  const rootRoute = createRootRoute();
  const benchmarkRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks",
    component: () => (
      <BenchmarkResultsTable
        grouped={options.grouped ?? buildGroupedRows()}
        selectedBasis="sto-3g"
        chemicalAccuracyHa={0.0016}
        onRunAction={options.onRunAction}
        onMoleculeAction={options.onMoleculeAction}
        onBeforeOpenRun={options.onBeforeOpenRun}
      />
    ),
  });
  const runDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/$runId",
    component: () => <div>Run detail</div>,
  });
  const routeTree = rootRoute.addChildren([benchmarkRoute, runDetailRoute]);
  const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
  const router = createRouter({ routeTree, history });

  return render(<RouterProvider router={router} />);
}

describe("BenchmarkResultsTable", () => {
  it("hides preset descriptions and keeps long header labels in a truncating aligned row", async () => {
    renderBenchmarkResultsTable();

    const formula = await screen.findByText(
      "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol;hydrochloride",
    );
    expect(formula).toHaveAttribute(
      "title",
      "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol;hydrochloride",
    );
    expect(formula).toHaveClass("truncate");
    expect(screen.queryByText("Clenbuterol clorhidrate")).not.toBeInTheDocument();
    expect(formula.parentElement).toHaveClass("min-w-0", "flex-1", "items-end");
    expect(screen.getByText(/HF:/).parentElement).toHaveClass("items-center", "md:shrink-0");
    expect(screen.queryByText("sto-3g")).not.toBeInTheDocument();
    expect(screen.queryByText(/Corr:/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "14-electron triple bond. Strong multireference character. Hardest benchmark.",
      ),
    ).not.toBeInTheDocument();
  });

  it("shows chemical accuracy as a symbol and error instead of a convergence column", async () => {
    renderBenchmarkResultsTable();

    expect(await screen.findByText("Chemical accurate")).toBeInTheDocument();
    expect(screen.queryByText("Converged")).not.toBeInTheDocument();
    expect(screen.queryByText("Verdict")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Chemically accurate")).toBeInTheDocument();
    expect(screen.queryByText("Yes")).not.toBeInTheDocument();
    expect(screen.getByText("1.50 mHa")).toBeInTheDocument();
  });

  it("shows chemical accuracy for valid results when benchmark eligibility is false", async () => {
    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({
        executionMetadata: {
          benchmarkEligible: false,
          benchmarkExclusionReason: "projected_solve_diagnostic",
          projectedSolveIsDiagnostic: true,
          scientificConverged: false,
          reportedEnergyIsValid: true,
        } as NonNullable<BenchmarkEntry["executionMetadata"]>,
      }),
    });

    expect(await screen.findByLabelText("Chemically accurate")).toBeInTheDocument();
    expect(screen.getByText("1.50 mHa")).toBeInTheDocument();
  });

  it("shows the reported execution path for a completed row", async () => {
    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({
        executionMetadata: {
          actualExecutionTarget: "local_classical",
          actualPathClass: "sector_matrix_free",
        } as NonNullable<BenchmarkEntry["executionMetadata"]>,
      }),
    });

    expect(await screen.findByText("Execution path")).toBeInTheDocument();
    expect(screen.getByLabelText("Execution path: Local matrix-free")).toBeInTheDocument();
  });

  it("shows the statevector execution path", async () => {
    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({
        executionMetadata: {
          actualExecutionTarget: "statevector",
          actualPathClass: "statevector_exact",
        } as NonNullable<BenchmarkEntry["executionMetadata"]>,
      }),
    });

    expect(await screen.findByLabelText("Execution path: Statevector exact")).toBeInTheDocument();
  });

  it("marks cancelled rows as unscored for chemical accuracy", async () => {
    renderBenchmarkResultsTable({ grouped: buildGroupedRows({ status: "cancelled" }) });

    expect(
      await screen.findByLabelText("Chemical accuracy unavailable: benchmark row cancelled"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Unscored")).not.toBeInTheDocument();
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
  });

  it("applies molecule actions to all runs in the molecule group", async () => {
    const user = userEvent.setup();
    const onMoleculeAction = vi.fn();
    const grouped = buildGroupedRows();
    const group = grouped[0];
    const firstRow = group?.rows[0];
    if (!group || !firstRow) throw new Error("Expected a benchmark group");

    group.rows = [
      { ...firstRow, status: "running" },
      { ...firstRow, id: "n2:sqd", algorithm: "sqd", status: "running" },
    ];
    renderBenchmarkResultsTable({ grouped, onMoleculeAction });

    await user.click(await screen.findByRole("button", { name: /molecule actions for/i }));
    await user.click(screen.getByRole("button", { name: "Cancel runs" }));
    await user.click(screen.getByRole("button", { name: "Cancel runs" }));

    expect(onMoleculeAction).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: "n2:vqe" }),
        expect.objectContaining({ id: "n2:sqd" }),
      ]),
      "cancel",
    );
  });

  it("does not navigate when a row action cancels a run", async () => {
    const user = userEvent.setup();
    const onRunAction = vi.fn();
    const onBeforeOpenRun = vi.fn();

    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({ status: "running" }),
      onRunAction,
      onBeforeOpenRun,
    });

    await user.click(await screen.findByRole("button", { name: /run actions for vqe/i }));
    await user.click(screen.getByRole("button", { name: "Cancel run" }));
    await user.click(screen.getByRole("button", { name: "Yes, cancel" }));

    expect(onRunAction).toHaveBeenCalledWith(
      expect.objectContaining({ status: "running" }),
      "cancel",
    );
    expect(onBeforeOpenRun).not.toHaveBeenCalled();
    expect(screen.queryByText("Run detail")).not.toBeInTheDocument();
  });

  it("gives benchmark result panels a subtle surfaced outline", async () => {
    renderBenchmarkResultsTable();

    const formula = await screen.findByText(
      "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol;hydrochloride",
    );
    const panel = formula.closest("div.overflow-hidden.rounded-xl");

    expect(panel?.className).toContain("bg-card");
    expect(panel?.className).toContain("shadow-[var(--shadow-surface-panel)]");
  });

  it("runs the pre-navigation hook before opening a run from the benchmark table", async () => {
    const user = userEvent.setup();
    const onBeforeOpenRun = vi.fn();

    renderBenchmarkResultsTable({ onBeforeOpenRun });

    await user.click(await screen.findByText("aaaaaa..."));

    expect(onBeforeOpenRun).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Run detail")).toBeInTheDocument();
  });

  it("offers retry in the row actions menu for failed benchmark runs", async () => {
    const user = userEvent.setup();
    const onRunAction = vi.fn();

    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({
        status: "failed",
        errorMessage: "Solver failed",
      }),
      onRunAction,
    });

    await user.click(await screen.findByRole("button", { name: /run actions for vqe/i }));

    expect(screen.getByRole("button", { name: /retry run/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /resume run/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pause run/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry run/i }));
    expect(await screen.findByText("Retry this run?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^retry$/i }));

    expect(onRunAction).toHaveBeenCalledWith(
      expect.objectContaining({ id: "n2:vqe", status: "failed" }),
      "retry",
    );
  });

  it("shows retry actions for failed benchmark rows even without a run id", async () => {
    const user = userEvent.setup();
    const onRunAction = vi.fn();

    renderBenchmarkResultsTable({
      grouped: buildGroupedRows({
        status: "failed",
        runId: null,
        moleculeId: null,
        errorMessage: "API unavailable",
      }),
      onRunAction,
    });

    await user.click(await screen.findByRole("button", { name: /run actions for vqe/i }));
    expect(screen.getByRole("button", { name: /retry run/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /resume run/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /restart run/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry run/i }));
    await user.click(screen.getByRole("button", { name: /^retry$/i }));

    expect(onRunAction).toHaveBeenCalledWith(
      expect.objectContaining({ id: "n2:vqe", status: "failed", runId: null }),
      "retry",
    );
  });

  it("marks completed but not converged rows with a warning status label", async () => {
    const rootRoute = createRootRoute();
    const groupedRows = buildGroupedRows();
    const firstGroup = groupedRows.at(0);
    if (firstGroup == null) {
      throw new Error("Expected at least one benchmark group");
    }
    const firstRow = firstGroup.rows.at(0);
    if (firstRow == null) {
      throw new Error("Expected at least one benchmark row");
    }
    const preset = firstGroup.preset;
    const benchmarkRoute = createRoute({
      getParentRoute: () => rootRoute,
      path: "/benchmarks",
      component: () => (
        <BenchmarkResultsTable
          grouped={[
            {
              preset,
              rows: [
                {
                  ...firstRow,
                  id: "n2:qfd",
                  algorithm: "qfd",
                  converged: false,
                },
              ],
            },
          ]}
          selectedBasis="sto-3g"
          chemicalAccuracyHa={0.0016}
        />
      ),
    });
    const routeTree = rootRoute.addChildren([benchmarkRoute]);
    const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
    const router = createRouter({ routeTree, history });

    render(<RouterProvider router={router} />);

    expect(
      await screen.findByLabelText("Done, convergence gate not satisfied"),
    ).toBeInTheDocument();
  });

  it("labels timed out benchmark failures distinctly from generic failures", async () => {
    const rootRoute = createRootRoute();
    const groupedRows = buildGroupedRows();
    const firstGroup = groupedRows.at(0);
    if (firstGroup == null) {
      throw new Error("Expected at least one benchmark group");
    }
    const firstRow = firstGroup.rows.at(0);
    if (firstRow == null) {
      throw new Error("Expected at least one benchmark row");
    }
    const benchmarkRoute = createRoute({
      getParentRoute: () => rootRoute,
      path: "/benchmarks",
      component: () => (
        <BenchmarkResultsTable
          grouped={[
            {
              preset: firstGroup.preset,
              rows: [
                {
                  ...firstRow,
                  status: "failed",
                  errorMessage: "Run timed out after reaching the 1h 0m execution limit.",
                },
              ],
            },
          ]}
          selectedBasis="sto-3g"
          chemicalAccuracyHa={0.0016}
        />
      ),
    });
    const routeTree = rootRoute.addChildren([benchmarkRoute]);
    const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
    const router = createRouter({ routeTree, history });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("Timed out")).toBeInTheDocument();
    expect(
      screen.getByText("Run timed out after reaching the 1h 0m execution limit."),
    ).toBeInTheDocument();
    expect(screen.getAllByText("-")).toHaveLength(1);
  });

  it("renders generic failed benchmark rows with dashes instead of pending accuracy cells", async () => {
    const rootRoute = createRootRoute();
    const groupedRows = buildGroupedRows();
    const firstGroup = groupedRows.at(0);
    if (firstGroup == null) {
      throw new Error("Expected at least one benchmark group");
    }
    const firstRow = firstGroup.rows.at(0);
    if (firstRow == null) {
      throw new Error("Expected at least one benchmark row");
    }
    const benchmarkRoute = createRoute({
      getParentRoute: () => rootRoute,
      path: "/benchmarks",
      component: () => (
        <BenchmarkResultsTable
          grouped={[
            {
              preset: firstGroup.preset,
              rows: [
                {
                  ...firstRow,
                  status: "failed",
                  errorMessage: "Solver failed",
                },
              ],
            },
          ]}
          selectedBasis="sto-3g"
          chemicalAccuracyHa={0.0016}
        />
      ),
    });
    const routeTree = rootRoute.addChildren([benchmarkRoute]);
    const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
    const router = createRouter({ routeTree, history });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Solver failed")).toBeInTheDocument();
    expect(screen.getAllByText("-")).toHaveLength(1);
    expect(screen.queryByText("Pending")).not.toBeInTheDocument();
  });
});
