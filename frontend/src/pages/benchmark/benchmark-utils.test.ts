import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchMolecules, createMolecule, getMolecule, updateMolecule } from "@/api/molecules";
import { createRun } from "@/api/runs";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { RunExecutionMetadata } from "@/lib/results/execution-metadata";
import type { BackendCapability, RunResponse } from "@/types/run";
import {
  acquireMoleculeId,
  extractClassicalRefsFromEvents,
  extractRunErrorMessage,
  filterBenchmarkRows,
  getBenchmarkBackendOptions,
  getBenchmarkAlgorithmBlockers,
  getBenchmarkEligibility,
  getBenchmarkIbmBackends,
  getBenchmarkMoleculeBlocker,
  getBenchmarkStats,
  assessBenchmarkEntry,
  normalizeStoredEntry,
  QUEUED_POLL_INTERVAL_MS,
  RUNNING_POLL_INTERVAL_MS,
  runStatusToEntryStatus,
  resolveBenchmarkBackendNameForMode,
  resolveBenchmarkBackendName,
  shouldPollBenchmarkEntryNow,
  submitBenchmarkEntry,
  sortBenchmarkRows,
  shouldPollEntry,
  shouldSyncBenchmarkEntryEvents,
  type BenchmarkEntry,
} from "./benchmark-utils";

vi.mock("@/api/molecules", () => ({
  createMolecule: vi.fn(),
  fetchMolecules: vi.fn(),
  getMolecule: vi.fn(),
  updateMolecule: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  createRun: vi.fn(),
}));

