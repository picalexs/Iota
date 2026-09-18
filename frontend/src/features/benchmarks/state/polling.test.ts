import { beforeEach, describe, expect, it, vi } from "vitest";
import { getRun, getRunEvents, getRunResult } from "@/api/runs";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { RunResponse, RunResultResponse } from "@/types/run";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import {
  buildInitialEntries,
  type BenchmarkEntry,
  type BenchmarkEntryWithRunId,
} from "@/pages/benchmark/benchmark-utils";
import { buildBenchmarkEntryUpdate, reconcileSavedBenchmarkEntries } from "./polling";

vi.mock("@/api/runs", () => ({
  getRun: vi.fn(),
  getRunEvents: vi.fn(),
  getRunResult: vi.fn(),
}));

const mockedGetRun = vi.mocked(getRun);
const mockedGetRunEvents = vi.mocked(getRunEvents);
const mockedGetRunResult = vi.mocked(getRunResult);

function makeEntry(overrides: Partial<BenchmarkEntry> = {}): BenchmarkEntryWithRunId {
  const entry = buildInitialEntries(
    [BENCHMARK_MOLECULE_PRESETS[0]!],
    [createSimpleBenchmarkVariant("vqe")],
  )[0]!;
  return {
    ...entry,
    status: "running",
    moleculeId: "molecule-id",
    currentEnergy: -1.1,
    latestEventSequence: 1,
    ...overrides,
    runId: overrides.runId ?? "run-id",
  };
}

function makeRun(status: RunResponse["status"], metadata: Record<string, unknown> | null = null) {
  return {
    id: "run-id",
    molecule_id: "molecule-id",
    status,
    algorithm: "vqe",
    mode: "easy",
    backend_target: "statevector",
    config_json: {},
    ibm_job_id: null,
    client_request_id: null,
    versions: null,
    metadata,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:10Z",
  } satisfies RunResponse;
}

function makeResult(overrides: Partial<RunResultResponse> = {}): RunResultResponse {
  return {
    run_id: "run-id",
    energy: -1.137,
    iterations: 4,
    optimal_parameters: [],
    converged: true,
    algorithm_metrics: {
      classical_references: { hf: -1.116, fci: -1.137 },
    },
    created_at: "2026-01-01T00:00:10Z",
    ...overrides,
  };
}

describe("benchmark polling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("merges running progress events without losing the stored run state", async () => {
    mockedGetRun.mockResolvedValueOnce(makeRun("RUNNING", { runtime_seconds: 12 }));
    mockedGetRunEvents.mockResolvedValueOnce({
      events: [
        {
          id: 2,
          run_id: "run-id",
          sequence: 2,
          type: "iteration_update",
          payload: { energy: -1.12, hf_energy: -1.116, casci_energy: -1.137 },
          created_at: "2026-01-01T00:00:08Z",
        },
      ],
      last_sequence: 2,
    });

    await expect(buildBenchmarkEntryUpdate(makeEntry())).resolves.toMatchObject({
      status: "running",
      currentEnergy: -1.12,
      classicalRefs: { hf: -1.116, fci: -1.137 },
      elapsedSeconds: 12,
      latestEventSequence: 2,
    });
    expect(mockedGetRunEvents).toHaveBeenCalledWith("run-id", 1);
    expect(mockedGetRunResult).not.toHaveBeenCalled();
  });

  it("loads the terminal result after the run reaches completed", async () => {
    mockedGetRun.mockResolvedValueOnce(makeRun("COMPLETED"));
    mockedGetRunResult.mockResolvedValueOnce(makeResult());

    await expect(
      buildBenchmarkEntryUpdate(
        makeEntry({
          status: "running",
          energy: null,
          currentEnergy: -1.1,
        }),
      ),
    ).resolves.toMatchObject({
      status: "completed",
      energy: -1.137,
      currentEnergy: -1.137,
      converged: true,
      classicalRefs: { hf: -1.116, fci: -1.137 },
    });
    expect(mockedGetRunEvents).not.toHaveBeenCalled();
  });

  it("recovers classical references from terminal events when the result omits them", async () => {
    mockedGetRun.mockResolvedValueOnce(makeRun("COMPLETED"));
    mockedGetRunResult.mockResolvedValueOnce(
      makeResult({ algorithm_metrics: {} }),
    );
    mockedGetRunEvents.mockResolvedValueOnce({
      events: [
        {
          id: 2,
          run_id: "run-id",
          sequence: 2,
          type: "iteration_update",
          payload: { energy: -1.137, hf_energy: -1.116, casci_energy: -1.137 },
          created_at: "2026-01-01T00:00:08Z",
        },
      ],
      last_sequence: 2,
    });

    await expect(
      buildBenchmarkEntryUpdate(makeEntry({ status: "completed", classicalRefs: null })),
    ).resolves.toMatchObject({
      status: "completed",
      classicalRefs: { hf: -1.116, fci: -1.137 },
      latestEventSequence: 2,
    });
    expect(mockedGetRunEvents).toHaveBeenCalledWith("run-id", 1);
  });

  it("refreshes failed saved rows while leaving terminal successes untouched", async () => {
    const failedEntry = makeEntry({ id: "failed", status: "failed", errorMessage: "old error" });
    const completedEntry = makeEntry({ id: "completed", status: "completed", runId: "run-2" });
    mockedGetRun.mockResolvedValueOnce(
      makeRun("FAILED", { error_message: "worker failed", error_type: "JobError" }),
    );

    const refreshed = await reconcileSavedBenchmarkEntries([failedEntry, completedEntry]);

    expect(refreshed).toEqual([
      expect.objectContaining({ id: "failed", status: "failed", errorMessage: "worker failed" }),
      expect.objectContaining({ id: "completed", status: "completed", runId: "run-2" }),
    ]);
    expect(mockedGetRun).toHaveBeenCalledTimes(1);
    expect(mockedGetRun).toHaveBeenCalledWith("run-id");
  });

  it("can refresh active saved rows when route hydration asks for it", async () => {
    const activeEntry = makeEntry({ status: "queued" });
    mockedGetRun.mockResolvedValueOnce(makeRun("QUEUED"));

    const refreshed = await reconcileSavedBenchmarkEntries([activeEntry], {
      refreshActiveRows: true,
    });

    expect(refreshed[0]).toMatchObject({ id: activeEntry.id, status: "queued" });
    expect(mockedGetRun).toHaveBeenCalledWith("run-id");
  });

  it("refreshes completed saved rows when route hydration asks for it", async () => {
    const completedEntry = makeEntry({ status: "completed", classicalRefs: null });
    mockedGetRun.mockResolvedValueOnce(makeRun("COMPLETED"));
    mockedGetRunResult.mockResolvedValueOnce(makeResult({ algorithm_metrics: {} }));
    mockedGetRunEvents.mockResolvedValueOnce({
      events: [
        {
          id: 2,
          run_id: "run-id",
          sequence: 2,
          type: "iteration_update",
          payload: { hf_energy: -1.116, casci_energy: -1.137 },
          created_at: "2026-01-01T00:00:08Z",
        },
      ],
      last_sequence: 2,
    });

    const refreshed = await reconcileSavedBenchmarkEntries([completedEntry], {
      refreshCompletedRows: true,
    });

    expect(refreshed[0]).toMatchObject({
      status: "completed",
      classicalRefs: { hf: -1.116, fci: -1.137 },
    });
  });
});
