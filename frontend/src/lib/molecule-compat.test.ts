import { describe, it, expect } from "vitest";
import { isMoleculeCompatible } from "./molecule-compat";
import type { MoleculeResponse } from "@/types/run";

describe("isMoleculeCompatible", () => {
  const baseMolecule: MoleculeResponse = {
    id: "test-id",
    name: "Test Molecule",
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.74 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: {
      n_electrons: 2,
      n_orbitals: 4,
    },
    created_at: "2026-04-13T00:00:00Z",
    updated_at: "2026-04-13T00:00:00Z",
  };

  it("returns ok=true for compatible singlet with even electrons", () => {
    const result = isMoleculeCompatible(baseMolecule);
    expect(result.ok).toBe(true);
  });

  it("rejects molecules with multiplicity !== 1", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      multiplicity: 2,
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("multiplicity");
      expect(result.reason).toContain("singlet");
    }
  });

  it("rejects molecules with odd number of electrons", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      active_space: {
        n_electrons: 3,
        n_orbitals: 4,
      },
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("odd_electrons");
      expect(result.reason).toContain("even");
    }
  });

  it("accepts molecules with more than 12 orbitals so VQE and SQD remain selectable", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      active_space: {
        n_electrons: 14,
        n_orbitals: 13,
      },
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(true);
  });

  it("accepts molecules with exactly 12 orbitals", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      active_space: {
        n_electrons: 10,
        n_orbitals: 12,
      },
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(true);
  });

  it("accepts molecules without active_space defined", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      active_space: null,
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(true);
  });

  it("multiplicity check takes precedence", () => {
    const molecule: MoleculeResponse = {
      ...baseMolecule,
      multiplicity: 3,
      active_space: {
        n_electrons: 3,
        n_orbitals: 13,
      },
    };
    const result = isMoleculeCompatible(molecule);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("multiplicity");
    }
  });
});
