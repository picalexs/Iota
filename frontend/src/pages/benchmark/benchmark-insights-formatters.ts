import type { EasyGoal } from "@/types/run";

export function formatMetric(value: number): string {
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(3);
}

export function formatRuntimeMinutes(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);
  if (safeSeconds < 1) {
    return `${safeSeconds < 0.1 ? safeSeconds.toFixed(2) : safeSeconds.toFixed(1)} s`;
  }

  const roundedSeconds = Math.round(safeSeconds);
  if (roundedSeconds < 60) {
    return `${roundedSeconds} s`;
  }

  const hours = Math.floor(roundedSeconds / 3600);
  const minutes = Math.floor((roundedSeconds % 3600) / 60);
  const remainingSeconds = roundedSeconds % 60;

  if (hours > 0) {
    return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`;
  }

  return remainingSeconds > 0 ? `${minutes} min ${remainingSeconds} s` : `${minutes} min`;
}

function trimTrailingZeroes(value: string): string {
  return value
    .replace(/(\.\d*?[1-9])0+$/u, "$1")
    .replace(/\.0+$/u, "")
    .replace(/\.$/u, "");
}

export function formatParameterNumber(value: number | null | undefined): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  const absoluteValue = Math.abs(value);
  if ((absoluteValue > 0 && absoluteValue < 0.001) || absoluteValue >= 1000) {
    return value.toExponential(1).replace(".0e", "e").replace("e+", "e");
  }
  if (absoluteValue >= 100) return value.toFixed(0);
  if (absoluteValue >= 10) return trimTrailingZeroes(value.toFixed(1));
  if (absoluteValue >= 1) return trimTrailingZeroes(value.toFixed(2));
  return trimTrailingZeroes(value.toFixed(3));
}

export function formatEasyGoalLabel(goal: EasyGoal | null | undefined): string {
  if (goal === "fastest") {
    return "Quick scan";
  }
  if (goal === "best_accuracy") {
    return "High accuracy";
  }
  return "Balanced";
}
