import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { CircuitArtifactsTile } from "./circuit-artifacts-tile";

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
    artifacts?: Array<{ logical?: { qasm?: string | null } | null }>;
  }) => <div data-testid="measurement-panel">{artifacts?.[0]?.logical?.qasm ?? "no-qasm"}</div>,
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({
    message,
    pending,
    pendingMessage,
  }: {
    message?: string;
    pending?: boolean;
    pendingMessage?: string;
  }) => <div data-testid="empty-state">{pending ? pendingMessage : message}</div>,
}));

describe("CircuitArtifactsTile", () => {
  it("renders the measurement panel when circuit artifacts exist", () => {
    render(
      <CircuitArtifactsTile
        title="QSE Reference Circuit"
        helpText="Reference circuit"
        artifacts={[
          {
            id: "qse.reference.final",
            role: "reference",
            representative: true,
            logical: { qasm: "OPENQASM 3.0; // reference" },
          },
        ]}
        stateKey="qse-reference-circuit"
        emptyMessage="No reference circuit recorded"
        pendingMessage="Awaiting QSE reference circuit"
      />,
    );

    expect(screen.getByRole("heading", { name: "QSE Reference Circuit" })).toBeInTheDocument();
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent("OPENQASM 3.0; // reference");
  });

  it("shows the pending empty state when artifacts are not available yet", () => {
    render(
      <CircuitArtifactsTile
        title="KQD Circuit"
        helpText="KQD circuit"
        artifacts={[]}
        stateKey="kqd-associated-circuit"
        emptyMessage="No KQD circuit recorded"
        pendingMessage="Awaiting KQD circuit artifacts"
        isRunning
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent("Awaiting KQD circuit artifacts");
  });
});
