import { useEffect, useMemo, useState } from "react";
import { fetchBasisSets } from "@/api/molecules";
import type { BasisSetMetadata } from "@/types/run";

const FALLBACK_BASIS_SET = "sto-3g";
const FALLBACK_BASIS_OPTIONS: BasisSetMetadata[] = [
  {
    id: "sto-3g",
    label: "STO-3G",
    description: "Minimal basis",
    family: "minimal",
    recommended: true,
    supported_elements: [],
  },
  {
    id: "3-21g",
    label: "3-21G",
    description: "Split-valence basis with moderate cost",
    family: "pople",
    recommended: false,
    supported_elements: [],
  },
  {
    id: "6-31g",
    label: "6-31G",
    description: "Split-valence",
    family: "split_valence",
    recommended: true,
    supported_elements: [],
  },
  {
    id: "6-31g*",
    label: "6-31G*",
    description: "Polarized split-valence",
    family: "split_valence",
    recommended: true,
    supported_elements: [],
  },
  {
    id: "cc-pvdz",
    label: "cc-pVDZ",
    description: "Correlation-consistent double-zeta",
    family: "correlation_consistent",
    recommended: true,
    supported_elements: [],
  },
  {
    id: "cc-pvtz",
    label: "cc-pVTZ",
    description: "Correlation-consistent triple-zeta",
    family: "correlation_consistent",
    recommended: false,
    supported_elements: [],
  },
  {
    id: "def2-svp",
    label: "def2-SVP",
    description: "Ahlrichs split-valence polarized basis",
    family: "def2",
    recommended: false,
    supported_elements: [],
  },
  {
    id: "def2-tzvp",
    label: "def2-TZVP",
    description: "Ahlrichs triple-zeta valence polarized basis",
    family: "def2",
    recommended: false,
    supported_elements: [],
  },
];

function getOrderedBasisOptions(
  basisOptions: readonly BasisSetMetadata[],
  basisDefault: string,
): BasisSetMetadata[] {
  const defaultOption = basisOptions.find((option) => option.id === basisDefault);
  const remainingOptions = basisOptions
    .filter((option) => option.id !== basisDefault)
    .sort(
      (left, right) =>
        Number(right.recommended) - Number(left.recommended) ||
        left.label.localeCompare(right.label),
    );

  return defaultOption ? [defaultOption, ...remainingOptions] : remainingOptions;
}

export function useBenchmarkBasisSets(
  selectedBasis: string,
  onBasisChange: (basis: string) => void,
) {
  const [basisOptions, setBasisOptions] = useState<BasisSetMetadata[]>(FALLBACK_BASIS_OPTIONS);
  const [basisDefault, setBasisDefault] = useState(FALLBACK_BASIS_SET);
  const basisIds = useMemo(() => new Set(basisOptions.map((option) => option.id)), [basisOptions]);
  const orderedBasisOptions = useMemo(
    () => getOrderedBasisOptions(basisOptions, basisDefault),
    [basisDefault, basisOptions],
  );

  useEffect(() => {
    let cancelled = false;

    void fetchBasisSets()
      .then((response) => {
        if (cancelled || response.basis_sets.length === 0) return;
        setBasisOptions(response.basis_sets);
        setBasisDefault(response.default_basis_set || FALLBACK_BASIS_SET);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (basisIds.has(selectedBasis) || selectedBasis === basisDefault) return;
    onBasisChange(basisDefault);
  }, [basisDefault, basisIds, onBasisChange, selectedBasis]);

  return { basisIds, basisDefault, orderedBasisOptions };
}
