import { FormProvider, useFormContext } from "react-hook-form";
import type React from "react";

import type { SimulationRunFormData } from "@/types/run";
import type { RunFormMethods } from "./run-form-context-helpers";

interface RunFormProviderProps {
  form: RunFormMethods;
  children: React.ReactNode;
}

export function RunFormProvider({ form, children }: RunFormProviderProps) {
  return <FormProvider {...form}>{children}</FormProvider>;
}

export function useRunFormContext() {
  return useFormContext<SimulationRunFormData>();
}
