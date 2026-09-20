import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HardwareMappingTile } from "./hardware-mapping-tile";
import { fetchBackendCapabilities } from "@/api/backends";
import type { BackendCapabilitiesResponse } from "@/types/run";
import type { RunExecutionMetadata } from "@/lib/results/execution-metadata";

const capabilities: BackendCapabilitiesResponse = {
  backends: [
    {
      target: "ibm_runtime",
      enabled: true,
      backends: [
        {
          name: "ibm_test",
          simulator: false,
          operational: true,
          num_qubits: 4,
          coupling_map: [
            [0, 1],
            [1, 2],
            [2, 3],
            [0, 2],
          ],
          qubit_errors: [
            { qubit: 0, readout_error: 0.01, t1_us: 120, t2_us: 90 },
            { qubit: 2, readout_error: 0.02, t1_us: 110, t2_us: 95 },
          ],
        },
      ],
    },
  ],
};

vi.mock("@/api/backends", () => ({
  getBackendCapabilitiesCached: vi.fn(() => capabilities),
  fetchBackendCapabilities: vi.fn(() => new Promise<BackendCapabilitiesResponse>(() => {})),
}));

const execution: RunExecutionMetadata = {
  backendName: "ibm_test",
  selectionPolicy: null,
  shots: 1024,
  optimizationLevel: 2,
  aerMethod: null,
  simulatorMethod: null,
  primitiveFamily: "qiskit_ibm_runtime",
  qubits: 2,
  depth: 42,
  twoQubitDepth: 12,
  seedSimulator: null,
  seedTranspiler: null,
  ibmJobId: "job-1",
  ibmStatus: "DONE",
  ibmQueuePosition: null,
  ibmPubCount: 1,
  ibmTiming: null,
  transpilationLayout: [
    { logical: 0, physical: 0 },
    { logical: 1, physical: 2 },
  ],
  usedPhysicalQubits: [0, 2],
};

describe("HardwareMappingTile", () => {
  it("renders the topology map and logical layout table", () => {
    render(<HardwareMappingTile execution={execution} credentialProfileId="profile-1" />);

    expect(screen.getByText("Hardware Mapping")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "IBM Runtime physical qubit map" })).toBeInTheDocument();
    expect(screen.queryByText("Logical to physical")).not.toBeInTheDocument();
    expect(screen.queryByText("q0 → 0")).not.toBeInTheDocument();
    expect(screen.queryByText("q1 → 2")).not.toBeInTheDocument();
    expect(screen.queryByText("0, 2")).not.toBeInTheDocument();
    expect(screen.queryByText("Mapped qubits")).not.toBeInTheDocument();
    expect(screen.queryByText("Device")).not.toBeInTheDocument();
    expect(screen.queryByText("Depth")).not.toBeInTheDocument();
    expect(screen.queryByText("Optimization")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom out hardware map" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zoom in hardware map" })).toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByTestId("hardware-map-node-0"));
    expect(screen.getByText("Logical q0 → Physical 0")).toBeInTheDocument();
    expect(screen.getByText("Mapped from q0")).toBeInTheDocument();
    expect(screen.getByText("RO 0.0100")).toBeInTheDocument();

    fireEvent.mouseLeave(screen.getByTestId("hardware-map-node-0"));
    fireEvent.mouseEnter(screen.getByTestId("hardware-map-node-1"));
    expect(screen.queryByText("Physical qubit 1")).not.toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByTestId("hardware-map-edge-0-1"));
    expect(screen.queryByText("0 ↔ 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Available device connection")).not.toBeInTheDocument();

    fireEvent.mouseEnter(screen.getByTestId("hardware-map-edge-0-2"));
    expect(
      screen
        .getByRole("img", { name: "IBM Runtime physical qubit map" })
        .querySelector('line[stroke="#ef4444"]'),
    ).toBeNull();
    expect(
      screen
        .getByRole("img", { name: "IBM Runtime physical qubit map" })
        .querySelector('line[stroke="#6f8fdc"][stroke-width="7"]'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Layout" }));

    expect(screen.getByText("Logical to physical")).toBeInTheDocument();
    expect(screen.getByText("q0 → 0")).toBeInTheDocument();
    expect(screen.getByText("q1 → 2")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Logical" })).toBeInTheDocument();
    expect(screen.getByText("q0")).toBeInTheDocument();
    expect(screen.getByText("q1")).toBeInTheDocument();
    expect(screen.getByText("0.0100")).toBeInTheDocument();
    expect(screen.getByText("110.00")).toBeInTheDocument();

    expect(vi.mocked(fetchBackendCapabilities)).toHaveBeenCalledWith("profile-1");
  });
});
