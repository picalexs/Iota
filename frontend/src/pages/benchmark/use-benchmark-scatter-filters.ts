import { useEffect, useMemo, useState } from "react";
import type { CompletedPoint } from "./benchmark-scatter-data";
import {
  buildScatterAlgorithmOptions,
  buildScatterFamilyOptions,
  buildScatterMoleculeOptions,
  hideAllFilters,
  reconcileHiddenFilters,
  toggleHiddenFilter,
} from "./benchmark-scatter-data";

export function useBenchmarkScatterFilters(points: readonly CompletedPoint[]) {
  const [hiddenFamilies, setHiddenFamilies] = useState<string[]>([]);
  const [hiddenAlgorithms, setHiddenAlgorithms] = useState<string[]>([]);
  const [hiddenMolecules, setHiddenMolecules] = useState<string[]>([]);
  const familyOptions = useMemo(() => buildScatterFamilyOptions(points), [points]);
  const familyValues = useMemo(() => familyOptions.map((option) => option.value), [familyOptions]);
  const hiddenFamilySet = useMemo(() => new Set(hiddenFamilies), [hiddenFamilies]);
  const familyFilteredPoints = useMemo(
    () => points.filter((point) => !hiddenFamilySet.has(point.familyKey)),
    [hiddenFamilySet, points],
  );
  const algorithmOptions = useMemo(
    () => buildScatterAlgorithmOptions(familyFilteredPoints),
    [familyFilteredPoints],
  );
  const moleculeOptions = useMemo(
    () => buildScatterMoleculeOptions(familyFilteredPoints),
    [familyFilteredPoints],
  );
  const algorithmValues = useMemo(
    () => algorithmOptions.map((option) => option.value),
    [algorithmOptions],
  );
  const moleculeValues = useMemo(
    () => moleculeOptions.map((option) => option.value),
    [moleculeOptions],
  );
  const hiddenAlgorithmSet = useMemo(() => new Set(hiddenAlgorithms), [hiddenAlgorithms]);
  const hiddenMoleculeSet = useMemo(() => new Set(hiddenMolecules), [hiddenMolecules]);
  const filteredPoints = useMemo(
    () =>
      familyFilteredPoints.filter(
        (point) =>
          !hiddenAlgorithmSet.has(point.algorithm) && !hiddenMoleculeSet.has(point.moleculeKey),
      ),
    [familyFilteredPoints, hiddenAlgorithmSet, hiddenMoleculeSet],
  );

  useEffect(() => {
    setHiddenFamilies((current) => reconcileHiddenFilters(current, familyValues));
  }, [familyValues]);
  useEffect(() => {
    setHiddenAlgorithms((current) => reconcileHiddenFilters(current, algorithmValues));
  }, [algorithmValues]);
  useEffect(() => {
    setHiddenMolecules((current) => reconcileHiddenFilters(current, moleculeValues));
  }, [moleculeValues]);

  return {
    filteredPoints,
    familyOptions,
    algorithmOptions,
    moleculeOptions,
    hiddenFamilies: hiddenFamilySet,
    hiddenAlgorithms: hiddenAlgorithmSet,
    hiddenMolecules: hiddenMoleculeSet,
    toggleFamily: (value: string) =>
      setHiddenFamilies((current) => toggleHiddenFilter(current, value)),
    toggleAlgorithm: (value: string) =>
      setHiddenAlgorithms((current) => toggleHiddenFilter(current, value)),
    toggleMolecule: (value: string) =>
      setHiddenMolecules((current) => toggleHiddenFilter(current, value)),
    showAllFamilies: () => setHiddenFamilies([]),
    hideAllFamilies: () => setHiddenFamilies(hideAllFilters(familyValues)),
    showAllAlgorithms: () => setHiddenAlgorithms([]),
    hideAllAlgorithms: () => setHiddenAlgorithms(hideAllFilters(algorithmValues)),
    showAllMolecules: () => setHiddenMolecules([]),
    hideAllMolecules: () => setHiddenMolecules(hideAllFilters(moleculeValues)),
    resetFilters: () => {
      setHiddenFamilies([]);
      setHiddenAlgorithms([]);
      setHiddenMolecules([]);
    },
  };
}
