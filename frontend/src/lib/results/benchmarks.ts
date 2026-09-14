import type { RunResultResponse } from "@/types/run";

export interface ClassicalReferences {
  hf?: number;
  fci?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function extractClassicalReferences(result: RunResultResponse): ClassicalReferences {
  const metrics = isRecord(result.algorithm_metrics) ? result.algorithm_metrics : null;
  if (metrics === null) return {};

  const refs = metrics["classical_references"];
  if (isRecord(refs) === false) return {};

  return {
    hf: typeof refs["hf"] === "number" ? refs["hf"] : undefined,
    fci: typeof refs["fci"] === "number" ? refs["fci"] : undefined,
  };
}

export interface BenchmarkBar {
  label: string;
  energy: number | null;
  isResult?: boolean;
}

export function buildBenchmarkBars(
  resultEnergy: number,
  refs: ClassicalReferences,
  algorithm?: string,
): BenchmarkBar[] {
  const resultLabel = algorithm ? `${algorithm.toUpperCase()} result` : "Result";
  const bars: BenchmarkBar[] = [{ label: resultLabel, energy: resultEnergy, isResult: true }];
  if (refs.hf !== undefined) {
    bars.push({ label: "HF", energy: refs.hf });
  }
  if (refs.fci !== undefined) {
    bars.push({ label: "FCI/Exact", energy: refs.fci });
  }
  return bars.sort((left, right) => {
    if (left.energy == null || right.energy == null) {
      return Number(left.energy == null) - Number(right.energy == null);
    }
    return right.energy - left.energy;
  });
}
