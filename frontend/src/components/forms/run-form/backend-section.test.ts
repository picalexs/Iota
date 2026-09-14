import { describe, expect, it } from "vitest";

import {
  buildMapNodes,
  detectRectangularGridDimensions,
  hasDetailedTopologyMetrics,
  inferProcessorDescriptor,
} from "./backend-topology-utils";
import { buildTopologyCalibrationCsv } from "./backend-topology-exports";
import { positionTopologyHoverBubble } from "@/components/topology/topology-map-svg";

function buildRectangularGridCouplings(columns: number, rows: number): number[][] {
  const couplings: number[][] = [];

  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const index = row * columns + column;

      if (column + 1 < columns) {
        couplings.push([index, index + 1]);
      }
      if (row + 1 < rows) {
        couplings.push([index, index + columns]);
      }
    }
  }

  return couplings;
}

describe("backend topology layout helpers", () => {
  it("detects row-major rectangular lattice dimensions from backend couplings", () => {
    const couplings = buildRectangularGridCouplings(10, 12);

    expect(detectRectangularGridDimensions(120, couplings)).toEqual({
      columns: 10,
      rows: 12,
    });
  });

  it("lays out rectangular lattice backends as a true matrix grid", () => {
    const couplings = buildRectangularGridCouplings(10, 12);
    const nodes = buildMapNodes(120, couplings);
    const nodeByIndex = new Map(nodes.map((node) => [node.index, node]));
    const edgeLengths = couplings.map((coupling) => {
      const [source, target] = coupling;
      if (source === undefined || target === undefined) {
        throw new Error("Expected two node indices for every coupling");
      }
      const start = nodeByIndex.get(source);
      const end = nodeByIndex.get(target);
      if (!start || !end) {
        throw new Error("Expected topology nodes for every coupling");
      }
      return Math.hypot(start.x - end.x, start.y - end.y);
    });

    expect(nodes).toHaveLength(120);
    expect(nodes[1]?.y).toBe(nodes[0]?.y);
    expect(nodes[10]?.x).toBe(nodes[0]?.x);
    expect(Math.max(...edgeLengths)).toBeLessThan(80);
  });

  it("infers Nighthawk family metadata and IBM link for ibm_miami", () => {
    const couplings = buildRectangularGridCouplings(10, 12);

    expect(
      inferProcessorDescriptor(
        {
          name: "ibm_miami",
          simulator: false,
          num_qubits: 120,
        },
        120,
        couplings,
      ),
    ).toEqual({
      family: "Nighthawk",
      revision: null,
      layout: "10 x 12 square lattice",
      ibmUrl: "https://quantum.cloud.ibm.com/computers?tab=systems&system=ibm_miami",
    });
  });

  it("prefers backend processor_type metadata when available", () => {
    const descriptor = inferProcessorDescriptor(
      {
        name: "ibm_pittsburgh",
        simulator: false,
        num_qubits: 156,
        processor_type: {
          family: "Heron",
          revision: "r3",
        },
      },
      156,
      [],
    );

    expect(descriptor?.family).toBe("Heron");
    expect(descriptor?.revision).toBe("r3");
  });

  it("uses the known IBM coordinate family for 156-qubit devices", () => {
    const nodes = buildMapNodes(156, []);

    expect(nodes).toHaveLength(156);
    expect(nodes[15]?.y).toBe(nodes[0]?.y);
    expect(nodes[15]?.x).toBeGreaterThan(nodes[0]?.x ?? 0);
    expect(nodes[16]?.y).toBeGreaterThan(nodes[0]?.y ?? 0);
  });

  it("keeps synthetic fallback edges short when topology metadata is absent", () => {
    const couplings: number[][] = [];
    for (let index = 0; index < 156; index += 1) {
      const column = index % 18;
      if (column < 17 && index + 1 < 156) {
        couplings.push([index, index + 1]);
      }
      if ((column % 4 === 1 || column % 4 === 3) && index + 18 < 156) {
        couplings.push([index, index + 18]);
      }
    }

    const nodes = buildMapNodes(156, couplings, false);
    const nodeByIndex = new Map(nodes.map((node) => [node.index, node]));
    const edgeLengths = couplings.map(([source, target]) => {
      if (source === undefined || target === undefined) {
        throw new Error("Expected two endpoints for every fallback coupling");
      }
      const start = nodeByIndex.get(source);
      const end = nodeByIndex.get(target);
      if (!start || !end) {
        throw new Error("Expected a node for every fallback coupling endpoint");
      }
      return Math.hypot(start.x - end.x, start.y - end.y);
    });

    expect(Math.max(...edgeLengths)).toBeLessThan(80);
  });

  it("positions the topology hover bubble above the hovered point when there is room", () => {
    expect(
      positionTopologyHoverBubble({
        anchorX: 200,
        anchorY: 150,
        bubbleWidth: 120,
        bubbleHeight: 60,
        width: 760,
        height: 360,
      }),
    ).toEqual({
      x: 140,
      y: 72,
      width: 120,
      height: 60,
    });
  });

  it("repositions the topology hover bubble below and inside bounds near the top edge", () => {
    expect(
      positionTopologyHoverBubble({
        anchorX: 24,
        anchorY: 30,
        bubbleWidth: 180,
        bubbleHeight: 56,
        width: 220,
        height: 140,
      }),
    ).toEqual({
      x: 8,
      y: 48,
      width: 180,
      height: 56,
    });
  });

  it("detects when detailed topology metrics are unavailable", () => {
    expect(
      hasDetailedTopologyMetrics({
        name: "aer_simulator",
        simulator: true,
      }),
    ).toBe(false);

    expect(
      hasDetailedTopologyMetrics({
        name: "ibm_boston",
        simulator: false,
        qubit_errors: [
          {
            qubit: 0,
            readout_error: 0.01,
            t1_us: 120,
            t2_us: 90,
            operational: true,
          },
        ],
      }),
    ).toBe(true);
  });

  it("serializes qubit and gate calibration data to csv", () => {
    const csv = buildTopologyCalibrationCsv(
      [
        {
          qubit: 0,
          readout_error: 0.01,
          t1_us: 100,
          t2_us: 80,
          operational: true,
          degree: 2,
          bestGateError: 0.001,
          worstGateError: 0.003,
        },
      ],
      [
        {
          source: 0,
          target: 1,
          gate: "cx",
          error: 0.002,
          length_ns: 245,
        },
      ],
    );

    expect(csv).toContain('"record_type","qubit","source","target"');
    expect(csv).toContain('"qubit","0","","","0.01","100","80","2","0.001","0.003","true"');
    expect(csv).toContain('"gate","","0","1"');
  });
});
