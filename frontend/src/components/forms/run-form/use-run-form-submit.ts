import { useState, type Dispatch, type SetStateAction } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { FieldPath, UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { createRun } from "@/api/runs";
import { isApiErrorLike, showErrorToast } from "@/lib/error-handler";
import { buildAlgorithmAwareRunCreate } from "@/lib/run-create-payload";
import type { SimulationRunFormData } from "@/types/run";
import { invalidateRunsQueries } from "@/hooks/use-query-hooks";
import { allRunFormFields } from "./constants";

interface UseRunFormSubmitOptions {
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>;
  setSubmitAttempted: Dispatch<SetStateAction<boolean>>;
}

export function useRunFormSubmit({ form, setSubmitAttempted }: UseRunFormSubmitOptions) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const [ibmConfirmationOpen, setIbmConfirmationOpen] = useState(false);
  const [pendingIbmSubmit, setPendingIbmSubmit] = useState<SimulationRunFormData | null>(null);

  const submitRun = async (
    formValues: SimulationRunFormData,
    options: { ibmRuntimeConfirmed?: boolean } = {},
  ) => {
    setSubmitting(true);

    try {
      const payload = buildAlgorithmAwareRunCreate(formValues, {
        ibmRuntimeConfirmed: options.ibmRuntimeConfirmed,
      });
      const result = await createRun(payload);
      await invalidateRunsQueries(queryClient);

      toast.success("Run Created", {
        description: `Run ${result.id} has been queued`,
      });

      navigate({
        to: "/runs/$runId",
        params: { runId: result.id },
        state: (prev) => ({ ...prev, __source: "run-create" }),
      });
    } catch (error) {
      if (isApiErrorLike(error)) {
        if (error.status === 422 && error.field) {
          form.setError(error.field as FieldPath<SimulationRunFormData>, {
            type: "server",
            message: error.message,
          });
        }
        showErrorToast(error, { title: "Submission Failed" });
      } else {
        showErrorToast(error, {
          title: "Submission Failed",
          fallbackDescription: "An unexpected error occurred",
        });
      }
      throw error;
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = form.handleSubmit(
    async (formValues) => {
      setSubmitAttempted(true);

      if (formValues.backend_target === "ibm_runtime") {
        setPendingIbmSubmit(formValues);
        setIbmConfirmationOpen(true);
        return;
      }

      try {
        await submitRun(formValues);
      } catch {
        // submitRun already surfaced the error to the user.
      }
    },
    async () => {
      setSubmitAttempted(true);
      await Promise.all(
        allRunFormFields.map((field) => form.trigger(field, { shouldFocus: false })),
      );
      showErrorToast(null, {
        title: "Validation Error",
        description: "Please fix the errors in the form",
      });
    },
  );

  const confirmIbmSubmit = async () => {
    const formValues = pendingIbmSubmit ?? form.getValues();
    await submitRun(formValues, { ibmRuntimeConfirmed: true });
    setPendingIbmSubmit(null);
  };

  const handleIbmConfirmationOpenChange = (open: boolean) => {
    setIbmConfirmationOpen(open);
    if (!open && !submitting) {
      setPendingIbmSubmit(null);
    }
  };

  return {
    handleSubmit,
    submitting,
    ibmConfirmationOpen,
    setIbmConfirmationOpen: handleIbmConfirmationOpenChange,
    confirmIbmSubmit,
    pendingIbmSubmit,
  };
}
