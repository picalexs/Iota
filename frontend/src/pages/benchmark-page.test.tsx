import "./benchmark-page.test-mocks";

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { runKeys } from "@/hooks/query-keys";
import {
  benchmarkEntry,
  cancelRun,
  completedRun,
  createRun,
  customPausedBenchmarkEntry,
  deleteBenchmarkRun,
  failedBenchmarkEntry,
  fetchMolecules,
  getRun,
  getRunEvents,
  libraryMolecule,
  mockBenchmarkDetail,
  getBenchmarkPageMocks,
  pausedBenchmarkEntry,
  pauseRun,
  renderBenchmarkPage,
  resetBenchmarkPageTestState,
  restartRun,
  restartedRunId,
  resumeRun,
  runId,
  runningRun,
  savedBenchmarkWithEntries,
  selectHydrogen,
} from "./benchmark-page.test-support";

const { invalidateQueries: mockInvalidateQueries } = getBenchmarkPageMocks();

beforeEach(resetBenchmarkPageTestState);

describe("BenchmarkPage workspace", () => {
  it("renders the benchmark workspace on the legacy singular route", async () => {
    renderBenchmarkPage("/benchmark");

    await waitFor(() => expect(screen.getByText("Algorithm Benchmark")).toBeInTheDocument());
  });

  it("starts empty so molecules are added explicitly instead of preselected", async () => {
    localStorage.setItem("benchmark_selected_molecules", JSON.stringify(["h2"]));
    localStorage.setItem("benchmark_selected_algorithms", JSON.stringify(["vqe"]));
    localStorage.setItem("benchmark_entries", JSON.stringify([benchmarkEntry()]));
    localStorage.setItem("benchmark_saved_runs", JSON.stringify([savedBenchmarkWithEntries([])]));

    renderBenchmarkPage();

    expect(await screen.findByText("No molecules selected yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Random 6" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run Benchmark/i })).toBeDisabled();
    expect(localStorage.getItem("benchmark_selected_molecules")).toBeNull();
    expect(localStorage.getItem("benchmark_selected_algorithms")).toBeNull();
    expect(localStorage.getItem("benchmark_entries")).toBeNull();
    expect(localStorage.getItem("benchmark_saved_runs")).toBeNull();

    const randomLibraryMolecules = Array.from({ length: 6 }, (_, index) =>
      libraryMolecule(index + 1),
    );
    const nextRandomLibraryMolecules = Array.from({ length: 6 }, (_, index) =>
      libraryMolecule(index + 7),
    );
    (fetchMolecules as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        items: [randomLibraryMolecules[0]],
        total: randomLibraryMolecules.length,
      })
      .mockResolvedValueOnce({
        items: randomLibraryMolecules,
        total: randomLibraryMolecules.length,
      })
      .mockResolvedValueOnce({
        items: [nextRandomLibraryMolecules[0]],
        total: nextRandomLibraryMolecules.length,
      })
      .mockResolvedValueOnce({
        items: nextRandomLibraryMolecules,
        total: nextRandomLibraryMolecules.length,
      });

    await userEvent.click(screen.getByRole("button", { name: "Random 6" }));

    expect(
      await screen.findByRole("button", { name: /H2-1\s+Library molecule 1/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /H2-6\s+Library molecule 6/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Run Benchmark/i })).toBeEnabled(),
    );

    await userEvent.click(screen.getByRole("button", { name: "Random 6" }));

    expect(
      await screen.findByRole("button", { name: /H2-7\s+Library molecule 7/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /H2-12\s+Library molecule 12/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /H2-1\s+Library molecule 1/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /H2-6\s+Library molecule 6/i }),
    ).not.toBeInTheDocument();
  }, 20_000);

  it("reconciles restored benchmark rows with their run status instead of leaving them waiting", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        benchmarkEntry({
          status: "idle",
        }),
      ]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(getRun).toHaveBeenCalledWith(runId));
    await waitFor(() => expect(screen.getAllByText("Done").length).toBeGreaterThan(0));

    expect(screen.queryByText("Waiting")).not.toBeInTheDocument();
    expect(screen.getByText("-1.137283 Ha")).toBeInTheDocument();
    expect(screen.getByLabelText("Chemically accurate")).toBeInTheDocument();
    expect(screen.queryByText("CASCI refs")).not.toBeInTheDocument();
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
    expect(screen.queryByText(/Reference energies:/)).not.toBeInTheDocument();
  });

  it("shows live benchmark energy from iteration events while a row is running", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue(runningRun);
    (getRunEvents as ReturnType<typeof vi.fn>).mockResolvedValue({
      events: [
        {
          id: 2,
          run_id: runId,
          sequence: 2,
          type: "iteration_update",
          payload: { iteration: 4, energy: -1.125 },
          created_at: "2026-01-01T00:01:00Z",
        },
      ],
      last_sequence: 2,
    });
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(getRun).toHaveBeenCalledWith(runId), { timeout: 5000 });
    expect(await screen.findByText("Running", undefined, { timeout: 5000 })).toBeInTheDocument();
    expect(await screen.findByText("-1.125000 Ha")).toBeInTheDocument();
    expect(screen.getByText("current energy")).toBeInTheDocument();
  });

  it("keeps advanced benchmark drafts editable and hides waiting rows before launch", async () => {
    const user = userEvent.setup();

    renderBenchmarkPage();

    await selectHydrogen();
    await user.click(screen.getByRole("button", { name: /advanced benchmark/i }));

    const addVqeRowButton = await screen.findByRole("button", {
      name: /add vqe comparison row/i,
    });
    expect(addVqeRowButton).toBeEnabled();

    await user.click(addVqeRowButton);

    expect(await screen.findByRole("textbox", { name: /row label/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run benchmark/i })).toBeEnabled();
    expect(screen.queryByText("Waiting")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear results/i })).not.toBeInTheDocument();
  }, 20_000);

  it("does not fetch run events for queued benchmark rows", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...completedRun,
      status: "QUEUED",
    });
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await waitFor(() => expect(getRun).toHaveBeenCalledWith(runId), { timeout: 5000 });
    await waitFor(() => expect(screen.getAllByText("Queued").length).toBeGreaterThan(0));
    expect(getRunEvents).not.toHaveBeenCalled();
  });

  it("keeps restored benchmark configuration locked after cancelling until results are cleared", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => undefined));
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(cancelRun).toHaveBeenCalledWith(runId));
    expect(screen.getAllByText("Cancelled").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Run Benchmark/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Clear results" })).toBeInTheDocument();
  });

  it("lets users pause a restored active benchmark from the workspace controls", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => undefined));
    mockBenchmarkDetail(savedBenchmarkWithEntries([benchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));

    await waitFor(() => expect(pauseRun).toHaveBeenCalledWith(runId));
    expect(await screen.findByRole("button", { name: "Pausing..." })).toBeDisabled();
    expect(screen.getByLabelText("Pausing")).toBeInTheDocument();
  });

  it("shows resume and restart controls when a benchmark row is paused", async () => {
    mockBenchmarkDetail(savedBenchmarkWithEntries([pausedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect(await screen.findByRole("button", { name: "Resume" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Run Benchmark/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear results" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Paused")).toBeInTheDocument();
  });

  it("confirms before clearing completed benchmark results and unlocks editing afterward", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        benchmarkEntry({
          status: "completed",
          energy: -1.137283,
          currentEnergy: -1.137283,
          converged: true,
          classicalRefs: { hf: -1.116, fci: -1.137 },
          elapsedSeconds: 45,
        }),
      ]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect(await screen.findByRole("button", { name: /Run Benchmark/i })).toBeDisabled();

    await userEvent.click(await screen.findByRole("button", { name: "Clear results" }));

    expect(await screen.findByText("Clear benchmark results?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^clear results$/i }));

    await waitFor(() => {
      expect(screen.queryByText("-1.137283 Ha")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Clear results" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Run Benchmark/i })).toBeEnabled();
  });

  it("recovers missing selected custom molecules from saved benchmark entries", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([customPausedBenchmarkEntry()], {
        selectedMoleculeKeys: [],
        customMolecules: [],
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    expect((await screen.findAllByText("Recovered custom molecule")).length).toBeGreaterThan(0);
    expect(screen.queryByText("No molecules selected yet.")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No benchmark rows match the current accuracy filter."),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });

  it("resumes paused benchmark rows from the workspace controls", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue(runningRun);
    mockBenchmarkDetail(savedBenchmarkWithEntries([pausedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: "Resume" }));

    await waitFor(() => expect(resumeRun).toHaveBeenCalledWith(runId));
    await waitFor(() =>
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: runKeys.summariesPrefix,
        refetchType: "all",
      }),
    );
  });

  it("confirms before restarting paused benchmark rows and tracks the child run", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...runningRun,
      id: restartedRunId,
      status: "RUNNING",
    });
    mockBenchmarkDetail(savedBenchmarkWithEntries([pausedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: "Restart" }));

    expect(await screen.findByText("Restart paused benchmark?")).toBeInTheDocument();
    expect(restartRun).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Restart paused rows" }));

    await waitFor(() => expect(restartRun).toHaveBeenCalledWith(runId));
    await waitFor(() => expect(screen.queryByText("Restart this run?")).not.toBeInTheDocument());
  });

  it("retries failed benchmark rows from the row actions menu", async () => {
    (getRun as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...completedRun,
      status: "FAILED",
    });
    mockBenchmarkDetail(savedBenchmarkWithEntries([failedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /run actions for vqe/i }));
    await userEvent.click(screen.getByRole("button", { name: /retry run/i }));

    expect(await screen.findByText("Retry this run?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^retry$/i }));

    await waitFor(() => expect(restartRun).toHaveBeenCalledWith(runId));
    await waitFor(() => expect(screen.queryByText("Retry this run?")).not.toBeInTheDocument());
  });

  it("retries failed benchmark rows without a run id by submitting a fresh run", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([
        failedBenchmarkEntry({
          runId: null,
          moleculeId: null,
          errorMessage: "Unable to reach the API while creating this run.",
        }),
      ]),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /run actions for vqe/i }));
    await userEvent.click(screen.getByRole("button", { name: /retry run/i }));

    expect(await screen.findByText("Retry this run?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^retry$/i }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("aaaaaa...")).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Retry this run?")).not.toBeInTheDocument());
  });

  it("deletes the current saved benchmark from the workspace actions menu", async () => {
    mockBenchmarkDetail(savedBenchmarkWithEntries([pausedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /benchmark actions/i }));
    await userEvent.click(screen.getByRole("button", { name: /delete benchmark/i }));

    const deleteDialog = await screen.findByRole("dialog", { name: /delete this benchmark\?/i });

    await userEvent.click(
      within(deleteDialog).getByRole("button", { name: /^delete benchmark$/i }),
    );

    await waitFor(() =>
      expect(deleteBenchmarkRun).toHaveBeenCalledWith("saved-benchmark-1", {
        deleteAssociatedRuns: false,
      }),
    );
  });

  it("can delete the current saved benchmark together with its associated runs", async () => {
    mockBenchmarkDetail(savedBenchmarkWithEntries([pausedBenchmarkEntry()]));

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /benchmark actions/i }));
    await userEvent.click(screen.getByRole("button", { name: /delete benchmark/i }));

    const deleteDialog = await screen.findByRole("dialog", { name: /delete this benchmark\?/i });
    await userEvent.click(
      within(deleteDialog).getByRole("checkbox", { name: /also delete associated runs/i }),
    );
    await userEvent.click(
      within(deleteDialog).getByRole("button", { name: /^delete benchmark$/i }),
    );

    await waitFor(() =>
      expect(deleteBenchmarkRun).toHaveBeenCalledWith("saved-benchmark-1", {
        deleteAssociatedRuns: true,
      }),
    );
  });
});
