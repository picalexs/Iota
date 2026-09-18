import type { AtomSchema, RunAlgorithm } from "@/types/run";

export interface MoleculePreset {
  key: string;
  name: string;
  formula: string;
  description: string;
  atoms: AtomSchema[];
  charge: number;
  multiplicity: number;
  active_space: { n_electrons: number; n_orbitals: number } | null;
  basis: string;
  references: {
    hf: number;
    fci: number | null;
    source: string;
  };
}

export const DEFAULT_CHEMICAL_ACCURACY_HA = 1.6e-3;
export const MAX_DENSE_BENCHMARK_ACTIVE_ORBITALS = 6;

export function usesLargeBenchmarkActiveSpace(
  activeSpace: MoleculePreset["active_space"] | null | undefined,
): boolean {
  return (activeSpace?.n_orbitals ?? 0) > MAX_DENSE_BENCHMARK_ACTIVE_ORBITALS;
}

// STO-3G equilibrium geometries (Å) with published FCI/HF reference energies (Hartree).
// Sources: Szabo & Ostlund "Modern Quantum Chemistry", standard NIST/PySCF benchmarks.
export const BENCHMARK_MOLECULE_PRESETS: MoleculePreset[] = [
  {
    key: "h2",
    name: "Hydrogen (H₂)",
    formula: "H₂",
    description: "2-electron, 2-orbital system. Simplest correlated benchmark.",
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.741 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: {
      hf: -1.11675,
      fci: -1.15164,
      source: "Szabo & Ostlund (STO-3G, R=0.741 Å)",
    },
  },
  {
    key: "lih",
    name: "Lithium Hydride (LiH)",
    formula: "LiH",
    description: "4-electron system with significant correlation. Classic VQE benchmark.",
    atoms: [
      { symbol: "Li", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 1.5951 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 3 },
    basis: "sto-3g",
    references: {
      hf: -7.86204,
      fci: -7.88229,
      source: "Standard STO-3G benchmark (R=1.595 Å)",
    },
  },
  {
    key: "hf_mol",
    name: "Hydrogen Fluoride (HF)",
    formula: "HF",
    description: "10-electron polar molecule. Uses the two active orbitals near the F HOMO.",
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "F", x: 0, y: 0, z: 0.9168 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: {
      hf: -98.57063,
      fci: -98.59252,
      source: "Standard STO-3G benchmark (R=0.917 Å)",
    },
  },
  {
    key: "h2o",
    name: "Water (H₂O)",
    formula: "H₂O",
    description: "10-electron bent molecule. Strong correlation from lone pairs.",
    atoms: [
      { symbol: "O", x: 0, y: 0, z: 0.11779 },
      { symbol: "H", x: 0, y: 0.7572, z: -0.47116 },
      { symbol: "H", x: 0, y: -0.7572, z: -0.47116 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 4, n_orbitals: 4 },
    basis: "sto-3g",
    references: {
      hf: -74.96296,
      fci: -75.0129,
      source: "Szabo & Ostlund Table 6.2 (STO-3G, experimental geometry)",
    },
  },
  {
    key: "beh2",
    name: "Beryllium Hydride (BeH₂)",
    formula: "BeH₂",
    description: "Linear 6-electron system. Near-degeneracy at equilibrium geometry.",
    atoms: [
      { symbol: "Be", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 1.3264 },
      { symbol: "H", x: 0, y: 0, z: -1.3264 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 4, n_orbitals: 4 },
    basis: "sto-3g",
    references: {
      hf: -15.56774,
      fci: -15.58744,
      source: "Standard STO-3G benchmark (linear, R=1.326 Å)",
    },
  },
  {
    key: "n2",
    name: "Nitrogen (N₂)",
    formula: "N₂",
    description: "14-electron triple bond. Strong multireference character. Hardest benchmark.",
    atoms: [
      { symbol: "N", x: 0, y: 0, z: 0 },
      { symbol: "N", x: 0, y: 0, z: 1.0977 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 10, n_orbitals: 8 },
    basis: "sto-3g",
    references: {
      hf: -107.49654,
      fci: -107.59543,
      source: "Standard STO-3G benchmark (R=1.098 Å)",
    },
  },
];

export const BENCHMARK_ALGORITHMS: Array<{
  value: RunAlgorithm;
  label: string;
  description: string;
}> = [
  {
    value: "vqe",
    label: "VQE",
    description: "Variational Quantum Eigensolver (TwoLocal, L-BFGS-B, seeded starts)",
  },
  { value: "sqd", label: "SQD", description: "Sample-based Quantum Diagonalization" },
  { value: "kqd", label: "KQD", description: "Krylov Quantum Diagonalization (exact)" },
  { value: "qfd", label: "QFD", description: "Quantum Filter Diagonalization" },
  { value: "qse", label: "QSE", description: "Quantum Subspace Expansion" },
  { value: "skqd", label: "SKQD", description: "SQD-seeded Krylov Diagonalization" },
];

export function correlationEnergy(hf: number, fci: number): number {
  return fci - hf;
}

export function percentCorrelationRecovered(
  result: number,
  hf: number,
  fci: number,
): number | null {
  const total = correlationEnergy(hf, fci);
  if (Math.abs(total) < 1e-10) return null;
  const recovered = ((result - hf) / total) * 100;
  if (!Number.isFinite(recovered)) return null;
  return Math.max(0, Math.min(100, recovered));
}

export function errorToFci(result: number, fci: number): number {
  return result - fci;
}

export function chemicalAccuracy(
  errorHa: number,
  thresholdHa = DEFAULT_CHEMICAL_ACCURACY_HA,
): boolean {
  return Math.abs(errorHa) <= Math.abs(thresholdHa);
}