const preset: MoleculePreset = {
  key: "custom:old-id",
  name: "sodium chloride",
  formula: "NaCl",
  description: "Library molecule",
  atoms: [
    { symbol: "Na", x: 0, y: 0, z: 0 },
    { symbol: "Cl", x: 0, y: 0, z: 2.36 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: { n_electrons: 2, n_orbitals: 2 },
  basis: "sto-3g",
  references: { hf: 0, fci: null, source: "unknown" },
};

function makeEntry(overrides: Partial<BenchmarkEntry>): BenchmarkEntry {
  return {
    id: "entry",
    preset: {
      ...preset,
      key: "h2",
      name: "hydrogen",
      formula: "H2",
      references: { hf: -1.116, fci: -1.137, source: "test" },
    },
    algorithm: "vqe",
    status: "completed",
    moleculeId: "mol-id",
    runId: "run-id",
    energy: -1.1372,
    currentEnergy: -1.1372,
    converged: true,
    errorMessage: null,
    classicalRefs: { hf: -1.116, fci: -1.137 },
    elapsedSeconds: null,
    latestEventSequence: 0,
    ...overrides,
  };
}

function makeExecutionMetadata(overrides: Partial<RunExecutionMetadata> = {}): RunExecutionMetadata {
  return {
    backendName: null,
    selectionPolicy: null,
    shots: null,
    optimizationLevel: null,
    aerMethod: null,
    simulatorMethod: null,
    primitiveFamily: null,
    qubits: null,
    depth: null,
    twoQubitDepth: null,
    seedSimulator: null,
    seedTranspiler: null,
    ibmJobId: null,
    ibmStatus: null,
    ibmQueuePosition: null,
    ibmPubCount: null,
    ibmTiming: null,
    transpilationLayout: [],
    usedPhysicalQubits: [],
    ...overrides,
  };
}

describe("benchmark molecule utilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("does not attach an IBM device to simulator modes", () => {
    const capability: BackendCapability = {
      target: "ibm_runtime",
      enabled: true,
      available: true,
      credential_configured: true,
      backends: [{ name: "ibm_pittsburgh", operational: true }],
    };

    expect(resolveBenchmarkBackendNameForMode("aer_simulator", null, capability)).toBeNull();
    expect(resolveBenchmarkBackendNameForMode("statevector", "ibm_pittsburgh", capability)).toBeNull();
    expect(resolveBenchmarkBackendNameForMode("aer_simulator_backend_noise", null, capability)).toBe(
      "ibm_pittsburgh",
    );
    expect(resolveBenchmarkBackendName("ibm_pittsburgh", capability)).toBe("ibm_pittsburgh");
  });

  it("recreates a custom molecule when the cached UUID no longer exists", async () => {
    localStorage.setItem("benchmark_molecule_ids", JSON.stringify({ [preset.key]: "old-id" }));
    (getMolecule as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("not found"));
    (fetchMolecules as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0 });
    (createMolecule as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "new-id" });

    await expect(acquireMoleculeId(preset)).resolves.toBe("new-id");

    expect(getMolecule).toHaveBeenCalledWith("old-id");
    expect(createMolecule).toHaveBeenCalledWith(
      expect.objectContaining({ name: "sodium chloride", active_space: preset.active_space }),
    );
  });

  it("refreshes cached built-in benchmark molecules when the preset active space changes", async () => {
    const builtInPreset: MoleculePreset = {
      ...preset,
      key: "n2",
      name: "Nitrogen (N₂)",
      formula: "N₂",
      active_space: { n_electrons: 10, n_orbitals: 8 },
    };
    localStorage.setItem(
      "benchmark_molecule_ids",
      JSON.stringify({ [builtInPreset.key]: "n2-id" }),
    );
    (fetchMolecules as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        { id: "n2-id", name: builtInPreset.name, active_space: { n_electrons: 6, n_orbitals: 6 } },
      ],
      total: 1,
    });
    (updateMolecule as ReturnType<typeof vi.fn>).mockResolvedValue({ id: "n2-id" });

    await expect(acquireMoleculeId(builtInPreset)).resolves.toBe("n2-id");

    expect(updateMolecule).toHaveBeenCalledWith("n2-id", {
      active_space: { n_electrons: 10, n_orbitals: 8 },
    });
  });

  it("blocks molecules whose benchmark active space is unknown or invalid", () => {
    expect(getBenchmarkMoleculeBlocker({ ...preset, active_space: null })).toContain(
      "No active space",
    );
    expect(
      getBenchmarkMoleculeBlocker({
        ...preset,
        active_space: { n_electrons: 3, n_orbitals: 13 },
      }),
    ).toContain("Odd active-space");
    expect(getBenchmarkMoleculeBlocker(preset)).toBeNull();
  });

  it("allows large benchmark molecules so VQE and SQD can still run", () => {
    expect(
      getBenchmarkMoleculeBlocker({
        ...preset,
        active_space: { n_electrons: 14, n_orbitals: 13 },
      }),
    ).toBeNull();
  });

  it("keeps KQD and QFD available for large fixed-sector benchmark molecules", () => {
    const blockers = getBenchmarkAlgorithmBlockers([
      { ...preset, formula: "NaCl", active_space: { n_electrons: 8, n_orbitals: 8 } },
    ]);

    expect(blockers.get("kqd")).toBeUndefined();
    expect(blockers.get("qfd")).toBeUndefined();
    expect(blockers.get("qse")).toBeUndefined();
    expect(blockers.get("skqd")).toBeUndefined();
    expect(blockers.get("vqe")).toBeUndefined();
    expect(blockers.get("sqd")).toBeUndefined();
  });

  it("keeps all benchmark algorithms available in Aer backend-noise mode", () => {
    const blockers = getBenchmarkAlgorithmBlockers([preset], "aer_simulator_backend_noise");

    expect(blockers.get("kqd")).toBeUndefined();
    expect(blockers.get("qfd")).toBeUndefined();
    expect(blockers.get("vqe")).toBeUndefined();
    expect(blockers.get("sqd")).toBeUndefined();
    expect(blockers.get("qse")).toBeUndefined();
    expect(blockers.get("skqd")).toBeUndefined();
  });

  it("allows selecting KQD and QFD for large Aer backend-noise benchmarks", () => {
    const blockers = getBenchmarkAlgorithmBlockers(
      [{ ...preset, active_space: { n_electrons: 8, n_orbitals: 8 } }],
      "aer_simulator_backend_noise",
    );

    expect(blockers.get("kqd")).toBeUndefined();
    expect(blockers.get("qfd")).toBeUndefined();
    expect(blockers.get("vqe")).toBeUndefined();
    expect(blockers.get("sqd")).toBeUndefined();
    expect(blockers.get("qse")).toBeUndefined();
    expect(blockers.get("skqd")).toBeUndefined();
  });

  it("enables IBM-backed benchmark modes when operational backends are available", () => {
    const ibmCapability = {
      target: "ibm_runtime",
      enabled: true,
      available: true,
      credential_configured: true,
      supports_noise_profile: false,
      backends: [
        {
          name: "ibm_brisbane",
          operational: true,
        },
      ],
    } satisfies BackendCapability;

    expect(getBenchmarkIbmBackends(ibmCapability).map((backend) => backend.name)).toEqual([
      "ibm_brisbane",
    ]);
    expect(getBenchmarkBackendOptions(ibmCapability)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ value: "aer_simulator_backend_noise", enabled: true }),
        expect.objectContaining({ value: "ibm_runtime", enabled: true }),
      ]),
    );
  });

  it("marks IBM-backed benchmark modes as pending while capability warmup is still in flight", () => {
    expect(getBenchmarkBackendOptions(null, { pending: true })).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          value: "aer_simulator_backend_noise",
          enabled: false,
          label: "Aer simulator with backend noise (Checking IBM...)",
          warning: "Checking IBM backend availability...",
        }),
        expect.objectContaining({
          value: "ibm_runtime",
          enabled: false,
          label: "IBM Quantum backend (Checking IBM...)",
          warning: "Checking IBM backend availability...",
        }),
      ]),
    );
  });

  it("maps paused run statuses distinctly so benchmark polling can stop at safe checkpoints", () => {
    expect(runStatusToEntryStatus({ status: "PAUSING" })).toBe("pausing");
    expect(runStatusToEntryStatus({ status: "PAUSED" })).toBe("paused");
    expect(shouldPollEntry(makeEntry({ status: "pausing" }))).toBe(true);
    expect(shouldPollEntry(makeEntry({ status: "paused" }))).toBe(false);
  });

  it("maps EXCLUDED run status to the excluded entry status", () => {
    expect(runStatusToEntryStatus({ status: "EXCLUDED" })).toBe("excluded");
  });

  it("does not poll persisted planned rows when the API omitted runId", () => {
    const persistedRow = {
      ...makeEntry({ status: "planned", runId: null }),
      runId: undefined,
    } as unknown as BenchmarkEntry;

    const normalized = normalizeStoredEntry(persistedRow);

    expect(normalized.runId).toBeNull();
    expect(shouldPollEntry(normalized)).toBe(false);
  });

  it("normalizes omitted persisted energy values to null", () => {
    const persistedRow = {
      ...makeEntry({ status: "completed" }),
      energy: undefined,
      currentEnergy: undefined,
    } as unknown as BenchmarkEntry;

    const normalized = normalizeStoredEntry(persistedRow);

    expect(normalized.energy).toBeNull();
    expect(normalized.currentEnergy).toBeNull();
  });

  it.each([
    ["vqe", "vqe.easy.balanced", "Balanced"],
    ["sqd", "sqd.easy.fastest", "Quick scan"],
    ["qse", "qse.easy.best_accuracy", "High accuracy"],
  ] as const)(
    "migrates legacy %s variant labels to human-readable names",
    (algorithm, label, expected) => {
      const normalized = normalizeStoredEntry(makeEntry({ algorithm, variantLabel: label }));

      expect(normalized.variantLabel).toBe(expected);
    },
  );

  it("preserves user-defined benchmark variant labels during migration", () => {
    const normalized = normalizeStoredEntry(makeEntry({ variantLabel: "My balanced reference" }));

    expect(normalized.variantLabel).toBe("My balanced reference");
  });

  it("syncs run events only for running benchmark rows", () => {
    expect(shouldSyncBenchmarkEntryEvents("queued")).toBe(false);
    expect(shouldSyncBenchmarkEntryEvents("running")).toBe(true);
    expect(shouldSyncBenchmarkEntryEvents("pausing")).toBe(true);
    expect(shouldSyncBenchmarkEntryEvents("completed")).toBe(false);
  });

  it("polls queued benchmark rows less often than running rows", () => {
    const queuedEntry = makeEntry({ status: "queued" });
    const runningEntry = makeEntry({ status: "running" });
    const queuedPollEveryCycles = Math.round(QUEUED_POLL_INTERVAL_MS / RUNNING_POLL_INTERVAL_MS);

    expect(shouldPollBenchmarkEntryNow(runningEntry, 1)).toBe(true);
    expect(shouldPollBenchmarkEntryNow(queuedEntry, 1)).toBe(false);
    expect(shouldPollBenchmarkEntryNow(queuedEntry, queuedPollEveryCycles)).toBe(true);
  });

  it("uses run-emitted Hamiltonian references for basis-specific benchmark scoring", () => {
    expect(
      extractClassicalRefsFromEvents([
        { payload: { energy: -108.95 } },
        { payload: { hf_energy: -108.94186, casci_energy: -109.02106 } },
      ]),
    ).toEqual({ hf: -108.94186, fci: -109.02106 });
  });

  it("summarizes accurate, not accurate, unscored, and not converged rows separately", () => {
    const entries: BenchmarkEntry[] = [
      makeEntry({ id: "accurate", energy: -1.1372, converged: true }),
      makeEntry({ id: "inaccurate", algorithm: "qse", energy: -1.12, converged: true }),
      makeEntry({
        id: "unscored",
        algorithm: "kqd",
        preset: { ...preset, key: "custom", references: { hf: 0, fci: null, source: "test" } },
        energy: -1.12,
        classicalRefs: null,
      }),
      makeEntry({ id: "not-converged", algorithm: "sqd", energy: -1.1371, converged: false }),
    ];

    expect(getBenchmarkStats(entries, 0.0016)).toMatchObject({
      accurate: 1,
      notAccurate: 1,
      unscored: 2,
      notConverged: 1,
    });
  });

  it("does not score projected diagnostics as benchmark results", () => {
    const entry = makeEntry({
      algorithm: "kqd",
      executionMetadata: makeExecutionMetadata({
        reportedEnergyIsValid: true,
        projectedSolveIsDiagnostic: true,
        scientificConverged: false,
      }),
    });

    expect(getBenchmarkEligibility(entry)).toEqual({
      eligible: false,
      reason: "projected_solve_diagnostic",
    });
    expect(assessBenchmarkEntry(entry, 0.0016).isScorable).toBe(false);
  });

  it("does not score scientifically unconverged results", () => {
    const entry = makeEntry({
      executionMetadata: makeExecutionMetadata({
        reportedEnergyIsValid: true,
        projectedSolveIsDiagnostic: false,
        scientificConverged: false,
      }),
    });

    expect(getBenchmarkEligibility(entry)).toEqual({
      eligible: false,
      reason: "scientific_convergence_not_established",
    });
    expect(assessBenchmarkEntry(entry, 0.0016).verdict).toBe("unscored");
  });

  it("does not fall back to a preset reference for a completed row", () => {
    const entry = makeEntry({ classicalRefs: null });

    expect(getBenchmarkEligibility(entry)).toEqual({
      eligible: false,
      reason: "reference_provenance_unavailable",
    });
    expect(assessBenchmarkEntry(entry, 0.0016).isScorable).toBe(false);
  });

  it("filters and sorts benchmark rows by verdict and absolute error", () => {
    const accurate = makeEntry({ id: "accurate", algorithm: "vqe", energy: -1.1372 });
    const inaccurate = makeEntry({ id: "inaccurate", algorithm: "qse", energy: -1.12 });
    const unscored = makeEntry({
      id: "unscored",
      algorithm: "kqd",
      preset: { ...preset, key: "custom", references: { hf: 0, fci: null, source: "test" } },
      energy: -1.12,
      classicalRefs: null,
    });

    expect(filterBenchmarkRows([accurate, inaccurate, unscored], 0.0016, "accurate")).toEqual([
      accurate,
    ]);

    expect(
      sortBenchmarkRows([inaccurate, accurate, unscored], 0.0016, "lowest_error").map(
        (entry) => entry.id,
      ),
    ).toEqual(["accurate", "inaccurate", "unscored"]);
  });

  it("classifies timeout failures from run metadata with a human-readable message", () => {
    const run = {
      id: "run-id",
      molecule_id: "mol-id",
      status: "FAILED",
      algorithm: "vqe",
      mode: "easy",
      backend_target: "aer_simulator",
      config_json: {},
      basis_set: null,
      ibm_job_id: null,
      client_request_id: null,
      versions: null,
      metadata: {
        error_message: "Run execution failed. Check worker logs for details.",
        error_type: "JobTimeoutException",
        timeout_seconds: 3600,
      },
      initial_estimate: null,
      latest_estimate: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T01:00:00Z",
    } satisfies RunResponse;

    expect(extractRunErrorMessage(run)).toBe(
      "Run timed out after reaching the 1h 0m execution limit.",
    );
  });

  it("retries transient benchmark submission failures with the same client request id", async () => {
    const entry = makeEntry({
      id: "h2:kqd",
      algorithm: "kqd",
      mode: "simple",
      easyOptions: { goal: "balanced" },
      status: "idle",
      moleculeId: null,
      runId: null,
    });
    let entries = [entry];
    const setEntries = (updater: (current: BenchmarkEntry[]) => BenchmarkEntry[]) => {
      entries = updater(entries);
    };

    vi.mocked(createRun)
      .mockRejectedValueOnce(
        Object.assign(new Error("Unable to reach the API. Please try again."), {
          name: "ApiError",
          code: "NETWORK_ERROR",
          status: 0,
        }),
      )
      .mockResolvedValueOnce({
        id: "retried-run",
        molecule_id: "mol-id",
        status: "QUEUED",
        algorithm: "vqe",
        mode: "easy",
        backend_target: "aer_simulator",
        config_json: {},
        ibm_job_id: null,
        client_request_id: null,
        versions: null,
        metadata: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      });

    const result = await submitBenchmarkEntry(
      entry,
      "mol-id",
      "sto-3g",
      { mode: "aer_simulator", backendName: null },
      setEntries,
    );

    expect(result).toMatchObject({
      id: entry.id,
      runId: "retried-run",
      status: "queued",
      errorMessage: null,
    });
    expect(createRun).toHaveBeenCalledTimes(2);
    expect(vi.mocked(createRun).mock.calls[0]?.[0].client_request_id).toBeDefined();
    expect(vi.mocked(createRun).mock.calls[0]?.[0].client_request_id).toBe(
      vi.mocked(createRun).mock.calls[1]?.[0].client_request_id,
    );
    expect(entries[0]).toMatchObject({ status: "queued", runId: "retried-run" });
  });

  it("surfaces a richer row error when benchmark submission fails with a generic server error", async () => {
    const entry = makeEntry({
      id: "h2:kqd",
      algorithm: "kqd",
      mode: "simple",
      easyOptions: { goal: "balanced" },
      status: "idle",
      moleculeId: null,
      runId: null,
    });
    let entries = [entry];
    const setEntries = (updater: (current: BenchmarkEntry[]) => BenchmarkEntry[]) => {
      entries = updater(entries);
    };

    vi.mocked(createRun).mockRejectedValueOnce(
      Object.assign(new Error("An unexpected error occurred"), {
        name: "ApiError",
        code: "UNKNOWN_ERROR",
        status: 500,
      }),
    );

    const result = await submitBenchmarkEntry(
      entry,
      "mol-id",
      "sto-3g",
      { mode: "aer_simulator", backendName: null },
      setEntries,
    );

    expect(result.errorMessage).toBe(
      "The API failed while creating this run (HTTP 500). Refresh Benchmarks or Runs before retrying.",
    );
    expect(entries[0]?.errorMessage).toBe(result.errorMessage);
    expect(entries[0]?.status).toBe("failed");
  });
});
