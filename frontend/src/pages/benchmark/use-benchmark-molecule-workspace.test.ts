import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { MoleculeResponse } from "@/types/run";
import { useBenchmarkMoleculeWorkspace } from "./use-benchmark-molecule-workspace";

function makeMolecule(id: string): MoleculeResponse {
  return {
    id,
    name: "Custom molecule",
    iupac_name: "Custom molecule",
    description: "Test molecule",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis_set: "sto-3g",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("useBenchmarkMoleculeWorkspace", () => {
  it("combines built-in and custom options and removes a custom molecule", () => {
    const onSetMolecules = vi.fn();
    const onRemoveCustomMolecule = vi.fn();
    const customMolecule = makeMolecule("custom-1");
    const { result } = renderHook(() =>
      useBenchmarkMoleculeWorkspace({
        selectedMolecules: new Set(["h2", "custom:custom-1"]),
        customMolecules: [customMolecule],
        workspaceLocked: false,
        onSetMolecules,
        onAddCustomMolecule: vi.fn(),
        onRemoveCustomMolecule,
      }),
    );

    expect(result.current.moleculeOptions).toHaveLength(BENCHMARK_MOLECULE_PRESETS.length + 1);
    expect(result.current.visibleMoleculeOptions).toHaveLength(
      BENCHMARK_MOLECULE_PRESETS.length + 1,
    );

    const customPreset = result.current.moleculeOptions.at(-1);
    expect(customPreset?.key).toBe("custom:custom-1");
    act(() => result.current.handleDeleteMolecule(customPreset!));

    expect(onRemoveCustomMolecule).toHaveBeenCalledWith("custom-1");
    expect(onSetMolecules).not.toHaveBeenCalled();
  });

  it("deletes all custom molecules and records the hidden built-in state", () => {
    const onSetMolecules = vi.fn();
    const onRemoveCustomMolecule = vi.fn();
    const customMolecules = [makeMolecule("custom-1"), makeMolecule("custom-2")];
    const { result } = renderHook(() =>
      useBenchmarkMoleculeWorkspace({
        selectedMolecules: new Set(["h2"]),
        customMolecules,
        workspaceLocked: false,
        onSetMolecules,
        onAddCustomMolecule: vi.fn(),
        onRemoveCustomMolecule,
      }),
    );

    act(() => result.current.handleDeleteAllMolecules());

    expect(onRemoveCustomMolecule).toHaveBeenCalledWith("custom-1");
    expect(onRemoveCustomMolecule).toHaveBeenCalledWith("custom-2");
    expect(onSetMolecules).toHaveBeenCalledWith([]);
    expect(result.current.visibleMoleculeOptions.map((preset) => preset.key)).toEqual([
      "h2",
      "custom:custom-1",
      "custom:custom-2",
    ]);
  });
});
