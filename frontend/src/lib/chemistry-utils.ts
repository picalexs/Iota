/**
 * Chemistry utility functions for molecular calculations and conversions.
 * Used by the 3D molecule viewer and related components.
 */

import type { AtomSchema } from "@/types/run";

/**
 * Atomic masses in Daltons (g/mol)
 * Source: NIST - Standard Atomic Weights
 */
const ATOMIC_MASSES: Record<string, number> = {
  H: 1.008,
  He: 4.003,
  Li: 6.941,
  Be: 9.012,
  B: 10.81,
  C: 12.011,
  N: 14.007,
  O: 15.999,
  F: 18.998,
  Ne: 20.18,
  Na: 22.99,
  Mg: 24.305,
  Al: 26.982,
  Si: 28.086,
  P: 30.974,
  S: 32.065,
  Cl: 35.453,
  Ar: 39.948,
  K: 39.098,
  Ca: 40.078,
};

/**
 * Covalent radii in Ångströms (Å)
 * Used for bond detection heuristics
 */
const COVALENT_RADII: Record<string, number> = {
  H: 0.31,
  He: 0.28,
  Li: 1.28,
  Be: 0.96,
  B: 0.84,
  C: 0.76,
  N: 0.71,
  O: 0.66,
  F: 0.57,
  Ne: 0.58,
  Na: 1.66,
  Mg: 1.41,
  Al: 1.21,
  Si: 1.11,
  P: 1.07,
  S: 1.05,
  Cl: 1.02,
  Ar: 1.06,
  K: 2.03,
  Ca: 1.76,
};

/**
 * Unicode subscript digits for chemical formulas
 */
const SUBSCRIPT_DIGITS = ["₀", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉"];

/**
 * Converts atoms array to XYZ format string for 3Dmol.js
 * @param atoms - Array of atoms with symbol and coordinates
 * @returns XYZ format string (lines: atom count, comment, then SYMBOL X Y Z per atom)
 */
export function atomsToXyz(atoms: AtomSchema[]): string {
  const lines: string[] = [
    atoms.length.toString(),
    "Molecule",
    ...atoms.map((atom) => `${atom.symbol} ${atom.x} ${atom.y} ${atom.z}`),
  ];
  return lines.join("\n");
}

/**
 * Calculates molecular formula in Hill order (C first, H second, then alphabetical)
 * @param atoms - Array of atoms
 * @returns Formula string with Unicode subscript numbers (e.g., "H₂O", "CH₄")
 */
export function calculateFormula(atoms: AtomSchema[]): string {
  if (atoms.length === 0) {
    return "";
  }

  // Count atoms by symbol
  const counts: Record<string, number> = {};
  atoms.forEach((atom) => {
    counts[atom.symbol] = (counts[atom.symbol] ?? 0) + 1;
  });

  // Hill order: C first, H second, then rest alphabetically
  const symbols: string[] = [];
  if (counts["C"]) symbols.push("C");
  if (counts["H"]) symbols.push("H");

  Object.keys(counts)
    .sort((left, right) => left.localeCompare(right))
    .forEach((symbol) => {
      if (symbol !== "C" && symbol !== "H") {
        symbols.push(symbol);
      }
    });

  // Build formula with subscript numbers
  const formula = symbols
    .map((symbol) => {
      const count = counts[symbol] ?? 0;
      if (count === 1) {
        return symbol;
      }
      // Convert count to subscript digits
      const subscript = count
        .toString()
        .split("")
        .map((digit) => SUBSCRIPT_DIGITS[Number.parseInt(digit, 10)])
        .join("");
      return symbol + subscript;
    })
    .join("");

  return formula;
}

/**
 * Calculates molecular weight from atoms
 * @param atoms - Array of atoms
 * @returns Molecular weight in Daltons, rounded to 3 decimal places
 */
export function calculateMolecularWeight(atoms: AtomSchema[]): number {
  const weight = atoms.reduce((sum, atom) => {
    const mass = ATOMIC_MASSES[atom.symbol];
    return sum + (mass ?? 0);
  }, 0);

  return Math.round(weight * 1000) / 1000;
}

/**
 * Bond definition
 */
export interface Bond {
  from: number;
  to: number;
  order: number; // 1 = single bond
}

/**
 * Calculates bonds from interatomic distances using covalent radii heuristic
 * Bond condition: distance < (radius_a + radius_b) * 1.3
 * @param atoms - Array of atoms
 * @returns Array of bonds with from/to indices and order (always 1 for now)
 */
export function calculateBonds(atoms: AtomSchema[]): Bond[] {
  const bonds: Bond[] = [];

  // Only check pairs i < j to avoid duplicates
  for (let i = 0; i < atoms.length; i++) {
    for (let j = i + 1; j < atoms.length; j++) {
      const atomI = atoms[i];
      const atomJ = atoms[j];
      if (!atomI || !atomJ) {
        continue;
      }

      // Calculate distance
      const dx = atomJ.x - atomI.x;
      const dy = atomJ.y - atomI.y;
      const dz = atomJ.z - atomI.z;
      const distance = Math.hypot(dx, dy, dz);

      // Get covalent radii
      const radiusI = COVALENT_RADII[atomI.symbol] ?? 0;
      const radiusJ = COVALENT_RADII[atomJ.symbol] ?? 0;

      // Check if bond exists
      const bondThreshold = (radiusI + radiusJ) * 1.3;
      if (distance < bondThreshold) {
        bonds.push({
          from: i,
          to: j,
          order: 1, // Single bond for now
        });
      }
    }
  }

  return bonds;
}
