import { useCallback, useEffect, useMemo, type Dispatch, type SetStateAction } from "react";

import type { RunAlgorithm } from "@/types/run";
import type { BenchmarkBackendMode } from "@/types/benchmark";

import {
  createAdvancedBenchmarkVariant,
  createSimpleBenchmarkVariant,
  duplicateBenchmarkVariant,
  kqdRequiresBranchEstimatorForBackendMode,
  normalizeBenchmarkVariantLabels,
  type BenchmarkAlgorithmVariant,
  type BenchmarkVariantMode,
} from "@/pages/benchmark/benchmark-variants";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import {
  benchmarkEntriesChanged,
  reconcileAdvancedBenchmarkEntries,
} from "@/features/benchmarks/state/normalization";
import {
  insertAdvancedVariantAfterAlgorithmTail,
  type BenchmarkPreset,
} from "@/features/benchmarks/state/selectors";
import type { BenchmarkEntriesSetter } from "@/features/benchmarks/state/polling";
import type { BenchmarkPendingAction } from "@/features/benchmarks/state/controls";

function useDisabledBenchmarkAlgorithmsSync({
  disabledAlgorithms,
  setSelectedAlgorithms,
  setAlgorithmVariants,
}: {
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  setSelectedAlgorithms: Dispatch<SetStateAction<RunAlgorithm[]>>;
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
}) {
  useEffect(() => {
    if (disabledAlgorithms.size === 0) return;
    setSelectedAlgorithms((previous) =>
      previous.filter((algorithm) => !disabledAlgorithms.has(algorithm)),
    );
    setAlgorithmVariants((previous) =>
      previous.filter((variant) => !disabledAlgorithms.has(variant.algorithm)),
    );
  }, [disabledAlgorithms, setAlgorithmVariants, setSelectedAlgorithms]);
}

function resizeAdvancedBenchmarkVariants(
  previous: BenchmarkAlgorithmVariant[],
  algorithm: RunAlgorithm,
  targetCount: number,
  chemicalAccuracyHa: number,
  requiresBranchEstimator: boolean,
): BenchmarkAlgorithmVariant[] {
  const currentCount = previous.filter((variant) => variant.algorithm === algorithm).length;
  if (currentCount === targetCount) {
    return previous;
  }

  if (targetCount > currentCount) {
    let nextVariants = [...previous];
    for (let index = currentCount; index < targetCount; index += 1) {
      nextVariants = insertAdvancedVariantAfterAlgorithmTail(
        nextVariants,
        createAdvancedBenchmarkVariant(
          algorithm,
          chemicalAccuracyHa,
          undefined,
          requiresBranchEstimator,
        ),
      );
    }
    return normalizeBenchmarkVariantLabels(nextVariants);
  }

  let remainingToRemove = currentCount - targetCount;
  const retainedVariants = [...previous];
  for (let index = retainedVariants.length - 1; index >= 0; index -= 1) {
    if (remainingToRemove === 0) {
      break;
    }
    if (retainedVariants[index]?.algorithm !== algorithm) {
      continue;
    }
    retainedVariants.splice(index, 1);
    remainingToRemove -= 1;
  }

  return normalizeBenchmarkVariantLabels(retainedVariants);
}

