import type { LayoutItem } from "react-grid-layout";
import { describe, expect, it } from "vitest";

import { buildResultsDashboardModel } from "./results-dashboard-model";
import type { RunEventResponse, RunResponse } from "@/types/run";

const run: RunResponse = {
  id: "run-1",
  molecule_id: "molecule-1",
  status: "RUNNING",
  algorithm: "qse",
  mode: "advanced",
  backend_target: "statevector",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

const layout: LayoutItem[] = [
  { i: "summary", x: 0, y: 0, w: 6, h: 5 },
  { i: "convergence", x: 6, y: 0, w: 6, h: 5 },
  { i: "hardware-mapping", x: 0, y: 5, w: 8, h: 8 },
  { i: "timeline", x: 0, y: 13, w: 6, h: 6 },
  { i: "benchmark-bars", x: 6, y: 13, w: 6, h: 6 },
  { i: "qse-subspace", x: 0, y: 19, w: 12, h: 8 },
];

const iterationEvents: RunEventResponse[] = [
  {
    id: 1,
    run_id: "run-1",
    sequence: 1,
    type: "iteration_update",
    payload: { iteration: 1, energy: -2.1, hf_energy: -2.2, casci_energy: -2.3 },
    created_at: "2025-06-01T10:01:00Z",
  },
  {
    id: 2,
    run_id: "run-1",
    sequence: 2,
    type: "iteration_update",
    payload: { completed_iterations: 2, energy: -2.2, casci_energy: -2.4 },
    created_at: "2025-06-01T10:02:00Z",
  },
];

function buildModel(overrides: Partial<Parameters<typeof buildResultsDashboardModel>[0]> = {}) {
  return buildResultsDashboardModel({
    run,
    result: null,
    events: [],
    layout,
    moleculePending: false,
    eventsPending: false,
    resultPending: false,
    ...overrides,
  });
}

describe("buildResultsDashboardModel", () => {
  it("keeps live metrics and classical references in one model", () => {
    const model = buildModel({ events: iterationEvents });

    expect(model.currentIteration).toBe(2);
    expect(model.currentEnergy).toBe(-2.2);
    expect(model.liveBestEnergy).toBe(-2.2);
    expect(model.refs).toEqual({ hf: -2.2, fci: -2.4 });
  });

  it("filters the hardware tile for non-IBM runs but keeps it for IBM runs", () => {
    const simulatorModel = buildModel();
    const ibmModel = buildModel({
      run: { ...run, backend_target: "ibm_runtime" },
    });

    expect(simulatorModel.visibleTileIds).not.toContain("hardware-mapping");
    expect(simulatorModel.hiddenLayout).toEqual(
      expect.arrayContaining([expect.objectContaining({ i: "hardware-mapping" })]),
    );
    expect(ibmModel.visibleTileIds).toContain("hardware-mapping");
    expect(ibmModel.activeTiles.has("hardware-mapping")).toBe(true);
  });

  it("assigns pending state to the tiles that depend on each request", () => {
    const model = buildModel({
      moleculePending: true,
      eventsPending: true,
      resultPending: false,
    });

    expect(model.pending).toEqual({
      summary: true,
      convergence: true,
      timeline: true,
      benchmark: true,
      algorithm: false,
    });
  });

  it("normalizes finite SKQD spectrum values for the algorithm tile", () => {
    const model = buildModel({
      run: { ...run, algorithm: "skqd" },
      result: {
        run_id: "run-1",
        energy: -2.2,
        iterations: 2,
        optimal_parameters: [],
        converged: true,
        algorithm_metrics: {
          krylov_extension_diagnostics: {
            ritz_values: [-2.2, "invalid", 0, null],
          },
        },
        created_at: "2025-06-01T10:05:00Z",
      },
    });

    expect(model.parsed.type).toBe("skqd");
    expect(model.skqdSpectrumEnergies).toEqual([-2.2, 0]);
  });
});
