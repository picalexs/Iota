import { useCallback, useMemo, useState } from "react";
import { BENCHMARK_MOLECULE_PRESETS, type MoleculePreset } from "@/lib/benchmark-presets";
import type { MoleculeResponse, UUID } from "@/types/run";
import { moleculeToPreset } from "./benchmark-utils";
import {
  buildSelectedMoleculeKeysWithRandomLibrary,
  loadEligibleLibraryMolecules,
  RANDOM_LIBRARY_TARGET,
} from "./benchmark-random-library";

interface UseBenchmarkMoleculeWorkspaceOptions {
  selectedMolecules: ReadonlySet<string>;
  customMolecules: readonly MoleculeResponse[];
  workspaceLocked: boolean;
  onSetMolecules: (keys: string[]) => void;
  onAddCustomMolecule: (molecule: MoleculeResponse) => void;
  onRemoveCustomMolecule: (id: UUID) => void;
}

export function useBenchmarkMoleculeWorkspace({
  selectedMolecules,
  customMolecules,
  workspaceLocked,
  onSetMolecules,
  onAddCustomMolecule,
  onRemoveCustomMolecule,
}: UseBenchmarkMoleculeWorkspaceOptions) {
  const [randomLibraryLoading, setRandomLibraryLoading] = useState(false);
  const [randomLibraryMessage, setRandomLibraryMessage] = useState<string | null>(null);
  const [randomLibraryMoleculeIds, setRandomLibraryMoleculeIds] = useState<UUID[]>([]);
  const [hiddenBuiltinMoleculeKeys, setHiddenBuiltinMoleculeKeys] = useState<string[]>([]);
  const [deleteAllConfirmationOpen, setDeleteAllConfirmationOpen] = useState(false);

  const customPresets = useMemo(() => customMolecules.map(moleculeToPreset), [customMolecules]);
  const moleculeOptions = useMemo(
    () => [...BENCHMARK_MOLECULE_PRESETS, ...customPresets],
    [customPresets],
  );
  const builtinMoleculeKeys = useMemo(
    () => BENCHMARK_MOLECULE_PRESETS.map((preset) => preset.key),
    [],
  );
  const hiddenBuiltinMoleculeKeySet = useMemo(
    () => new Set(hiddenBuiltinMoleculeKeys),
    [hiddenBuiltinMoleculeKeys],
  );
  const visibleMoleculeOptions = useMemo(
    () =>
      moleculeOptions.filter(
        (preset) =>
          selectedMolecules.has(preset.key) || !hiddenBuiltinMoleculeKeySet.has(preset.key),
      ),
    [hiddenBuiltinMoleculeKeySet, moleculeOptions, selectedMolecules],
  );

  const hideBuiltinMolecule = useCallback(
    (key: string) => {
      setHiddenBuiltinMoleculeKeys((previous) =>
        previous.includes(key) ? previous : [...previous, key],
      );
      onSetMolecules(Array.from(selectedMolecules).filter((selectedKey) => selectedKey !== key));
    },
    [onSetMolecules, selectedMolecules],
  );

  const handleDeleteMolecule = useCallback(
    (preset: MoleculePreset) => {
      if (workspaceLocked) return;
      if (preset.key.startsWith("custom:")) {
        const id = preset.key.slice("custom:".length);
        setRandomLibraryMoleculeIds((previous) =>
          previous.filter((moleculeId) => moleculeId !== id),
        );
        onRemoveCustomMolecule(id);
        return;
      }
      hideBuiltinMolecule(preset.key);
    },
    [hideBuiltinMolecule, onRemoveCustomMolecule, workspaceLocked],
  );

  const handleDeleteAllMolecules = useCallback(() => {
    if (workspaceLocked) return;

    setHiddenBuiltinMoleculeKeys((previous) =>
      Array.from(new Set([...previous, ...builtinMoleculeKeys])),
    );
    for (const molecule of customMolecules) {
      onRemoveCustomMolecule(molecule.id);
    }
    setRandomLibraryMoleculeIds([]);
    onSetMolecules([]);
    setRandomLibraryMessage(null);
  }, [
    builtinMoleculeKeys,
    customMolecules,
    onRemoveCustomMolecule,
    onSetMolecules,
    workspaceLocked,
  ]);

  const handleRandomLibraryMolecules = useCallback(async () => {
    if (workspaceLocked || randomLibraryLoading) return;

    setRandomLibraryLoading(true);
    setRandomLibraryMessage(null);

    try {
      const picked = await loadEligibleLibraryMolecules();

      if (picked.length === 0) {
        setRandomLibraryMessage("No eligible molecules found in the library.");
        return;
      }

      for (const moleculeId of randomLibraryMoleculeIds) {
        onRemoveCustomMolecule(moleculeId);
      }
      for (const molecule of picked) {
        onAddCustomMolecule(molecule);
      }
      const nextRandomIds = picked.map((molecule) => molecule.id);
      setRandomLibraryMoleculeIds(nextRandomIds);
      onSetMolecules(
        buildSelectedMoleculeKeysWithRandomLibrary({
          selectedMolecules,
          randomLibraryMoleculeIds,
          picked,
        }),
      );
      const suffix = picked.length === 1 ? "" : "s";
      setRandomLibraryMessage(
        picked.length === RANDOM_LIBRARY_TARGET
          ? null
          : `Selected ${picked.length} eligible library molecule${suffix}.`,
      );
    } catch {
      setRandomLibraryMessage("Could not load random molecules from the library.");
    } finally {
      setRandomLibraryLoading(false);
    }
  }, [
    onAddCustomMolecule,
    onRemoveCustomMolecule,
    onSetMolecules,
    randomLibraryLoading,
    randomLibraryMoleculeIds,
    selectedMolecules,
    workspaceLocked,
  ]);

  return {
    moleculeOptions,
    visibleMoleculeOptions,
    randomLibraryLoading,
    randomLibraryMessage,
    hasVisibleMolecules: visibleMoleculeOptions.length > 0,
    handleRandomLibraryMolecules,
    handleDeleteMolecule,
    handleDeleteAllMolecules,
    deleteAllConfirmationOpen,
    setDeleteAllConfirmationOpen,
  };
}
