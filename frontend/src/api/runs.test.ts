import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createRun,
  exportRun,
  getRun,
  getRunEvents,
  getRunResult,
  parseRunListResponse,
  parseRunConfigMetadataResponse,
  parseRunResponse,
  parseRunSummaryListResponse,
  validateRunRequest,
} from "./runs";
import { ApiError } from "./http";

function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

const runResponse = {
  id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  molecule_id: "4fa85f64-5717-4562-b3fc-2c963f66afa7",
  status: "CREATED",
  algorithm: "vqe",
  mode: "easy",
  backend_target: "aer_simulator",
  config_json: {},
  execution_generation: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("run API transport adapters", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("rejects malformed generated run envelopes before adaptation", () => {
    expect(() => parseRunResponse({ ...runResponse, status: "BROKEN" })).toThrow(ApiError);
    expect(() => parseRunResponse({ ...runResponse, status: "BROKEN" })).toThrow(
      "Invalid run response",
    );
    expect(() => parseRunListResponse({ items: [runResponse], total: 1 })).toThrow(
      "Invalid run list response",
    );
    expect(() =>
      parseRunSummaryListResponse({
        items: [{ id: runResponse.id, molecule_id: runResponse.molecule_id, status: "BROKEN" }],
        total: 1,
        limit: 20,
        offset: 0,
      }),
    ).toThrow("Invalid run summary list response");
  });

  it("classifies malformed transport bodies as invalid API responses", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse({ ...runResponse, status: "BROKEN" }));

    await expect(getRun(runResponse.id)).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
      message: "Invalid run response",
      status: 0,
    });
  });

  it("validates registry-backed run configuration metadata", () => {
    expect(
      parseRunConfigMetadataResponse({
        algorithms: ["vqe"],
        ansatzes: [{ id: "hardware_efficient", label: "Hardware efficient" }],
        backend_targets: ["statevector"],
        catalog_version: "2026-01",
        easy_goals: ["balanced"],
        easy_goal_presets: [
          { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
        ],
        optimizers: [],
      }),
    ).toMatchObject({ algorithms: ["vqe"], backend_targets: ["statevector"] });
    expect(() =>
      parseRunConfigMetadataResponse({
        algorithms: ["future_algorithm"],
        ansatzes: [],
        backend_targets: ["statevector"],
        catalog_version: "2026-01",
        easy_goals: ["balanced"],
        easy_goal_presets: [
          { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
        ],
        optimizers: [],
      }),
    ).toThrow("Invalid run configuration metadata response");
    expect(() =>
      parseRunConfigMetadataResponse({
        algorithms: ["vqe"],
        ansatzes: [],
        backend_targets: ["statevector"],
        catalog_version: "2026-01",
        easy_goals: ["balanced"],
        easy_goal_presets: [{ goal: "balanced", label: "invalid", chemical_accuracy_target_ha: 0 }],
        optimizers: [],
      }),
    ).toThrow("Invalid run configuration metadata response");
    expect(() =>
      parseRunConfigMetadataResponse({
        algorithms: ["vqe"],
        ansatzes: [],
        backend_targets: ["statevector"],
        catalog_version: "2026-01",
        easy_goals: ["balanced"],
        easy_goal_presets: [
          { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
        ],
        optimizers: [],
        recommendations: { vqe: { balanced: "invalid" } },
      }),
    ).toThrow("Invalid run configuration metadata response");
  });

  it("fills the generated confirmation default without changing the UI input model", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse(runResponse));

    await createRun({
      molecule_id: runResponse.molecule_id,
      algorithm: "vqe",
      mode: "easy",
      backend_target: "aer_simulator",
      easy_options: { goal: "balanced" },
    });

    const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toMatchObject({
      molecule_id: runResponse.molecule_id,
      ibm_runtime_confirmed: false,
    });
  });

  it("normalizes optional validation fields at the response boundary", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse({ valid: true }));

    const result = await validateRunRequest({
      molecule_id: runResponse.molecule_id,
      run: {
        molecule_id: runResponse.molecule_id,
        algorithm: "vqe",
        mode: "easy",
        backend_target: "aer_simulator",
        easy_options: { goal: "balanced" },
      },
    });

    expect(result).toEqual({ valid: true, errors: [], warnings: [], estimate: null });
  });

  it("adapts result and event transport identifiers to the domain types", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        mockResponse({
          run_id: runResponse.id,
          energy: -1.0,
          iterations: 3,
          optimal_parameters: [],
          converged: true,
          algorithm_metrics: { convergence_trace: [-0.8, -1.0] },
          created_at: "2026-01-01T00:00:00Z",
        }),
      )
      .mockResolvedValueOnce(
        mockResponse({
          events: [
            {
              id: 1,
              run_id: runResponse.id,
              sequence: 0,
              type: "status_changed",
              payload: { new_status: "RUNNING" },
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
          last_sequence: 0,
        }),
      );

    const result = await getRunResult(runResponse.id);
    const events = await getRunEvents(runResponse.id, 0);

    expect(result.run_id).toBe(runResponse.id);
    expect(result.algorithm_metrics).toEqual({ convergence_trace: [-0.8, -1.0] });
    expect(events.events[0]?.run_id).toBe(runResponse.id);
    expect(events.last_sequence).toBe(0);
  });

  it("uses the generated ExportBundle response contract", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        export_version: "1.0",
        exported_at: "2026-01-01T00:00:00Z",
        molecule: {},
        events: [],
        result: null,
        run: runResponse,
        versions: null,
      }),
    );

    const result = await exportRun(runResponse.id);

    expect(result.export_version).toBe("1.0");
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/api/runs/${runResponse.id}/export`),
      expect.objectContaining({ method: "GET" }),
    );
  });
});
