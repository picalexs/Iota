import type { FieldErrors } from "react-hook-form";

import type { SimulationRunFormData } from "@/types/run";

export function flattenErrors(
  errors: FieldErrors<SimulationRunFormData>,
  prefix = "",
): Record<string, string> {
  const flat: Record<string, string> = {};

  for (const [key, value] of Object.entries(errors)) {
    if (!value) continue;
    const path = prefix ? `${prefix}.${key}` : key;

    if (typeof value === "string") {
      flat[path] = value;
      continue;
    }

    if (typeof value !== "object") {
      continue;
    }

    if ("message" in value && typeof value.message === "string") {
      flat[path] = value.message;
    }

    Object.assign(flat, flattenErrors(value as FieldErrors<SimulationRunFormData>, path));
  }

  return flat;
}
