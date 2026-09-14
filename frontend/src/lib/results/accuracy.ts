import {
  chemicalAccuracy,
  DEFAULT_CHEMICAL_ACCURACY_HA,
  errorToFci,
  percentCorrelationRecovered,
} from "@/lib/benchmark-presets";
import type { RunResponse } from "@/types/run";

export type AccuracyVerdict = "accurate" | "not_accurate" | "unscored";

export interface AccuracyAssessment {
  verdict: AccuracyVerdict;
  errorHa: number | null;
  errorMha: number | null;
  absErrorHa: number | null;
  absErrorMha: number | null;
  withinThreshold: boolean;
  correlationRecoveredPct: number | null;
  isScorable: boolean;
  thresholdHa: number;
  converged: boolean | null;
}

interface AssessChemicalAccuracyArgs {
  energy: number | null | undefined;
  hf?: number | null;
  fci?: number | null;
  thresholdHa?: number;
  converged?: boolean | null;
}

export function resolveChemicalAccuracyTargetHa(
  run: Pick<RunResponse, "config_json"> | null | undefined,
): number {
  const thresholdHa = run?.config_json?.chemical_accuracy_target_ha;
  return typeof thresholdHa === "number" && Number.isFinite(thresholdHa) && thresholdHa > 0
    ? thresholdHa
    : DEFAULT_CHEMICAL_ACCURACY_HA;
}

export function assessChemicalAccuracy({
  energy,
  hf,
  fci,
  thresholdHa = DEFAULT_CHEMICAL_ACCURACY_HA,
  converged = null,
}: AssessChemicalAccuracyArgs): AccuracyAssessment {
  const hasEnergy = typeof energy === "number" && Number.isFinite(energy);
  const hasHf = typeof hf === "number" && Number.isFinite(hf);
  const hasFci = typeof fci === "number" && Number.isFinite(fci);

  if (!hasEnergy || !hasFci) {
    return {
      verdict: "unscored",
      errorHa: null,
      errorMha: null,
      absErrorHa: null,
      absErrorMha: null,
      withinThreshold: false,
      correlationRecoveredPct:
        hasEnergy && hasHf && hasFci ? percentCorrelationRecovered(energy, hf, fci) : null,
      isScorable: false,
      thresholdHa,
      converged,
    };
  }

  const errorHa = errorToFci(energy, fci);
  const absErrorHa = Math.abs(errorHa);
  return {
    verdict: chemicalAccuracy(errorHa, thresholdHa) ? "accurate" : "not_accurate",
    errorHa,
    errorMha: errorHa * 1000,
    absErrorHa,
    absErrorMha: absErrorHa * 1000,
    withinThreshold: chemicalAccuracy(errorHa, thresholdHa),
    correlationRecoveredPct: hasHf ? percentCorrelationRecovered(energy, hf, fci) : null,
    isScorable: true,
    thresholdHa,
    converged,
  };
}

export function formatAccuracyVerdict(verdict: AccuracyVerdict): string {
  switch (verdict) {
    case "accurate":
      return "Chemically accurate";
    case "not_accurate":
      return "Not chemically accurate";
    case "unscored":
      return "Unscored";
  }
}
