import { describe, expect, it } from "vitest";

import {
  buildActiveTopologyDiagramSvg,
  buildTopologyCalibrationCsv,
} from "./backend-topology-exports";
import { formatMaybeScientific } from "./backend-topology-panel";
import {
  buildMapNodes,
  buildCouplings,
  buildTableRows,
  detectRectangularGridDimensions,
  inferProcessorDescriptor,
  inferTotalQubits,
  metricPercent,
  uniqueCouplings,
} from "./backend-topology-utils";
import type { BackendDeviceSummary } from "@/types/run";

function makeDevice(overrides: Partial<BackendDeviceSummary> = {}): BackendDeviceSummary {
  return {
    name: "ibm_test",
    simulator: false,
    operational: true,
    pending_jobs: 3,
    num_qubits: null,
    basis_gates: null,
    coupling_map: null,
    coupling_map_edges: null,
    max_shots: null,
    error_rate: null,
    processor_type: null,
    qubit_errors: null,
    gate_errors: null,
    ...overrides,
  };
}

describe("backend-topology-panel helpers", () => {
  it("infers total qubits from device metadata and backend target fallbacks", () => {
    expect(inferTotalQubits(makeDevice({ num_qubits: 27 }), "ibm_runtime")).toBe(27);
    expect(
      inferTotalQubits(
        makeDevice({
          qubit_errors: [{ qubit: 4 }],
          coupling_map: [
            [0, 1],
            [1, 2],
          ],
          gate_errors: [{ source: 5, target: 6 }],
        }),
        "ibm_runtime",
      ),
    ).toBe(7);
    expect(inferTotalQubits(null, "aer_simulator")).toBe(8);
    expect(inferTotalQubits(null, "ibm_runtime")).toBeNull();
  });

  it("deduplicates couplings and detects rectangular grids", () => {
    const couplings = uniqueCouplings([
      [0, 1],
      [1, 0],
      [0, 2],
      [1, 3],
      [2, 3],
      [2, 4],
      [3, 5],
      [4, 5],
    ]);

    expect(couplings).toEqual([
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 3],
      [2, 4],
      [3, 5],
      [4, 5],
    ]);
    expect(detectRectangularGridDimensions(6, couplings)).toEqual({ columns: 2, rows: 3 });
    expect(detectRectangularGridDimensions(3, [])).toBeNull();
  });

  it("uses calibrated two-qubit gate endpoints when Runtime omits coupling_map", () => {
    const couplings = buildCouplings(
      makeDevice({
        num_qubits: 4,
        coupling_map: null,
        gate_errors: [
          { source: 0, target: 1, gate: "cz" },
          { source: 1, target: 0, gate: "cx" },
          { source: 1, target: 3, gate: "cz" },
          { source: 3, target: 1, gate: "cx" },
          { source: 0, target: 4, gate: "cz" },
        ],
      }),
      4,
    );

    expect(couplings).toEqual([
      [0, 1],
      [1, 3],
    ]);
  });

  it("builds rectangular and fallback map nodes", () => {
    const rectangularNodes = buildMapNodes(6, [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 3],
      [2, 4],
      [3, 5],
      [4, 5],
    ]);
    const fallbackNodes = buildMapNodes(5, []);
    const firstFallbackNode = fallbackNodes[0];
    const fourthFallbackNode = fallbackNodes[3];
    if (!firstFallbackNode || !fourthFallbackNode) {
      throw new Error("Expected fallback topology nodes");
    }

    expect(rectangularNodes[0]).toMatchObject({ index: 0, x: 42, y: 40 });
    expect(rectangularNodes[5]).toMatchObject({ index: 5 });
    expect(firstFallbackNode.x).toBe(42);
    expect(fourthFallbackNode.x).not.toBe(firstFallbackNode.x);
  });

  it("summarizes processor descriptors for simulators, rectangular devices, and heavy-hex layouts", () => {
    expect(inferProcessorDescriptor(makeDevice({ simulator: true }), 27, [])).toBeNull();

    expect(
      inferProcessorDescriptor(
        makeDevice({
          name: "custom_rect",
          processor_type: { family: "Falcon", revision: "r2" },
        }),
        6,
        [
          [0, 1],
          [0, 2],
          [1, 3],
          [2, 3],
          [2, 4],
          [3, 5],
          [4, 5],
        ],
      ),
    ).toMatchObject({
      family: "Falcon",
      revision: "r2",
      layout: "2 × 3 square lattice",
      ibmUrl: null,
    });

    expect(
      inferProcessorDescriptor(makeDevice({ name: "ibm_heron_candidate" }), 133, []),
    ).toMatchObject({
      layout: "Heavy-hex lattice",
    });
  });

  it("builds table rows, percentages, and formatted calibration exports", () => {
    const tableRows = buildTableRows(
      3,
      [
        [0, 1],
        [1, 2],
      ],
      new Map([
        [0, { qubit: 0, readout_error: 0.01, t1_us: 110, t2_us: 95, operational: true }],
        [1, { qubit: 1, readout_error: 0.015, t1_us: 105, t2_us: 91, operational: true }],
      ]),
      new Map([
        ["0:1", { source: 0, target: 1, gate: "cx", error: 0.02, length_ns: 300 }],
        ["1:2", { source: 1, target: 2, gate: "cz", error: 0.03, length_ns: 450 }],
      ]),
    );

    expect(tableRows[1]).toMatchObject({
      degree: 2,
      bestGateError: 0.02,
      worstGateError: 0.03,
    });
    expect(metricPercent(0.02, { min: 0.01, max: 0.03 })).toBeCloseTo(0.5);
    expect(metricPercent(null, { min: 0.01, max: 0.03 })).toBe(0.05);
    expect(formatMaybeScientific(0.0002)).toBe("2.000e-4");
    expect(formatMaybeScientific(12.34567)).toBe("12.3457");
    expect(formatMaybeScientific(null)).toBe("-");

    const csv = buildTopologyCalibrationCsv(tableRows, [
      { source: 0, target: 1, gate: 'c"x', error: 0.02, length_ns: 300 },
    ]);
    expect(csv).toContain('"record_type","qubit","source"');
    expect(csv).toContain('"qubit","1"');
    expect(csv).toContain('"c""x"');
  });

  it("exports graph and map SVG variants", () => {
    const graphSvg = buildActiveTopologyDiagramSvg({
      activeView: "graph",
      graphRows: [
        {
          qubit: 0,
          readout_error: 0.01,
          t1_us: 100,
          t2_us: 90,
          operational: true,
          degree: 1,
          bestGateError: 0.02,
          worstGateError: 0.02,
        },
      ],
      graphLabelStep: 1,
      graphBarWidth: 16,
      graphCanvasWidth: 120,
      shouldInvertMetricScale: false,
      invert: false,
      qubitMetric: "readout_error",
      metricRange: { min: 0.01, max: 0.03 },
      nodes: [],
      couplings: [],
      gateMetadata: new Map(),
      qubitMetadata: new Map(),
      edgeRange: { min: 0, max: 1 },
      mapOffsetX: 0,
      mapOffsetY: 0,
      width: 120,
      height: 120,
    });

    const mapSvg = buildActiveTopologyDiagramSvg({
      activeView: "map",
      graphRows: [],
      graphLabelStep: 1,
      graphBarWidth: 16,
      graphCanvasWidth: 120,
      shouldInvertMetricScale: false,
      invert: false,
      qubitMetric: "readout_error",
      metricRange: { min: 0.01, max: 0.03 },
      nodes: [
        { index: 0, x: 20, y: 20 },
        { index: 1, x: 60, y: 20 },
      ],
      couplings: [[0, 1]],
      gateMetadata: new Map([["0:1", { source: 0, target: 1, error: 0.02 }]]),
      qubitMetadata: new Map([
        [0, { qubit: 0, readout_error: 0.01, t1_us: 100, t2_us: 90, operational: true }],
        [1, { qubit: 1, readout_error: 0.03, t1_us: 95, t2_us: 88, operational: true }],
      ]),
      edgeRange: { min: 0.01, max: 0.03 },
      mapOffsetX: 5,
      mapOffsetY: 5,
      width: 120,
      height: 120,
    });

    expect(graphSvg).toContain("<rect");
    expect(graphSvg).toContain(">0</text>");
    expect(mapSvg).toContain("<line");
    expect(mapSvg).toContain("<circle");
  });
});
