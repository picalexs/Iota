import { describe, expect, it } from "vitest";

import { initialValues } from "./constants";

describe("run form balanced defaults", () => {
  it("opens advanced VQE with the canonical balanced settings", () => {
    expect(initialValues.advanced_vqe).toMatchObject({
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 448,
      max_function_evaluations: 448,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 2,
    });
    expect(initialValues.advanced_qse.vqe_reference_ansatz_name).toBe("NumberPreserving");
  });
});
