import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { EasyGoalSlider } from "./easy-goal-slider";
import { initialValues } from "./constants";
import { RunFormProvider, useRunFormContext } from "./run-form-context";
import type { SimulationRunFormData } from "@/types/run";

function GoalProbe() {
  const form = useRunFormContext();

  return <span data-testid="goal-value">{form.watch("easy_options.goal")}</span>;
}

function renderEasyGoalSlider() {
  function TestHarness() {
    const form = useForm<SimulationRunFormData, unknown, SimulationRunFormData>({
      defaultValues: {
        ...initialValues,
        algorithm: "vqe",
      },
    });

    return (
      <RunFormProvider form={form}>
        <EasyGoalSlider id="easy-goal-slider" />
        <GoalProbe />
      </RunFormProvider>
    );
  }

  return render(<TestHarness />);
}

describe("EasyGoalSlider", () => {
  it("renders the guided goal options", () => {
    renderEasyGoalSlider();

    expect(screen.getByRole("group", { name: /accuracy/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /quick scan/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /production default/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /high accuracy/i })).toBeInTheDocument();
  });

  it("updates the selected goal when an option is pressed", async () => {
    const user = userEvent.setup();
    renderEasyGoalSlider();

    await user.click(screen.getByRole("button", { name: /high accuracy/i }));

    await waitFor(() => {
      expect(screen.getByTestId("goal-value")).toHaveTextContent("best_accuracy");
    });

    expect(screen.getByRole("button", { name: /high accuracy/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
