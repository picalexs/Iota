import { describe, it, expect } from "vitest";
import {
  atomsToXyz,
  calculateFormula,
  calculateMolecularWeight,
  calculateBonds,
} from "./chemistry-utils";
import type { AtomSchema } from "@/types/run";

describe("atomsToXyz", () => {
  it("produces correct XYZ format for H2 molecule", () => {
    const atoms: AtomSchema[] = [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.74 },
    ];

    const result = atomsToXyz(atoms);
    const lines = result.split("\n");

    expect(lines[0]).toBe("2");
    expect(lines[1]).toBe("Molecule");
    expect(lines[2]).toMatch(/^H\s+0(\.\d+)?\s+0(\.\d+)?\s+0(\.\d+)?$/);
    expect(lines[3]).toMatch(/^H\s+0(\.\d+)?\s+0(\.\d+)?\s+0\.74/);
  });

  it("handles single atom", () => {
    const atoms: AtomSchema[] = [{ symbol: "He", x: 1.5, y: 2.5, z: 3.5 }];

    const result = atomsToXyz(atoms);
    const lines = result.split("\n");

    expect(lines[0]).toBe("1");
    expect(lines[1]).toBe("Molecule");
    expect(lines[2]).toContain("He");
  });
});

describe("calculateFormula", () => {
  it("returns H₂O for water", () => {
    const atoms: AtomSchema[] = [
      { symbol: "O", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.96, y: 0, z: 0 },
      { symbol: "H", x: -0.24, y: 0.93, z: 0 },
    ];

    expect(calculateFormula(atoms)).toBe("H₂O");
  });

  it("returns CH₄ for methane", () => {
    const atoms: AtomSchema[] = [
      { symbol: "C", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.63, y: 0.63, z: 0.63 },
      { symbol: "H", x: -0.63, y: -0.63, z: 0.63 },
      { symbol: "H", x: -0.63, y: 0.63, z: -0.63 },
      { symbol: "H", x: 0.63, y: -0.63, z: -0.63 },
    ];

    expect(calculateFormula(atoms)).toBe("CH₄");
  });

  it("returns H₂ for H2 molecule", () => {
    const atoms: AtomSchema[] = [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.74 },
    ];

    expect(calculateFormula(atoms)).toBe("H₂");
  });

  it("returns empty string for empty atoms array", () => {
    const atoms: AtomSchema[] = [];

    expect(calculateFormula(atoms)).toBe("");
  });
});

describe("calculateMolecularWeight", () => {
  it("returns approximately 2.016 for H2", () => {
    const atoms: AtomSchema[] = [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.74 },
    ];

    const result = calculateMolecularWeight(atoms);
    expect(result).toBeCloseTo(2.016, 2);
  });

  it("returns approximately 18.015 for H2O", () => {
    const atoms: AtomSchema[] = [
      { symbol: "O", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.96, y: 0, z: 0 },
      { symbol: "H", x: -0.24, y: 0.93, z: 0 },
    ];

    const result = calculateMolecularWeight(atoms);
    expect(result).toBeCloseTo(18.015, 2);
  });
});

describe("calculateBonds", () => {
  it("returns 1 bond for H2 at distance 0.74Å", () => {
    const atoms: AtomSchema[] = [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.74 },
    ];

    const bonds = calculateBonds(atoms);
    expect(bonds).toHaveLength(1);
    expect(bonds[0]).toEqual({ from: 0, to: 1, order: 1 });
  });

  it("returns 0 bonds for atoms too far apart", () => {
    const atoms: AtomSchema[] = [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 10, y: 10, z: 10 },
    ];

    const bonds = calculateBonds(atoms);
    expect(bonds).toHaveLength(0);
  });

  it("returns 2 bonds for water (H-O, H-O)", () => {
    const atoms: AtomSchema[] = [
      { symbol: "O", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.96, y: 0, z: 0 },
      { symbol: "H", x: -0.24, y: 0.93, z: 0 },
    ];

    const bonds = calculateBonds(atoms);
    expect(bonds).toHaveLength(2);
    expect(bonds.some((b) => b.from === 0 && b.to === 1)).toBe(true);
    expect(bonds.some((b) => b.from === 0 && b.to === 2)).toBe(true);
  });
});
