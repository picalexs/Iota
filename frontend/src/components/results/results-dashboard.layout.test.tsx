import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import type { LayoutItem } from "react-grid-layout";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResultsDashboard } from "./results-dashboard";
import type { MoleculeResponse, RunResponse, RunResultResponse } from "@/types/run";

vi.mock("./dashboard-grid", () => ({
  DashboardGrid: ({
    layout,
    layoutKey,
    children,
  }: {
    layout: LayoutItem[];
    layoutKey?: string;
    children: ReactNode;
  }) => (
    <div data-layout={JSON.stringify(layout)} data-layout-key={layoutKey} data-testid="grid">
      {children}
    </div>
  ),
}));

vi.mock("./tiles/summary-tile", () => ({
  SummaryTile: () => <div>Summary tile</div>,
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
  status: "COMPLETED",
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

const result: RunResultResponse = {
  run_id: "run-1",
  energy: -108.2,
  iterations: 3,
  optimal_parameters: [],
  converged: false,
  algorithm_metrics: {
    eigenvalues: [-108.2, -107.9],
  },
  created_at: "2025-06-01T10:05:00Z",
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

function gridLayout(): LayoutItem[] {
  return JSON.parse(screen.getByTestId("grid").dataset.layout ?? "[]");
}

describe("ResultsDashboard layout reset", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("does not render removed VQE state-visualization tiles", () => {
    const vqeRun: RunResponse = {
      ...run,
      algorithm: "vqe",
    };
    const vqeResult: RunResultResponse = {
      ...result,
      algorithm_metrics: {
        convergence_trace: [-108.2, -108.3],
        bloch_vectors: [[0, 0, 1]],
        density_matrix_real: [
          [1, 0],
          [0, 0],
        ],
        density_matrix_imag: [
          [0, 0],
          [0, 0],
        ],
      },
    };

    render(<ResultsDashboard run={vqeRun} result={vqeResult} events={[]} molecule={molecule} />);

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "vqe:0:summary,convergence,timeline,benchmark-bars,vqe-circuit",
    );
    expect(gridLayout().find((item) => item.i === "vqe-circuit")).toMatchObject({
      x: 0,
      y: 11,
      w: 12,
      h: 7,
    });
    expect(screen.queryByText("Bloch sphere tile")).not.toBeInTheDocument();
    expect(screen.queryByText("Density matrix tile")).not.toBeInTheDocument();
  });

  it("migrates legacy circuit-heavy layouts and still resets from the toolbar", () => {
    localStorage.setItem(
      "vqe-studio:results-layout:v14:qse:default",
      JSON.stringify([
        { i: "summary", x: 0, y: 0, w: 6, h: 5 },
        { i: "convergence", x: 6, y: 0, w: 6, h: 5 },
        { i: "benchmark-bars", x: 6, y: 5, w: 6, h: 4 },
        { i: "timeline", x: 0, y: 5, w: 6, h: 6 },
        { i: "qse-subspace", x: 6, y: 9, w: 2, h: 1 },
      ]),
    );

    render(<ResultsDashboard run={run} result={result} events={[]} molecule={molecule} />);

    expect(gridLayout().find((item) => item.i === "benchmark-bars")).toMatchObject({
      x: 6,
      y: 5,
      w: 6,
      h: 6,
    });
    expect(gridLayout().find((item) => item.i === "qse-subspace")).toMatchObject({
      x: 0,
      y: 11,
      w: 12,
      h: 8,
    });

    expect(screen.queryByRole("button", { name: "Reset layout" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit layout" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset layout" }));

    expect(gridLayout().find((item) => item.i === "qse-subspace")).toMatchObject({
      x: 0,
      y: 11,
      w: 12,
      h: 8,
    });
    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "qse:1:summary,convergence,timeline,benchmark-bars,qse-subspace,qse-circuit,spectral-gaps",
    );
    expect(screen.getByText("QSE subspace tile")).toBeInTheDocument();
    expect(screen.getByText("QSE Reference Circuit")).toBeInTheDocument();
  });

  it("sanitizes invalid saved layouts before compacting the dashboard grid", () => {
    localStorage.setItem(
      "vqe-studio:results-layout:v14:qse:default",
      JSON.stringify([
        { i: "summary", x: 999999, y: 999999, w: 999999, h: 999999 },
        { i: "convergence", x: -4, y: 0, w: 6, h: 5 },
        { i: "timeline", x: 0, y: 12, w: 6, h: Number.POSITIVE_INFINITY },
        { i: "benchmark-bars", x: 6, y: 5, w: 6, h: 4 },
        { i: "qse-subspace", x: 6, y: 9, w: 2, h: 1 },
        { i: "removed-tile", x: 0, y: 0, w: 12, h: 1 },
      ]),
    );

    render(<ResultsDashboard run={run} result={result} events={[]} molecule={molecule} />);

    expect(gridLayout().find((item) => item.i === "summary")).toMatchObject({
      x: 0,
      y: 0,
      w: 6,
      h: 5,
    });
    expect(gridLayout().find((item) => item.i === "convergence")).toMatchObject({
      x: 6,
      y: 0,
      w: 6,
      h: 5,
    });
    expect(gridLayout().find((item) => item.i === "timeline")).toMatchObject({
      x: 0,
      y: 5,
      w: 6,
      h: 6,
    });
    expect(gridLayout().find((item) => item.i === "qse-subspace")).toMatchObject({
      x: 0,
      y: 11,
      w: 12,
      h: 8,
    });
    expect(gridLayout().find((item) => item.i === "removed-tile")).toBeUndefined();
  });

  it("compacts the initial non-IBM layout so visible tiles start at the top", () => {
    render(<ResultsDashboard run={run} result={null} events={[]} molecule={molecule} />);

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "qse:0:summary,convergence,timeline,benchmark-bars,qse-subspace,qse-circuit,spectral-gaps",
    );
    expect(gridLayout()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ i: "summary", x: 0, y: 0 }),
        expect.objectContaining({ i: "convergence", x: 6, y: 0 }),
        expect.objectContaining({ i: "timeline", x: 0, y: 5, w: 6, h: 6 }),
        expect.objectContaining({ i: "benchmark-bars", x: 6, y: 5, w: 6, h: 6 }),
        expect.objectContaining({ i: "qse-subspace", x: 0, y: 11, w: 12, h: 8 }),
        expect.objectContaining({ i: "qse-circuit", x: 0, y: 19, w: 12, h: 7 }),
        expect.objectContaining({ i: "spectral-gaps", x: 0, y: 26, w: 12, h: 5 }),
      ]),
    );
    expect(screen.getByText("Benchmark tile")).toBeInTheDocument();
    expect(screen.getByText("QSE subspace tile")).toBeInTheDocument();
    expect(screen.getByText("QSE Reference Circuit")).toBeInTheDocument();
  });

  it("keeps SQD-specific tiles visible before and after result data arrives", () => {
    const sqdRun: RunResponse = {
      ...run,
      algorithm: "sqd",
    };
    const sqdResult: RunResultResponse = {
      ...result,
      algorithm_metrics: {
        sci_energies: [-108.2, -108.1],
        configuration_recovery_trace: [],
        spin_diagnostics: {},
      },
    };

    const { rerender } = render(
      <ResultsDashboard run={sqdRun} result={null} events={[]} molecule={molecule} />,
    );

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "sqd:0:summary,convergence,timeline,benchmark-bars,sqd-occupancy,sqd-recovery",
    );
    expect(gridLayout().find((item) => item.i === "sqd-recovery")).toMatchObject({
      x: 0,
      y: 11,
      w: 12,
      h: 8,
    });
    expect(gridLayout().find((item) => item.i === "sqd-occupancy")).toMatchObject({
      x: 0,
      y: 19,
      w: 12,
      h: 4,
    });
    expect(screen.getByText("Benchmark tile")).toBeInTheDocument();
    expect(screen.getByText("SQD occupancy tile")).toBeInTheDocument();
    expect(screen.getByText("SQD recovery tile")).toBeInTheDocument();

    rerender(<ResultsDashboard run={sqdRun} result={sqdResult} events={[]} molecule={molecule} />);

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "sqd:0:summary,convergence,timeline,benchmark-bars,sqd-occupancy,sqd-recovery",
    );
    expect(gridLayout().find((item) => item.i === "sqd-occupancy")).toMatchObject({
      x: 0,
      y: 19,
      w: 12,
      h: 4,
    });
    expect(screen.getByText("SQD occupancy tile")).toBeInTheDocument();
    expect(screen.getByText("SQD recovery tile")).toBeInTheDocument();
  });

  it.each([
    {
      algorithm: "kqd" as const,
      expected: [
        { i: "kqd-ritz", x: 0, y: 11, w: 12, h: 8 },
        { i: "kqd-circuit", x: 0, y: 19, w: 12, h: 7 },
        { i: "spectral-gaps", x: 0, y: 26, w: 12, h: 5 },
      ],
      labels: ["KQD tile", "KQD Circuit", "Spectral gaps tile"],
    },
    {
      algorithm: "qfd" as const,
      expected: [
        { i: "qfd-spectrum", x: 0, y: 11, w: 6, h: 5 },
        { i: "spectral-gaps", x: 6, y: 11, w: 6, h: 5 },
      ],
      labels: ["QFD tile", "Spectral gaps tile"],
    },
    {
      algorithm: "skqd" as const,
      expected: [
        { i: "skqd-diagnostics", x: 0, y: 11, w: 12, h: 8 },
        { i: "skqd-circuit", x: 0, y: 19, w: 12, h: 7 },
        { i: "skqd-spectrum", x: 0, y: 26, w: 6, h: 5 },
        { i: "spectral-gaps", x: 6, y: 26, w: 6, h: 5 },
      ],
      labels: ["SKQD spectrum tile", "SKQD tile", "SKQD Seed Circuit", "Spectral gaps tile"],
    },
  ])(
    "keeps the taller benchmark row aligned for $algorithm layouts",
    ({ algorithm, expected, labels }) => {
      render(
        <ResultsDashboard
          run={{ ...run, algorithm }}
          result={result}
          events={[]}
          molecule={molecule}
        />,
      );

      expect(gridLayout().find((item) => item.i === "timeline")).toMatchObject({
        x: 0,
        y: 5,
        w: 6,
        h: 6,
      });
      expect(gridLayout().find((item) => item.i === "benchmark-bars")).toMatchObject({
        x: 6,
        y: 5,
        w: 6,
        h: 6,
      });
      for (const item of expected) {
        expect(gridLayout().find((layoutItem) => layoutItem.i === item.i)).toMatchObject(item);
      }
      for (const label of labels) {
        expect(screen.getByText(label)).toBeInTheDocument();
      }
    },
  );

  it("uses the IBM preset and shows the hardware mapping tile before layout data arrives", () => {
    const ibmRun: RunResponse = {
      ...run,
      backend_target: "ibm_runtime",
    };
    const ibmResult: RunResultResponse = {
      ...result,
      algorithm_metrics: {
        ...result.algorithm_metrics,
        backend_execution: {
          backend_name: "ibm_brisbane",
          transpilation_summary: {
            final_layout: [112, 113, 118, 119],
            used_physical_qubits: [112, 113, 118, 119],
          },
        },
      },
    };

    const { rerender } = render(
      <ResultsDashboard run={ibmRun} result={null} events={[]} molecule={molecule} />,
    );

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "qse:0:summary,convergence,hardware-mapping,timeline,benchmark-bars,qse-subspace,qse-circuit,spectral-gaps",
    );
    expect(gridLayout().find((item) => item.i === "hardware-mapping")).toMatchObject({
      x: 4,
      w: 8,
      h: 7,
    });
    expect(gridLayout().find((item) => item.i === "qse-subspace")).toMatchObject({
      x: 0,
      y: 20,
      w: 12,
      h: 8,
    });
    expect(gridLayout().find((item) => item.i === "qse-circuit")).toMatchObject({
      x: 0,
      y: 28,
      w: 12,
      h: 7,
    });
    expect(gridLayout().find((item) => item.i === "summary")).toMatchObject({ h: 7 });
    expect(gridLayout().find((item) => item.i === "convergence")).toMatchObject({ h: 7 });
    expect(screen.getByText("Hardware mapping tile")).toBeInTheDocument();

    rerender(<ResultsDashboard run={ibmRun} result={ibmResult} events={[]} molecule={molecule} />);

    expect(screen.getByTestId("grid")).toHaveAttribute(
      "data-layout-key",
      "qse:0:summary,convergence,hardware-mapping,timeline,benchmark-bars,qse-subspace,qse-circuit,spectral-gaps",
    );
    expect(gridLayout().find((item) => item.i === "qse-subspace")).toMatchObject({
      x: 0,
      y: 20,
      w: 12,
      h: 8,
    });
    expect(gridLayout().find((item) => item.i === "qse-circuit")).toMatchObject({
      x: 0,
      y: 28,
      w: 12,
      h: 7,
    });
    expect(gridLayout().find((item) => item.i === "spectral-gaps")).toMatchObject({
      x: 6,
      y: 14,
      w: 6,
      h: 5,
    });
  });
});
