import { describe, expect, it } from "vitest";

import { filterAndSortMolecules } from "./molecule-combobox";
import type { MoleculeResponse } from "@/types/run";

const molecules: MoleculeResponse[] = [
  {
    id: "mol-1",
    name: "Nile red",
    atoms: [
      { symbol: "C", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 1 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    iupac_name: "9-diethylamino-5H-benzo[a]phenoxazin-5-one",
    synonyms: ["Benzo phenoxazine dye"],
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
  },
  {
    id: "mol-2",
    name: "BENZOPHENONE",
    atoms: [
      { symbol: "C", x: 0, y: 0, z: 0 },
      { symbol: "O", x: 0, y: 0, z: 1 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
  },
  {
    id: "mol-3",
    name: "benzene",
    atoms: [
      { symbol: "C", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 1 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
  },
  {
    id: "mol-4",
    name: "toluene",
    atoms: [
      { symbol: "C", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 1 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    synonyms: ["methylbenzene"],
    created_at: "2025-06-01T00:00:00Z",
    updated_at: "2025-06-01T00:00:00Z",
  },
];

describe("filterAndSortMolecules", () => {
  it("prioritizes molecule name matches ahead of iupac and synonym-only hits", () => {
    expect(filterAndSortMolecules(molecules, "benz").map((molecule) => molecule.name)).toEqual([
      "benzene",
      "BENZOPHENONE",
      "Nile red",
      "toluene",
    ]);
  });

  it("still supports formula search", () => {
    expect(filterAndSortMolecules(molecules, "CH").map((molecule) => molecule.name)).toEqual([
      "benzene",
      "Nile red",
      "toluene",
    ]);
  });
});
