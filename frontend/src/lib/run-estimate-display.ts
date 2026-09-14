import { formatDuration } from "./format-duration";

export const MIN_DISPLAYABLE_ETA_SECONDS = 5;
export const MIN_DISPLAYABLE_ETA_CONFIDENCE = 0.65;

type OptionalNumber = number | null | undefined;

export function hasMeaningfulEta(
  remainingSeconds: OptionalNumber,
  confidence: OptionalNumber,
): boolean {
  if (remainingSeconds == null || remainingSeconds < MIN_DISPLAYABLE_ETA_SECONDS) {
    return false;
  }

  if (confidence == null) {
    return true;
  }

  return confidence >= MIN_DISPLAYABLE_ETA_CONFIDENCE;
}

export function formatMeaningfulEta(
  remainingSeconds: OptionalNumber,
  confidence: OptionalNumber,
): string | null {
  return hasMeaningfulEta(remainingSeconds, confidence)
    ? formatDuration(remainingSeconds ?? null)
    : null;
}
