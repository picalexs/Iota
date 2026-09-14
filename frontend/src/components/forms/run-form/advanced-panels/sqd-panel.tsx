import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import { SqdSkqdSamplingSection } from "./sqd-skqd-sampling-section";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";

interface SQDPanelProps {
  disabled?: boolean;
  onResetRecommended?: () => void;
}

export function SQDPanel({ disabled = false, onResetRecommended }: SQDPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_sqd");
  const sourcePath = "advanced_sqd.sampling_state_source" as const;
  const ansatzPath = "advanced_sqd.sampling_vqe_ansatz_name" as const;
  const optimizerPath = "advanced_sqd.sampling_vqe_optimizer_name" as const;
  const iterationsPath = "advanced_sqd.sampling_vqe_max_iterations" as const;
  const repsPath = "advanced_sqd.sampling_vqe_reps" as const;
  const seedPath = "advanced_sqd.sampling_vqe_seed" as const;

  const fieldError = (
    path:
      | typeof sourcePath
      | typeof ansatzPath
      | typeof optimizerPath
      | typeof iterationsPath
      | typeof repsPath
      | typeof seedPath,
  ) => (isRunFormFieldTouched(form, path) ? getRunFormError(form, path) : undefined);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Tune the SQD sampling budget, stopping tolerances, and selected-CI cap.
          </p>
        </div>
        {onResetRecommended ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onResetRecommended}
            disabled={disabled}
          >
            Reset to recommended
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 rounded-xl border border-border/70 bg-card p-4 dark:bg-muted/20 md:grid-cols-2">
        <div className="md:col-span-2">
          <p className="text-sm font-semibold">Sampling state</p>
          <p className="text-xs text-muted-foreground">
            SQD needs samples from a correlated state to improve on Hartree–Fock. Use the VQE state
            for guided and benchmark runs.
          </p>
        </div>
        <FormField
          label="Sampling State Source"
          htmlFor={sourcePath}
          required
          error={fieldError(sourcePath)}
          help={{
            short: "Choose the state that produces the bitstring samples used by SQD.",
            anchor: "sampling_state_source",
          }}
        >
          <Select
            value={values.sampling_state_source}
            onValueChange={(value) =>
              form.setValue(sourcePath, value as "hf" | "vqe", {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              })
            }
          >
            <SelectTrigger id={sourcePath} disabled={disabled}>
              <SelectValue placeholder="Select sampling state" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="vqe">VQE-prepared correlated state</SelectItem>
              <SelectItem value="hf">Hartree–Fock determinant</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        {values.sampling_state_source === "vqe" ? (
          <>
            <FormField
              label="Sampling VQE Ansatz"
              htmlFor={ansatzPath}
              required
              error={fieldError(ansatzPath)}
              help={{
                short: "Ansatz used to prepare the SQD sampling state.",
                anchor: "sampling_vqe_ansatz_name",
              }}
            >
              <Select
                value={values.sampling_vqe_ansatz_name}
                onValueChange={(value) =>
                  form.setValue(ansatzPath, value, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  })
                }
              >
                <SelectTrigger id={ansatzPath} disabled={disabled}>
                  <SelectValue placeholder="Select sampling ansatz" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="NumberPreserving">NumberPreserving</SelectItem>
                  <SelectItem value="EfficientSU2">EfficientSU2</SelectItem>
                  <SelectItem value="RealAmplitudes">RealAmplitudes</SelectItem>
                  <SelectItem value="TwoLocal">TwoLocal</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            <FormField
              label="Sampling VQE Optimizer"
              htmlFor={optimizerPath}
              required
              error={fieldError(optimizerPath)}
              help={{
                short: "Optimizer used to prepare the SQD sampling state.",
                anchor: "sampling_vqe_optimizer_name",
              }}
            >
              <Select
                value={values.sampling_vqe_optimizer_name}
                onValueChange={(value) =>
                  form.setValue(optimizerPath, value, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  })
                }
              >
                <SelectTrigger id={optimizerPath} disabled={disabled}>
                  <SelectValue placeholder="Select sampling optimizer" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="COBYLA">COBYLA</SelectItem>
                  <SelectItem value="SPSA">SPSA</SelectItem>
                  <SelectItem value="SLSQP">SLSQP</SelectItem>
                  <SelectItem value="L_BFGS_B">L-BFGS-B</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            {(
              [
                [
                  iterationsPath,
                  "Sampling VQE Iterations",
                  values.sampling_vqe_max_iterations,
                  "Sampling VQE optimizer budget.",
                ],
                [
                  repsPath,
                  "Sampling VQE Reps",
                  values.sampling_vqe_reps,
                  "Number of sampling-state ansatz layers.",
                ],
                [
                  seedPath,
                  "Sampling VQE Seed",
                  values.sampling_vqe_seed,
                  "Optional seed for the sampling-state preparation.",
                ],
              ] as const
            ).map(([path, label, value, help]) => {
              let maxValue: number | undefined;
              if (path === iterationsPath) {
                maxValue = RUN_CONSTRAINTS.vqe.max_iterations.max;
              } else if (path === repsPath) {
                maxValue = RUN_CONSTRAINTS.vqe.reps.max;
              }
              return (
                <FormField
                  key={path}
                  label={label}
                  htmlFor={path}
                  required={path !== seedPath}
                  error={fieldError(path)}
                  help={{ short: help, anchor: path.split(".").at(-1) ?? path }}
                >
                  <Input
                    id={path}
                    type="number"
                    inputMode="numeric"
                    step={1}
                    min={path === repsPath ? RUN_CONSTRAINTS.vqe.reps.min : 1}
                    max={maxValue}
                    value={value ?? ""}
                    onChange={(event) =>
                      form.setValue(
                        path,
                        event.target.value === "" ? null : Number(event.target.value),
                        {
                          shouldDirty: true,
                          shouldValidate: true,
                        },
                      )
                    }
                    onBlur={() =>
                      form.setValue(path, value, {
                        shouldTouch: true,
                        shouldValidate: true,
                      })
                    }
                    aria-invalid={!!getRunFormError(form, path)}
                    disabled={disabled}
                  />
                </FormField>
              );
            })}
          </>
        ) : null}
      </div>

      <SqdSkqdSamplingSection
        basePath="advanced_sqd"
        values={values}
        disabled={disabled}
        constraints={RUN_CONSTRAINTS.sqd}
      />
    </div>
  );
}
