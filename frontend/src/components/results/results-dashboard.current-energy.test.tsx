import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ResultsDashboard } from "./results-dashboard";
import type { MoleculeResponse, RunEventResponse, RunResponse } from "@/types/run";

type SummaryMetricKey =
  | "currentEnergy"
  | "currentIteration"
  | "liveBestEnergy"
  | "chemicalAccuracyHa";
type SummaryTileProps = Partial<Record<SummaryMetricKey, number | null>>;

let summaryProps: SummaryTileProps | null = null;

function capturedSummaryProps(): SummaryTileProps {
  if (!summaryProps) {
    throw new Error("Summary props were not captured");
  }
  return summaryProps;
}

function capturedSummaryMetric(key: SummaryMetricKey): number | null | undefined {
  return capturedSummaryProps()[key];
}

vi.mock("./dashboard-grid", () => ({
  DashboardGrid: ({ children }: { readonly children: ReactNode }) => (
    <div data-testid="grid">{children}</div>
  ),
}));

vi.mock("./tiles/summary-tile", () => ({
  SummaryTile: (props: SummaryTileProps) => {
    summaryProps = props;
    return <div>Summary tile</div>;
  },
}));
vi.mock("./tiles/convergence-tile", () => ({
  ConvergenceTile: () => <div>Convergence tile</div>,
}));
vi.mock("./tiles/benchmark-bars-tile", () => ({
  BenchmarkBarsTile: () => <div>Benchmark tile</div>,
}));
vi.mock("./tiles/hardware-mapping-tile", () => ({
  HardwareMappingTile: () => <div>Hardware mapping tile</div>,
}));
vi.mock("./tiles/vqe-parameters-tile", () => ({
  VqeParametersTile: () => <div>VQE tile</div>,
}));
vi.mock("./tiles/circuit-artifacts-tile", () => ({
  CircuitArtifactsTile: ({ title }: { title: string }) => <div>{title}</div>,
}));
vi.mock("./tiles/sqd-occupancy-tile", () => ({
  SqdOccupancyTile: () => <div>SQD occupancy tile</div>,
}));
vi.mock("./tiles/sqd-recovery-tile", () => ({
  SqdRecoveryTile: () => <div>SQD recovery tile</div>,
}));
vi.mock("./tiles/kqd-ritz-tile", () => ({
  KqdRitzTile: () => <div>KQD tile</div>,
}));
vi.mock("./tiles/qfd-spectrum-tile", () => ({
  QfdSpectrumTile: () => <div>QFD tile</div>,
}));
vi.mock("./tiles/qse-subspace-tile", () => ({
  QseSubspaceTile: () => <div>QSE subspace tile</div>,
}));
vi.mock("./tiles/spectral-gaps-tile", () => ({
  SpectralGapsTile: () => <div>Spectral gaps tile</div>,
}));
vi.mock("./tiles/skqd-diagnostics-tile", () => ({
  SkqdDiagnosticsTile: () => <div>SKQD tile</div>,
}));
vi.mock("./tiles/skqd-spectrum-tile", () => ({
  SkqdSpectrumTile: () => <div>SKQD spectrum tile</div>,
}));
vi.mock("./tiles/export-tile", () => ({
  ExportDropdown: () => <div>Export</div>,
}));
vi.mock("./tiles/timeline-tile", () => ({
  TimelineTile: () => <div>Timeline tile</div>,
}));

const run: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "RUNNING",
  algorithm: "qfd",
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

const molecule: MoleculeResponse = {
  id: "mol-1",
  name: "N2",
  atoms: [],
  basis_set: "6-31g*",
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:00:00Z",
};

describe("ResultsDashboard current energy", () => {
  it("keeps the last numeric live energy when the final QFD event has no energy", () => {
    summaryProps = null;
    const events: RunEventResponse[] = [
      {
        id: 1,
        run_id: "run-1",
        sequence: 1,
        type: "iteration_update",
        payload: { iteration: 1, energy: -108.94 },
        created_at: "2025-06-01T10:01:00Z",
      },
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "iteration_update",
        payload: {
          step: "hardware_matrix_elements",
          iteration: 2,
          completed_iterations: 2,
          total_iterations: 8,
          energy: -99.0,
          matrix_element_value: -99.0,
        },
        created_at: "2025-06-01T10:02:00Z",
      },
    ];

    render(<ResultsDashboard run={run} result={null} events={events} molecule={molecule} />);

    expect(screen.getByText("Summary tile")).toBeInTheDocument();
    expect(capturedSummaryMetric("currentEnergy")).toBe(-108.94);
    expect(capturedSummaryMetric("liveBestEnergy")).toBe(-108.94);
    expect(capturedSummaryMetric("currentIteration")).toBe(2);
  });

  it("passes the best live energy to the summary tile separately from the latest point", () => {
    summaryProps = null;
    const events: RunEventResponse[] = [
      {
        id: 1,
        run_id: "run-1",
        sequence: 1,
        type: "iteration_update",
        payload: { iteration: 1, energy: -108.96 },
        created_at: "2025-06-01T10:01:00Z",
      },
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "iteration_update",
        payload: { iteration: 2, energy: -108.94 },
        created_at: "2025-06-01T10:02:00Z",
      },
    ];

    render(<ResultsDashboard run={run} result={null} events={events} molecule={molecule} />);

    expect(capturedSummaryMetric("currentEnergy")).toBe(-108.94);
    expect(capturedSummaryMetric("liveBestEnergy")).toBe(-108.96);
  });

  it("passes the per-run chemical accuracy threshold to the summary tile", () => {
    summaryProps = null;

    render(
      <ResultsDashboard
        run={{
          ...run,
          config_json: { chemical_accuracy_target_ha: 0.0025 },
        }}
        result={null}
        events={[]}
        molecule={molecule}
      />,
    );

    expect(capturedSummaryMetric("chemicalAccuracyHa")).toBe(0.0025);
  });
});
