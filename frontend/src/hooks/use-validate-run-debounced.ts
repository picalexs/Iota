import { useEffect, useRef, useState } from "react";
import { validateRunRequest } from "@/api/runs";
import { buildAlgorithmAwareRunCreate } from "@/lib/run-create-payload";
import type { RunEstimate, RunValidationErrorDetail, SimulationRunFormData } from "@/types/run";

export interface ValidateRunResult {
  estimate: RunEstimate | null;
  serverErrors: RunValidationErrorDetail[];
  warnings: string[];
  loading: boolean;
}

export function useValidateRunDebounced(
  values: SimulationRunFormData,
  isClientValid: boolean,
  delayMs = 400,
): ValidateRunResult {
  const valuesKey = JSON.stringify(values);
  const valuesRef = useRef(values);
  valuesRef.current = values;
  const [state, setState] = useState<ValidateRunResult>({
    estimate: null,
    serverErrors: [],
    warnings: [],
    loading: false,
  });

  useEffect(() => {
    if (!isClientValid) {
      setState((prev) => {
        if (!prev.loading && prev.estimate === null && prev.serverErrors.length === 0) {
          return prev.warnings.length === 0 ? prev : { ...prev, warnings: [] };
        }
        return { estimate: null, serverErrors: [], warnings: [], loading: false };
      });
      return;
    }

    setState((prev) => (prev.loading ? prev : { ...prev, loading: true }));

    const timer = setTimeout(async () => {
      try {
        const currentValues = valuesRef.current;
        const payload = buildAlgorithmAwareRunCreate(currentValues);
        const result = await validateRunRequest({
          molecule_id: currentValues.molecule_id!,
          run: payload,
        });
        setState({
          estimate: result.estimate ?? null,
          serverErrors: result.errors,
          warnings: result.warnings,
          loading: false,
        });
      } catch {
        setState((prev) => ({ ...prev, loading: false }));
      }
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [valuesKey, isClientValid, delayMs]);

  return state;
}
