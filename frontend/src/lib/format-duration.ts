export function formatDuration(value: number | null): string {
  if (value == null) return "-";

  const rounded = Math.max(0, Math.round(value));
  if (rounded < 60) return `${rounded}s`;

  const minutes = Math.floor(rounded / 60);
  const seconds = rounded % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}
