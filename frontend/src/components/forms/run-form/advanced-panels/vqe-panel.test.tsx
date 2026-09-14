import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";

import { VQEPanel } from "./vqe-panel";
import { RunFormProvider, useRunFormContext } from "../run-form-context";
import { initialValues } from "../constants";
import type { RunConfigMetadataResponse, SimulationRunFormData } from "@/types/run";

vi.mock("@/components/forms/field-help", () => ({
  FieldHelp: () => <span data-testid="field-help" />,
}));

function VqeProbe() {
  const form = useRunFormContext();
  const values = form.watch("advanced_vqe");

  return <pre data-testid="vqe-values">{JSON.stringify(values)}</pre>;
}

function renderVqePanel() {
  const metadata: RunConfigMetadataResponse = {
    catalog_version: "2026-09-11-v21",
    algorithms: ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"],
    backend_targets: ["statevector", "aer_simulator", "ibm_runtime"],
    easy_goals: ["fastest", "balanced", "best_accuracy"],
    easy_goal_presets: [
      { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
      { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
      { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
    ],
    ansatzes: [
      {
        id: "EfficientSU2",
        label: "EfficientSU2",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
      {
        id: "TwoLocal",
        label: "TwoLocal",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
    ],
    optimizers: [
      {
        id: "COBYLA",
        label: "COBYLA",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
      {
        id: "SLSQP",
        label: "SLSQP",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
    ],
    defaults: {},
    limits: {},
    capabilities: {},
  };
  function TestHarness() {
    const form = useForm<SimulationRunFormData, unknown, SimulationRunFormData>({
      defaultValues: initialValues,
    });

    return (
      <RunFormProvider form={form}>
        <VQEPanel metadata={metadata} />
        <VqeProbe />
      </RunFormProvider>
    );
  }

  return render(<TestHarness />);
}

describe("VQEPanel", () => {
  it("renders the expected advanced VQE controls", () => {
    renderVqePanel();

    expect(screen.getByRole("combobox", { name: /ansatz/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /optimizer/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /start strategy/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/ansatz depth \(reps\)/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/starting candidates/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max iterations/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max function evaluations/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^show$/i })).toBeInTheDocument();
  });

  it("updates form state when select and numeric controls change", async () => {
    const user = userEvent.setup();
    renderVqePanel();

    await user.click(screen.getByRole("combobox", { name: /ansatz/i }));
    await user.click(screen.getByRole("option", { name: "TwoLocal" }));

    await user.click(screen.getByRole("combobox", { name: /optimizer/i }));
    await user.click(screen.getByRole("option", { name: "SLSQP" }));

    await user.click(screen.getByRole("combobox", { name: /start strategy/i }));
    await user.click(screen.getByRole("option", { name: /^Seeded random$/i }));

    await user.click(screen.getByRole("button", { name: /^show$/i }));

    const maxIterationsInput = screen.getByLabelText(/max iterations/i);
    await user.clear(maxIterationsInput);
    await user.type(maxIterationsInput, "512");
    await user.tab();

    const convergenceThresholdInput = screen.getByLabelText(/convergence threshold/i);
    await user.clear(convergenceThresholdInput);
    await user.type(convergenceThresholdInput, "0.000001");
    await user.tab();

    await waitFor(() => {
      expect(screen.getByTestId("vqe-values")).toHaveTextContent('"ansatz_name":"TwoLocal"');
      expect(screen.getByTestId("vqe-values")).toHaveTextContent('"optimizer_name":"SLSQP"');
      expect(screen.getByTestId("vqe-values")).toHaveTextContent(
        '"initial_point_strategy":"seeded_random"',
      );
      expect(screen.getByTestId("vqe-values")).toHaveTextContent('"max_iterations":512');
      expect(screen.getByTestId("vqe-values")).toHaveTextContent(
        '"convergence_threshold":0.000001',
      );
    });
  });
});
