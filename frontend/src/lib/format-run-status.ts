import { formatDuration } from "./format-duration";

interface FormatRunStatusLineInput {
  iteration: number | null;
  totalIterations: number | null;
  energy: number | null;
  remainingIterations: number | null;
  remainingSeconds: number | null;
  iterationLabel?: string;
}

export function formatRunStatusLine({
  iteration,
  energy,
  remainingIterations,
  remainingSeconds,
  iterationLabel = "Iteration",
}: FormatRunStatusLineInput): string | null {
  const segments: string[] = [];

  if (iteration != null) {
    segments.push(`${iterationLabel} ${iteration}`);
  }

  if (energy != null) {
    segments.push(`Energy ${energy.toFixed(6)} Ha`);
  }

  if (remainingIterations != null) {
    segments.push(`Remaining ${remainingIterations}`);
  }

  if (remainingSeconds != null && remainingSeconds > 0) {
    segments.push(`ETA ${formatDuration(remainingSeconds)}`);
  }

  return segments.length > 0 ? segments.join(" · ") : null;
}
