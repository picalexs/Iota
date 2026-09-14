import type { MoleculeResponse } from "@/types/run";

export type CompatResult =
  | { ok: true }
  | { ok: false; reason: string; code: "multiplicity" | "odd_electrons" | "eligibility" };

/**
 * Returns whether a molecule is compatible with the current backend rollout.
 * Rules mirror backend/app/services/validation_service.py:340–362 and :64–93.
 */
export function isMoleculeCompatible(m: MoleculeResponse): CompatResult {
  if (m.eligibility && !m.eligibility.selectable) {
    return {
      ok: false,
      code: "eligibility",
      reason: m.eligibility.reason ?? m.eligibility.label,
    };
  }
  if (m.multiplicity !== 1) {
    return {
      ok: false,
      code: "multiplicity",
      reason: "Only singlet molecules are supported in the current rollout",
    };
  }
  if (m.active_space && m.active_space.n_electrons % 2 !== 0) {
    return { ok: false, code: "odd_electrons", reason: "Active-space electrons must be even" };
  }
  return { ok: true };
}
