import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EstimateSummary } from "./estimate-summary";

vi.mock("./run-form-context", () => ({
  useRunFormContext: () => ({
    formState: {
      isValid: true,
    },
  }),
}));

describe("EstimateSummary", () => {
  it("formats long estimate durations as hours and minutes", () => {
    render(
      <EstimateSummary
        estimate={{
          source: "history",
          algorithm: "vqe",
          estimated_total_iterations: 420,
          estimated_remaining_iterations: 420,
          estimated_total_seconds: 481080,
          estimated_remaining_seconds: 481080,
          confidence: 0.7,
          updated_at: "2026-06-07T20:00:00Z",
        }}
        loading={false}
      />,
    );

    expect(screen.getByText("420", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("133h 38m")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("separates native recovery work from a nested SQD sampling VQE", () => {
    render(
      <EstimateSummary
        estimate={{
          source: "live",
          algorithm: "sqd",
          estimated_total_iterations: 8,
          estimated_primary_iterations: 8,
          estimated_reference_iterations: 450,
          estimated_total_work_units: 458,
          reference_workload: "sampling_vqe",
          work_unit_policy: "sqd_recovery_rounds_plus_sampling_vqe_objective_evaluations",
          estimated_remaining_iterations: 8,
          estimated_remaining_seconds: 180,
          estimated_total_seconds: 180,
          confidence: 0.5,
          updated_at: "2026-09-11T20:00:00Z",
        }}
        loading={false}
      />,
    );

    expect(screen.getByText("8", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("plus 450 sampling_vqe evaluations")).toBeInTheDocument();
  });
});
