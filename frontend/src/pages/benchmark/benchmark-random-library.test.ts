import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MoleculeResponse } from "@/types/run";

import { fetchMolecules } from "@/api/molecules";
import {
  buildSelectedMoleculeKeysWithRandomLibrary,
  loadEligibleLibraryMolecules,
} from "./benchmark-random-library";

vi.mock("@/api/molecules", () => ({
  fetchMolecules: vi.fn(),
}));

function makeMolecule(index: number): MoleculeResponse {
  return {
    id: `11111111-0000-0000-0000-${String(index).padStart(12, "0")}`,
    name: `Molecule ${index}`,
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("benchmark random library", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads eligible molecules and returns the bounded target size", async () => {
    const firstMolecule = makeMolecule(1);
    const pageMolecules = Array.from({ length: 6 }, (_, index) => makeMolecule(index + 2));
    vi.mocked(fetchMolecules)
      .mockResolvedValueOnce({ items: [firstMolecule], total: 7 })
      .mockResolvedValueOnce({ items: pageMolecules, total: 7 });

    const picked = await loadEligibleLibraryMolecules();

    expect(picked).toHaveLength(6);
    expect(new Set(picked.map((molecule) => molecule.id)).size).toBe(6);
    expect(fetchMolecules).toHaveBeenCalledTimes(2);
  });

  it("replaces previous random-library keys while preserving other selections", () => {
    const picked = [makeMolecule(4), makeMolecule(5)];
    const [firstPicked, secondPicked] = picked;
    if (!firstPicked || !secondPicked) {
      throw new Error("Expected two picked molecules");
    }

    expect(
      buildSelectedMoleculeKeysWithRandomLibrary({
        selectedMolecules: new Set(["h2", "custom:old-random"]),
        randomLibraryMoleculeIds: ["old-random" as MoleculeResponse["id"]],
        picked,
      }),
    ).toEqual(["h2", `custom:${firstPicked.id}`, `custom:${secondPicked.id}`]);
  });
});
