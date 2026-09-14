import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";

import { AlgorithmSection, ModeSection } from "./algorithm-section";
import { initialValues } from "./constants";
import { RunFormProvider, useRunFormContext } from "./run-form-context";
import type { SimulationRunFormData } from "@/types/run";

vi.mock("@/components/forms/field-help", () => ({
  FieldHelp: () => <span data-testid="field-help" />,
}));

function AlgorithmProbe() {
  const form = useRunFormContext();

  return (
    <div>
      <span data-testid="algorithm-value">{form.watch("algorithm") ?? "unset"}</span>
      <span data-testid="mode-value">{form.watch("mode")}</span>
    </div>
  );
}

function renderAlgorithmSection() {
  function TestHarness() {
    const form = useForm<SimulationRunFormData, unknown, SimulationRunFormData>({
      defaultValues: initialValues,
    });

    return (
      <RunFormProvider form={form}>
        <AlgorithmSection />
        <ModeSection />
        <AlgorithmProbe />
      </RunFormProvider>
    );
  }

  return render(<TestHarness />);
}

function getAlgorithmButton(algorithm: string) {
  return document.getElementById(`algorithm-option-${algorithm}`) as HTMLButtonElement;
}

function getModeButton(mode: "easy" | "advanced") {
  return document.getElementById(`mode-option-${mode}`) as HTMLButtonElement;
}

describe("AlgorithmSection", () => {
  it("renders algorithm and mode controls", () => {
    renderAlgorithmSection();

    expect(screen.getByRole("group", { name: /algorithm selection/i })).toBeInTheDocument();
    expect(getAlgorithmButton("vqe")).toBeInTheDocument();
    expect(getAlgorithmButton("sqd")).toBeInTheDocument();
    expect(getModeButton("easy")).toBeInTheDocument();
    expect(getModeButton("advanced")).toBeInTheDocument();
  });

  it("switches the selected algorithm and mode", async () => {
    const user = userEvent.setup();
    renderAlgorithmSection();

    await user.click(getAlgorithmButton("skqd"));
    await user.click(getModeButton("advanced"));

    await waitFor(() => {
      expect(screen.getByTestId("algorithm-value")).toHaveTextContent("skqd");
      expect(screen.getByTestId("mode-value")).toHaveTextContent("advanced");
    });

    expect(getAlgorithmButton("skqd")).toHaveAttribute("aria-pressed", "true");
    expect(getModeButton("advanced")).toHaveAttribute("aria-pressed", "true");
  });
});
