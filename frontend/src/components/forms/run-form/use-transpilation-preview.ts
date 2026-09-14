import { useEffect, useMemo, useRef, useState } from "react";

import { previewTranspilation } from "@/api/backends";
import type { SimulationRunFormData, TranspilationPreviewResponse } from "@/types/run";

interface PreviewState {
  data: TranspilationPreviewResponse | null;
  loading: boolean;
  error: string | null;
}

export function useTranspilationPreview(
  values: SimulationRunFormData,
  isClientValid: boolean,
  numQubits: number | null,
  delayMs = 500,
): PreviewState {
  const previewKey = useMemo(
    () =>
      JSON.stringify({
        molecule_id: values.molecule_id,
        algorithm: values.algorithm,
        backend_target: values.backend_target,
        backend_options: values.backend_options,
        noise_profile: values.noise_profile,
        basis_set_override: values.basis_set_override,
        num_qubits: numQubits,
      }),
    [
      values.algorithm,
      values.backend_options,
      values.backend_target,
      values.basis_set_override,
      values.molecule_id,
      values.noise_profile,
      numQubits,
    ],
  );
  const previewInputsRef = useRef({ values, numQubits });
  previewInputsRef.current = { values, numQubits };
  const [state, setState] = useState<PreviewState>({
    data: null,
    loading: false,
    error: null,
  });

  useEffect(() => {
    const currentInputs = previewInputsRef.current;
    const currentValues = currentInputs.values;
    const currentNumQubits = currentInputs.numQubits;
    const moleculeId = currentValues.molecule_id;
    const algorithm = currentValues.algorithm;
    const backendTarget = currentValues.backend_target;
    if (!moleculeId || !algorithm || !backendTarget || !currentNumQubits || !isClientValid) {
      setState({ data: null, loading: false, error: null });
      return;
    }

    setState((prev) => ({ ...prev, loading: true, error: null }));

    const timer = setTimeout(async () => {
      try {
        const result = await previewTranspilation({
          molecule_id: moleculeId,
          algorithm,
          backend_target: backendTarget,
          num_qubits: currentNumQubits,
          backend_options: currentValues.backend_options,
          noise_profile: currentValues.noise_profile,
          basis_set_override:
            currentValues.basis_set_override.trim().length > 0
              ? currentValues.basis_set_override.trim()
              : null,
        });
        setState({ data: result, loading: false, error: null });
      } catch {
        setState({
          data: null,
          loading: false,
          error: "Preview unavailable from backend API.",
        });
      }
    }, delayMs);

    return () => clearTimeout(timer);
  }, [previewKey, isClientValid, delayMs]);

  return state;
}
