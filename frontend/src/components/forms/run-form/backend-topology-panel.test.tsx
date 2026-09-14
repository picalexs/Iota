import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { BackendTopologyPanel } from "./backend-topology-panel";
import type { BackendDeviceSummary } from "@/types/run";

const detailedDevice: BackendDeviceSummary = {
  name: "ibm_miami",
  simulator: false,
  num_qubits: 4,
  coupling_map: [
    [0, 1],
    [1, 2],
    [2, 3],
  ],
  qubit_errors: [
    { qubit: 0, readout_error: 0.01, t1_us: 100, t2_us: 80, operational: true },
    { qubit: 1, readout_error: 0.02, t1_us: 110, t2_us: 90, operational: true },
    { qubit: 2, readout_error: 0.03, t1_us: 120, t2_us: 95, operational: true },
    { qubit: 3, readout_error: 0.04, t1_us: 130, t2_us: 100, operational: true },
  ],
  gate_errors: [
    { source: 0, target: 1, gate: "cx", error: 0.001, length_ns: 240 },
    { source: 1, target: 2, gate: "cx", error: 0.002, length_ns: 245 },
    { source: 2, target: 3, gate: "cx", error: 0.003, length_ns: 250 },
  ],
};

const aerDevice: BackendDeviceSummary = {
  name: "aer_simulator",
  simulator: true,
  num_qubits: 8,
};

function getQubitMetricTrigger() {
  return document.getElementById("qubit-metric-select") as HTMLButtonElement;
}

function getGraphSortTrigger() {
  return document.getElementById("topology-sort-select") as HTMLButtonElement;
}

describe("BackendTopologyPanel", () => {
  it("defaults qubit color to readout assignment error and omits a none option", async () => {
    const user = userEvent.setup();
    render(<BackendTopologyPanel target="ibm_runtime" device={detailedDevice} mode="execution" />);

    const qubitColorTrigger = getQubitMetricTrigger();
    expect(qubitColorTrigger).toBeInTheDocument();
    expect(qubitColorTrigger).toHaveTextContent(/readout assignment error/i);

    await user.click(qubitColorTrigger);

    expect(screen.getByRole("option", { name: /readout assignment error/i })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /^none$/i })).not.toBeInTheDocument();
  });

  it("keeps the qubit color control stable when switching from IBM runtime to Aer without noise metadata", () => {
    const { rerender } = render(
      <BackendTopologyPanel target="ibm_runtime" device={detailedDevice} mode="execution" />,
    );

    expect(getQubitMetricTrigger()).toHaveTextContent(/readout assignment error/i);

    rerender(<BackendTopologyPanel target="aer_simulator" device={aerDevice} mode="execution" />);

    expect(getQubitMetricTrigger()).toHaveTextContent(/readout assignment error/i);
    expect(screen.getByRole("tab", { name: /map view/i })).toHaveAttribute("aria-selected", "true");
  });

  it("disables graph and table views for aer execution without detailed calibration metadata", () => {
    render(<BackendTopologyPanel target="aer_simulator" device={aerDevice} mode="execution" />);

    expect(screen.getByRole("tab", { name: /graph view/i })).toBeDisabled();
    expect(screen.getByRole("tab", { name: /table view/i })).toBeDisabled();
    expect(
      screen.getByText(
        /enable an ibm-derived noise model when you want graph and table calibration views/i,
      ),
    ).toBeInTheDocument();
  });

  it("uses dark label text for very light qubit fills", () => {
    render(<BackendTopologyPanel target="ibm_runtime" device={detailedDevice} mode="execution" />);

    const lightQubitLabel = screen.getByText("3");
    expect(lightQubitLabel).toHaveAttribute("fill", "#0f172a");
  });

  it("keeps the selected map metric when switching to graph view and uses it for bar heights", async () => {
    const user = userEvent.setup();
    render(<BackendTopologyPanel target="ibm_runtime" device={detailedDevice} mode="execution" />);

    await user.click(getQubitMetricTrigger());
    await user.click(screen.getByRole("option", { name: /t1/i }));
    await user.click(screen.getByRole("tab", { name: /graph view/i }));

    expect(screen.getByText(/t1 lifetime/i)).toBeInTheDocument();
    expect(getGraphSortTrigger()).toHaveTextContent(/metric descending/i);

    const shortBar = screen.getByTestId("topology-graph-bar-0");
    const tallBar = screen.getByTestId("topology-graph-bar-3");

    expect(shortBar.getAttribute("style") ?? "").toContain("height: 12%");
    expect(tallBar.getAttribute("style") ?? "").toContain("height: 100%");
  });
});
