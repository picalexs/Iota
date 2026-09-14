import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { VqeParametersTile } from "./vqe-parameters-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/measurement-outcomes-panel", () => ({
  MeasurementOutcomesPanel: ({
    artifacts,
  }: {
    artifacts?: Array<{ role?: string | null; logical?: { qasm?: string | null } | null }>;
  }) => (
    <div data-testid="measurement-panel">
      {(artifacts ?? [])
        .map((artifact) => `${artifact.role}:${artifact.logical?.qasm ?? "none"}`)
        .join(",")}
    </div>
  ),
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { message?: string }) => (
    <div data-testid="empty-state">{message}</div>
  ),
}));

describe("VqeParametersTile", () => {
  it("renders VQE circuit artifacts", () => {
    render(
      <VqeParametersTile
        metrics={{
          convergence_trace: [-1.1, -1.2],
          bloch_vectors: null,
          density_matrix_real: null,
          density_matrix_imag: null,
          optimizer_diagnostics: null,
          objective_evaluations: 56,
          optimizer_iterations: 14,
          effective_max_iterations: 80,
          max_function_evaluations: 120,
          circuit_artifacts: [
            {
              id: "vqe.ansatz",
              role: "ansatz",
              representative: true,
              logical: { qasm: "OPENQASM 3.0; // ansatz" },
            },
            {
              id: "vqe.final",
              role: "final",
              logical: { qasm: "OPENQASM 3.0; // final" },
            },
          ],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "VQE Circuit" })).toBeInTheDocument();
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent(
      "ansatz:OPENQASM 3.0; // ansatz,final:OPENQASM 3.0; // final",
    );
  });

  it("falls back when artifacts are missing", () => {
    render(
      <VqeParametersTile
        metrics={{
          convergence_trace: [],
          bloch_vectors: null,
          density_matrix_real: null,
          density_matrix_imag: null,
          optimizer_diagnostics: null,
          objective_evaluations: null,
          optimizer_iterations: null,
          effective_max_iterations: null,
          max_function_evaluations: null,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "No VQE circuit artifacts recorded",
    );
  });
});
