import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BenchmarkSavedRunsList } from "./benchmark-saved-runs-list";
import type { BenchmarkEntry } from "./benchmark-utils";
import type { RunAlgorithm } from "@/types/run";
import type { SavedBenchmarkRun } from "./benchmark-storage";

function benchmarkEntry(status: BenchmarkEntry["status"]): BenchmarkEntry {
  return {
    id: `entry-${status}`,
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
    status,
    moleculeId: null,
    runId: null,
    energy: null,
    currentEnergy: null,
    converged: null,
    errorMessage: null,
    classicalRefs: null,
    elapsedSeconds: null,
    latestEventSequence: 0,
  };
}

function benchmarkEntryWithRun(
  status: BenchmarkEntry["status"],
  runId = "aaaaaaaa-0000-0000-0000-000000000001",
): BenchmarkEntry {
  return {
    ...benchmarkEntry(status),
    runId,
  };
}

function savedRun(
  overrides: Partial<SavedBenchmarkRun> & Pick<SavedBenchmarkRun, "id" | "name" | "entries">,
): SavedBenchmarkRun {
  return {
    createdAt: "2026-06-02T10:00:00.000Z",
    updatedAt: "2026-06-02T10:05:00.000Z",
    selectedMoleculeKeys: ["h2"],
    selectedAlgorithms: ["vqe"] as RunAlgorithm[],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    ...overrides,
  };
}

describe("BenchmarkSavedRunsList", () => {
  it("asks for confirmation before deleting a saved benchmark run", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntry("running")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={onDelete}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /benchmark actions for working benchmark/i }),
    );
    await user.click(screen.getByRole("button", { name: /delete benchmark/i }));

    expect(screen.getByRole("dialog", { name: /delete benchmark run/i })).toBeInTheDocument();
    expect(screen.getByText(/permanently delete "working benchmark"/i)).toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(onDelete).toHaveBeenCalledWith("run-1", { deleteAssociatedRuns: false });
  });

  it("can also delete the associated runs when requested", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntryWithRun("completed")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={onDelete}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /benchmark actions for working benchmark/i }),
    );
    await user.click(screen.getByRole("button", { name: /delete benchmark/i }));
    await user.click(screen.getByRole("checkbox", { name: /also delete associated runs/i }));
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(onDelete).toHaveBeenCalledWith("run-1", { deleteAssociatedRuns: true });
  });

  it("shows whether a benchmark is still running or completed", () => {
    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Running benchmark",
            entries: [benchmarkEntry("running")],
          }),
          savedRun({
            id: "run-2",
            name: "Completed benchmark",
            entries: [benchmarkEntry("completed")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("keeps a benchmark running while at least one row is still active", () => {
    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Mixed benchmark",
            entries: [
              benchmarkEntry("completed"),
              benchmarkEntry("failed"),
              benchmarkEntry("queued"),
            ],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
  });

  it("shows partial once the benchmark has mixed terminal rows", () => {
    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Mixed completed benchmark",
            entries: [benchmarkEntry("completed"), benchmarkEntry("failed")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Partial")).toBeInTheDocument();
  });

  it("keeps a paused benchmark labeled as paused", () => {
    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Paused benchmark",
            entries: [benchmarkEntryWithRun("paused")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Paused")).toBeInTheDocument();
  });

  it("switches rows into selection mode without triggering navigation actions", async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const onToggleSelected = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntry("running")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        selectionMode
        selectedRunIds={new Set<string>()}
        onLoad={onLoad}
        onDelete={vi.fn()}
        onToggleSelected={onToggleSelected}
      />,
    );

    await user.click(screen.getByRole("checkbox", { name: /select working benchmark/i }));

    expect(onToggleSelected).toHaveBeenCalledWith("run-1");
    expect(onLoad).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: /benchmark actions for working benchmark/i }),
    ).not.toBeInTheDocument();
  });

  it("renders selection controls below the toolbar and above the table", () => {
    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntry("running")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        toolbarContent={<div>Toolbar content</div>}
        selectionContent={<div>Selection controls</div>}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const toolbar = screen.getByText("Toolbar content");
    const selection = screen.getByText("Selection controls");
    const row = screen.getByText("Working benchmark");

    expect(
      toolbar.compareDocumentPosition(selection) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(selection.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("surfaces sortable column headers", async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntry("running")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        sortField="updated"
        sortOrder="desc"
        onLoad={vi.fn()}
        onDelete={vi.fn()}
        onSort={onSort}
      />,
    );

    await user.click(screen.getByRole("button", { name: /sort by name/i }));

    expect(onSort).toHaveBeenCalledWith("name");
  });

  it("shows benchmark control actions in the menu instead of open benchmark", async () => {
    const user = userEvent.setup();
    const onRunAction = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Paused benchmark",
            entries: [benchmarkEntryWithRun("paused")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={vi.fn()}
        onDelete={vi.fn()}
        onRunAction={onRunAction}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /benchmark actions for paused benchmark/i }),
    );

    expect(screen.queryByRole("button", { name: /open benchmark/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /resume benchmark/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /restart benchmark/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel benchmark/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /resume benchmark/i }));

    expect(onRunAction).toHaveBeenCalledWith(expect.objectContaining({ id: "run-1" }), "resume");
  });

  it("opens a saved benchmark when the row is clicked", async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();

    render(
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={[
          savedRun({
            id: "run-1",
            name: "Working benchmark",
            entries: [benchmarkEntry("running")],
          }),
        ]}
        selectedSavedBenchmarkId={null}
        onLoad={onLoad}
        onDelete={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Working benchmark"));

    expect(onLoad).toHaveBeenCalledWith("run-1");
  });
});