function useAdvancedBenchmarkVariantActions({
  chemicalAccuracyHa,
  selectedBackendMode,
  disabledAlgorithms,
  setAlgorithmVariants,
}: {
  chemicalAccuracyHa: number;
  selectedBackendMode: BenchmarkBackendMode;
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
}) {
  const addAdvancedVariant = useCallback(
    (algorithm: RunAlgorithm) => {
      if (disabledAlgorithms.has(algorithm)) {
        return;
      }
      setAlgorithmVariants((previous) =>
        normalizeBenchmarkVariantLabels(
          insertAdvancedVariantAfterAlgorithmTail(
            previous,
            createAdvancedBenchmarkVariant(
              algorithm,
              chemicalAccuracyHa,
              undefined,
              kqdRequiresBranchEstimatorForBackendMode(selectedBackendMode),
            ),
          ),
        ),
      );
    },
    [chemicalAccuracyHa, disabledAlgorithms, selectedBackendMode, setAlgorithmVariants],
  );

  const setAdvancedVariantCount = useCallback(
    (algorithm: RunAlgorithm, count: number) => {
      if (disabledAlgorithms.has(algorithm)) {
        return;
      }

      const targetCount = Math.max(0, Math.floor(count));
      setAlgorithmVariants((previous) =>
        resizeAdvancedBenchmarkVariants(
          previous,
          algorithm,
          targetCount,
          chemicalAccuracyHa,
          kqdRequiresBranchEstimatorForBackendMode(selectedBackendMode),
        ),
      );
    },
    [chemicalAccuracyHa, disabledAlgorithms, selectedBackendMode, setAlgorithmVariants],
  );

  const duplicateAdvancedVariant = useCallback(
    (variantId: string) => {
      setAlgorithmVariants((previous) => {
        const variantIndex = previous.findIndex((entry) => entry.id === variantId);
        if (variantIndex === -1) {
          return previous;
        }
        const variant = previous[variantIndex];
        if (!variant) {
          return previous;
        }
        return normalizeBenchmarkVariantLabels([
          ...previous.slice(0, variantIndex + 1),
          duplicateBenchmarkVariant(variant),
          ...previous.slice(variantIndex + 1),
        ]);
      });
    },
    [setAlgorithmVariants],
  );

  const updateAdvancedVariant = useCallback(
    (
      variantId: string,
      updater: (variant: BenchmarkAlgorithmVariant) => BenchmarkAlgorithmVariant,
    ) => {
      setAlgorithmVariants((previous) =>
        normalizeBenchmarkVariantLabels(
          previous.map((variant) => (variant.id === variantId ? updater(variant) : variant)),
        ),
      );
    },
    [setAlgorithmVariants],
  );

  const removeAdvancedVariant = useCallback(
    (variantId: string) => {
      setAlgorithmVariants((previous) =>
        normalizeBenchmarkVariantLabels(previous.filter((variant) => variant.id !== variantId)),
      );
    },
    [setAlgorithmVariants],
  );

  return {
    addAdvancedVariant,
    setAdvancedVariantCount,
    duplicateAdvancedVariant,
    updateAdvancedVariant,
    removeAdvancedVariant,
  };
}

export function useBenchmarkVariantSelectionState({
  benchmarkMode,
  selectedBackendMode,
  selectedAlgorithms,
  algorithmVariants,
  selectedPresets,
  entries,
  running,
  pendingBenchmarkAction,
  disabledAlgorithms,
  chemicalAccuracyHa,
  setBenchmarkMode,
  setSelectedAlgorithms,
  setAlgorithmVariants,
  setEntries,
}: {
  benchmarkMode: BenchmarkVariantMode;
  selectedBackendMode: BenchmarkBackendMode;
  selectedAlgorithms: RunAlgorithm[];
  algorithmVariants: BenchmarkAlgorithmVariant[];
  selectedPresets: BenchmarkPreset[];
  entries: BenchmarkEntry[];
  running: boolean;
  pendingBenchmarkAction: BenchmarkPendingAction;
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  chemicalAccuracyHa: number;
  setBenchmarkMode: Dispatch<SetStateAction<BenchmarkVariantMode>>;
  setSelectedAlgorithms: Dispatch<SetStateAction<RunAlgorithm[]>>;
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
  setEntries: BenchmarkEntriesSetter;
}) {
  const activeVariants = useMemo(
    () =>
      benchmarkMode === "advanced"
        ? normalizeBenchmarkVariantLabels(algorithmVariants)
        : selectedAlgorithms.map((algorithm) => createSimpleBenchmarkVariant(algorithm)),
    [algorithmVariants, benchmarkMode, selectedAlgorithms],
  );
  const activeAlgorithmSet = useMemo(
    () => new Set(activeVariants.map((variant) => variant.algorithm)),
    [activeVariants],
  );
  const setBenchmarkModeValue = useCallback(
    (mode: BenchmarkVariantMode) => setBenchmarkMode(mode),
    [setBenchmarkMode],
  );
  const advancedVariantActions = useAdvancedBenchmarkVariantActions({
    chemicalAccuracyHa,
    selectedBackendMode,
    disabledAlgorithms,
    setAlgorithmVariants,
  });

  useDisabledBenchmarkAlgorithmsSync({
    disabledAlgorithms,
    setSelectedAlgorithms,
    setAlgorithmVariants,
  });

  useEffect(() => {
    if (benchmarkMode !== "advanced") return;
    if (
      running ||
      entries.some((entry) => entry.runId !== null && entry.status === "paused") ||
      pendingBenchmarkAction !== null
    ) {
      return;
    }

    const reconciledEntries = reconcileAdvancedBenchmarkEntries(
      selectedPresets,
      activeVariants,
      entries,
    );
    if (!benchmarkEntriesChanged(entries, reconciledEntries)) {
      return;
    }
    setEntries(reconciledEntries);
  }, [
    activeVariants,
    benchmarkMode,
    entries,
    pendingBenchmarkAction,
    running,
    selectedPresets,
    setEntries,
  ]);

  return {
    activeVariants,
    activeAlgorithmSet,
    setBenchmarkModeValue,
    ...advancedVariantActions,
  };
}
