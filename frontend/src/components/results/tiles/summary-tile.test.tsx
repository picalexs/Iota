import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SummaryTile } from "./summary-tile";
import type { BackendOptions, MoleculeResponse, RunResponse } from "@/types/run";

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    to,
  }: {
    children: ReactNode;
    to?: string;
    params?: Record<string, string>;
    className?: string;
  }) => <a href={to ?? "#"}>{children}</a>,
}));

const run: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "COMPLETED",
  algorithm: "qfd",
  mode: "easy",
  backend_target: "statevector",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: {
    execution: {
      simulator_method: "statevector",
    },
  },
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

const molecule: MoleculeResponse = {
  id: "mol-1",
  name: "Water",
  atoms: [],
  basis_set: "def2-tzvp",
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:00:00Z",
};

describe("SummaryTile", () => {
  it("renders run descriptors as plain metadata instead of badges", () => {
    render(
      <SummaryTile
        run={run}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-76.061022}
        currentIteration={24}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("QFD").closest("[data-slot='badge']")).toBeNull();
    expect(screen.getByText("Easy").closest("[data-slot='badge']")).toBeNull();
  });

  it("hides a simulator method row when it duplicates the backend target", () => {
    render(
      <SummaryTile
        run={run}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-76.061022}
        currentIteration={24}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("Statevector")).toBeInTheDocument();
    expect(screen.queryByText("Simulator method")).not.toBeInTheDocument();
  });

  it("keeps execution metadata visible in summary after the dedicated tile is removed", () => {
    const backendOptions: BackendOptions = {
      backend_name: "statevector",
      selection_policy: "manual",
      shots: 4096,
      optimization_level: 1,
      aer_method: "automatic",
      seed_simulator: 123,
      seed_transpiler: 456,
    };

    render(
      <SummaryTile
        run={{
          ...run,
          config_json: {
            backend_options: backendOptions,
          },
          metadata: {
            num_qubits: 12,
            circuit_depth: 128,
            two_qubit_depth: 32,
          },
        }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-76.061022}
        currentIteration={24}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("Policy")).toBeInTheDocument();
    expect(screen.getByText("Manual")).toBeInTheDocument();
    expect(screen.getByText("Depth")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("2Q depth")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByText("Simulator seed")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
    expect(screen.getByText("Transpiler seed")).toBeInTheDocument();
    expect(screen.getByText("456")).toBeInTheDocument();
  });

  it("links the IBM account name to settings when the profile still exists", () => {
    render(
      <SummaryTile
        run={{
          ...run,
          backend_target: "ibm_runtime",
          credential_profile_id: "profile-1",
          credential_profile_name: "Main IBM",
        }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-76.061022}
        currentIteration={24}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("IBM Account")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Main IBM" })).toHaveAttribute("href", "/settings");
  });

  it("shows deleted IBM accounts with their preserved name", () => {
    render(
      <SummaryTile
        run={{
          ...run,
          backend_target: "ibm_runtime",
          credential_profile_id: null,
          credential_profile_name: "Lab IBM",
        }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-76.061022}
        currentIteration={24}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("IBM Account")).toBeInTheDocument();
    expect(screen.getByText("Lab IBM (Deleted)")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Lab IBM (Deleted)" })).not.toBeInTheDocument();
  });

  it("scores the live chemical-accuracy verdict against the best energy seen so far", () => {
    render(
      <SummaryTile
        run={{ ...run, status: "RUNNING" }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-75.9981}
        liveBestEnergy={-75.9986}
        currentIteration={24}
        runtimeSeconds={161}
        fciEnergy={-76.0}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("Chemically accurate")).toBeInTheDocument();
    expect(
      screen.getByText(
        "1.40 mHa difference from FCI/Exact · 0.20 mHa under 1.60 mHa threshold",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("-75.998100 Ha")).toBeInTheDocument();
  });

  it("shows how far an inaccurate result is over the threshold", () => {
    render(
      <SummaryTile
        run={{ ...run, status: "COMPLETED" }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={-70.69255}
        runtimeSeconds={161}
        fciEnergy={-76.0}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.getByText("Not chemically accurate")).toBeInTheDocument();
    expect(screen.getByText("+5305.85 mHa over 1.60 mHa threshold")).toBeInTheDocument();
  });

  it("keeps summary skeletons visible while dependent run detail data is still loading", () => {
    const { container } = render(
      <SummaryTile
        run={{ ...run, status: "COMPLETED" }}
        result={null}
        events={[]}
        molecule={molecule}
        currentEnergy={null}
        currentIteration={null}
        runtimeSeconds={null}
        chemicalAccuracyHa={0.0016}
        pending={true}
      />,
    );

    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.queryByText("Unscored")).not.toBeInTheDocument();
    expect(container.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0);
  });

  it("shows the stop reason in a hover tooltip on the convergence status", async () => {
    const user = userEvent.setup();

    render(
      <SummaryTile
        run={{
          ...run,
          algorithm: "vqe",
          config_json: {
            advanced_config: {
              algorithm: "vqe",
              ansatz_name: "EfficientSU2",
              optimizer_name: "COBYLA",
              max_iterations: 24,
              convergence_threshold: 1e-5,
              max_function_evaluations: 24,
            },
          },
        }}
        result={{
          run_id: "run-1",
          energy: -76.061022,
          iterations: 24,
          optimal_parameters: [],
          converged: false,
          algorithm_metrics: {
            objective_evaluations: 24,
            optimizer_diagnostics: {
              termination_reason: "max_function_evaluations",
              final_delta_energy: 2e-4,
              max_function_evaluations: 24,
            },
          },
          created_at: "2025-06-01T10:05:00Z",
        }}
        events={[]}
        molecule={molecule}
        runtimeSeconds={161}
        chemicalAccuracyHa={0.0016}
      />,
    );

    expect(screen.queryByText("Stopped because")).not.toBeInTheDocument();

    await user.hover(screen.getByRole("button", { name: "Convergence status details" }));

    expect(
      (await screen.findAllByText("The run reached the function-evaluation budget")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("|dE| 2.00e-4 > 1.00e-5 Ha · evals 24 / 24").length).toBeGreaterThan(
      0,
    );
  });
});
