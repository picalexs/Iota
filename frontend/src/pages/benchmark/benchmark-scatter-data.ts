import type { ChartTooltipSection } from "@/components/results/charts/chart-tooltip";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { AccuracyVerdict } from "@/lib/results/accuracy";
import { assessBenchmarkEntry, benchmarkEntryDisplayLabel } from "./benchmark-utils";
import type { BenchmarkEntry } from "./benchmark-utils";
import { buildBenchmarkTooltipLines } from "./benchmark-scatter-tooltips";

export interface CompletedPoint {
  id: string;
  familyKey: BenchmarkEntry["algorithm"];
  familyLabel: string;
  algorithm: string;
  moleculeKey: string;
  molecule: string;
  moleculeShort: string;
  runId: string | null;
  runtime: number;
  energy: number;
  absErrorMha: number;
  verdict: AccuracyVerdict;
  tooltipSections: readonly ChartTooltipSection[];
}

function isWhitespace(char: string): boolean {
  return char.trim().length === 0;
}

function isScatterLabelSeparator(char: string): boolean {
  return (
    char === "-" ||
    char === "," ||
    char === ";" ||
    char === ":" ||
    char === "/" ||
    isWhitespace(char)
  );
}

function normalizeScatterLabel(value: string): string {
  let normalized = "";
  let pendingSpace = false;

  for (const char of value.trim()) {
    if (isWhitespace(char)) {
      pendingSpace = normalized.length > 0;
      continue;
    }
    if (pendingSpace) {
      normalized += " ";
      pendingSpace = false;
    }
    normalized += char;
  }

  return normalized;
}

function compactScatterLabel(value: string, maxChars = 10): string {
  const normalized = normalizeScatterLabel(value);
  if (normalized.length <= maxChars) return normalized;

  let end = maxChars;
  while (end > 0 && !isScatterLabelSeparator(normalized.charAt(end - 1))) {
    end -= 1;
  }
  while (end > 0 && isScatterLabelSeparator(normalized.charAt(end - 1))) {
    end -= 1;
  }

  const separatorShortened = normalized.slice(0, end).trim();
  const base =
    separatorShortened.length >= Math.floor(maxChars * 0.6)
      ? separatorShortened
      : normalized.slice(0, maxChars - 1).trimEnd();

  return base + "…";
}

function shortMoleculeScatterLabel(formula: string, name: string): string {
  const candidates = [formula, name].map(normalizeScatterLabel).filter(Boolean);
  if (candidates.length === 0) return "Molecule";
  const shortest = [...candidates].sort((left, right) => left.length - right.length)[0];
  if (!shortest) return "Molecule";
  return compactScatterLabel(shortest);
}

export function buildCompletedPoints(
  grouped: ReadonlyArray<{ preset: MoleculePreset; rows: readonly BenchmarkEntry[] }>,
  chemicalAccuracyHa: number,
): CompletedPoint[] {
  return grouped.flatMap(({ preset, rows }) =>
    rows.flatMap((entry) => {
      if (entry.status !== "completed" || entry.energy === null || entry.elapsedSeconds === null) {
        return [];
      }

      const assessment = assessBenchmarkEntry(entry, chemicalAccuracyHa);
      if (assessment.absErrorMha == null) return [];

      return [
        {
          id: entry.id,
          familyKey: entry.algorithm,
          familyLabel: entry.algorithm.toUpperCase(),
          algorithm: benchmarkEntryDisplayLabel(entry),
          moleculeKey: preset.key,
          molecule: normalizeScatterLabel(preset.formula || preset.name),
          moleculeShort: shortMoleculeScatterLabel(preset.formula, preset.name),
          runId: entry.runId,
          runtime: entry.elapsedSeconds,
          energy: entry.energy,
          absErrorMha: assessment.absErrorMha,
          verdict: assessment.verdict,
          tooltipSections: buildBenchmarkTooltipLines(preset, entry, assessment.absErrorMha),
        },
      ];
    }),
  );
}

type ScatterFilterOption = { value: string; label: string };

export function buildScatterFamilyOptions(
  points: readonly CompletedPoint[],
): ScatterFilterOption[] {
  const seen = new Set<string>();
  const options: ScatterFilterOption[] = [];
  for (const point of points) {
    if (seen.has(point.familyKey)) continue;
    seen.add(point.familyKey);
    options.push({ value: point.familyKey, label: point.familyLabel });
  }
  return options;
}

export function buildScatterAlgorithmOptions(
  points: readonly CompletedPoint[],
): ScatterFilterOption[] {
  const seen = new Set<string>();
  const options: ScatterFilterOption[] = [];
  for (const point of points) {
    if (seen.has(point.algorithm)) continue;
    seen.add(point.algorithm);
    options.push({ value: point.algorithm, label: point.algorithm });
  }
  return options;
}

export function buildScatterMoleculeOptions(
  points: readonly CompletedPoint[],
): ScatterFilterOption[] {
  const seen = new Set<string>();
  const options: ScatterFilterOption[] = [];
  for (const point of points) {
    if (seen.has(point.moleculeKey)) continue;
    seen.add(point.moleculeKey);
    options.push({ value: point.moleculeKey, label: point.molecule });
  }
  return options;
}

export function reconcileHiddenFilters(
  current: readonly string[],
  availableValues: readonly string[],
): string[] {
  const available = new Set(availableValues);
  return current.filter((value) => available.has(value));
}

export function toggleHiddenFilter(current: readonly string[], value: string): string[] {
  return current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value];
}

export function hideAllFilters(availableValues: readonly string[]): string[] {
  return [...availableValues];
}
