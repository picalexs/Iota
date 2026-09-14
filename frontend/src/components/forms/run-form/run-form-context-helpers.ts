import type { FieldPath, UseFormReturn } from "react-hook-form";

import type { SimulationRunFormData } from "@/types/run";

export type RunFormMethods = UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>;

export function getRunFormError(
  form: RunFormMethods,
  name: FieldPath<SimulationRunFormData>,
): string | undefined {
  return form.getFieldState(name, form.formState).error?.message;
}

export function isRunFormFieldTouched(
  form: RunFormMethods,
  name: FieldPath<SimulationRunFormData>,
): boolean {
  return form.getFieldState(name, form.formState).isTouched;
}
