import { describe, it, expect } from "vitest";
import {
  validateMoleculeId,
  validateAnsatz,
  validateOptimizer,
  validateMaxIterations,
  validateBackend,
} from "./validation";

describe("Validation Functions", () => {
  describe("validateMoleculeId", () => {
    it("should return error for empty string", () => {
      const result = validateMoleculeId("");
      expect(result).toBeTruthy();
      expect(typeof result).toBe("string");
    });

    it("should return error for null", () => {
      const result = validateMoleculeId(null);
      expect(result).toBeTruthy();
      expect(typeof result).toBe("string");
    });

    it("should return null for valid UUID", () => {
      const validUUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
      const result = validateMoleculeId(validUUID);
      expect(result).toBeNull();
    });

    it("should return error for invalid UUID format", () => {
      const result = validateMoleculeId("not-a-uuid");
      expect(result).toBeTruthy();
    });
  });

  describe("validateAnsatz", () => {
    it("should return error for empty string", () => {
      const result = validateAnsatz("");
      expect(result).toBeTruthy();
    });

    it("should return null for non-empty ansatz", () => {
      const result = validateAnsatz("UCC");
      expect(result).toBeNull();
    });

    it("should return null for valid ansatz types", () => {
      const validAnsatze = ["UCC", "UCCSD", "HEA"];
      validAnsatze.forEach((ansatz) => {
        const result = validateAnsatz(ansatz);
        expect(result).toBeNull();
      });
    });
  });

  describe("validateOptimizer", () => {
    it("should return error for empty string", () => {
      const result = validateOptimizer("");
      expect(result).toBeTruthy();
    });

    it("should return null for non-empty optimizer", () => {
      const result = validateOptimizer("COBYLA");
      expect(result).toBeNull();
    });

    it("should return null for valid optimizer types", () => {
      const validOptimizers = ["COBYLA", "SLSQP", "NELDER_MEAD"];
      validOptimizers.forEach((optimizer) => {
        const result = validateOptimizer(optimizer);
        expect(result).toBeNull();
      });
    });
  });

  describe("validateMaxIterations", () => {
    it("should return error for max_iterations < 1", () => {
      const result = validateMaxIterations(0);
      expect(result).toBeTruthy();
    });

    it("should return null for max_iterations = 1", () => {
      const result = validateMaxIterations(1);
      expect(result).toBeNull();
    });

    it("should return null for max_iterations in valid range", () => {
      const result = validateMaxIterations(100);
      expect(result).toBeNull();
    });

    it("should return null for max_iterations = 5000 (default max)", () => {
      const result = validateMaxIterations(5000);
      expect(result).toBeNull();
    });

    it("should return error for max_iterations > 5000 (default max)", () => {
      const result = validateMaxIterations(5001);
      expect(result).toBeTruthy();
    });

    it("should return error for max_iterations > custom max", () => {
      const result = validateMaxIterations(10001, 10000);
      expect(result).toBeTruthy();
    });

    it("should return error for negative max_iterations", () => {
      const result = validateMaxIterations(-1);
      expect(result).toBeTruthy();
    });

    it("rejects non-integer value for max iterations", () => {
      expect(validateMaxIterations(1.5)).not.toBeNull();
    });
  });

  describe("validateBackend", () => {
    it("should return error for empty string", () => {
      const result = validateBackend("");
      expect(result).toBeTruthy();
    });

    it("should return null for statevector", () => {
      const result = validateBackend("statevector");
      expect(result).toBeNull();
    });

    it("should return null for ibm_runtime", () => {
      const result = validateBackend("ibm_runtime");
      expect(result).toBeNull();
    });

    it("should return null for aer_simulator", () => {
      const result = validateBackend("aer_simulator");
      expect(result).toBeNull();
    });

    it("should return error for raw ibm_* backend names", () => {
      const ibmBackends = ["ibm_brisbane", "ibm_kyoto", "ibm_condor"];
      ibmBackends.forEach((backend) => {
        const result = validateBackend(backend);
        expect(result).toBeTruthy();
        expect(result).toContain("IBM Runtime");
      });
    });

    it("should return error for invalid backend", () => {
      const result = validateBackend("invalid_backend");
      expect(result).toBeTruthy();
    });
  });
});
