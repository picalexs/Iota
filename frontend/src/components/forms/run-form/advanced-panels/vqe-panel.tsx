import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import { ExpertDisclosure } from "./expert-disclosure";
import { VqeSelectorFields } from "./vqe-selector-fields";
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumberSlider } from "@/components/ui/number-slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { RunConfigMetadataResponse } from "@/types/run";

interface VQEPanelProps {
  disabled?: boolean;
  metadata: RunConfigMetadataResponse | null;
  onResetRecommended?: () => void;
}

export function VQEPanel({ disabled = false, metadata, onResetRecommended }: VQEPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_vqe");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Configure the ansatz, optimizer, and search budget used by VQE.
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <VqeSelectorFields
          ansatzPath="advanced_vqe.ansatz_name"
          optimizerPath="advanced_vqe.optimizer_name"
          ansatzValue={values.ansatz_name}
          optimizerValue={values.optimizer_name}
          metadata={metadata}
          disabled={disabled}
        />

        <FormField
          label="Start Strategy"
          htmlFor="advanced-vqe-initial-point-strategy-select"
          required
          error={
            isRunFormFieldTouched(form, "advanced_vqe.initial_point_strategy")
              ? getRunFormError(form, "advanced_vqe.initial_point_strategy")
              : undefined
          }
          help={{
            short: "Choose how the optimizer starting parameters are initialized.",
            anchor: "initial_point_strategy",
            href: "/info/components/optimizers",
          }}
        >
          <Select
            value={values.initial_point_strategy}
            onValueChange={(value) =>
              form.setValue(
                "advanced_vqe.initial_point_strategy",
                value as "seeded_random" | "zero" | "zero_plus_seeded_random",
                {
                  shouldDirty: true,
                  shouldTouch: true,
                  shouldValidate: true,
                },
              )
            }
          >
            <SelectTrigger
              id="advanced-vqe-initial-point-strategy-select"
              disabled={disabled}
              aria-invalid={!!getRunFormError(form, "advanced_vqe.initial_point_strategy")}
            >
              <SelectValue placeholder="Select start strategy" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="zero_plus_seeded_random">Zero + seeded random</SelectItem>
              <SelectItem value="zero">Zero vector</SelectItem>
              <SelectItem value="seeded_random">Seeded random</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField
          label="Ansatz Depth (reps)"
          htmlFor="advanced-vqe-reps-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_vqe.reps")
              ? getRunFormError(form, "advanced_vqe.reps")
              : undefined
          }
          help={{
            short:
              "Number of repeated ansatz layers. More reps increase expressiveness and circuit cost.",
            anchor: "reps",
            href: "/info/components/ansatzes",
          }}
        >
          <NumberSlider
            id="advanced-vqe-reps-input"
            value={values.reps}
            min={RUN_CONSTRAINTS.vqe.reps.min}
            max={RUN_CONSTRAINTS.vqe.reps.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_vqe.reps", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_vqe.reps", values.reps, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Starting Candidates"
          htmlFor="advanced-vqe-initial-point-candidates-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_vqe.initial_point_candidates")
              ? getRunFormError(form, "advanced_vqe.initial_point_candidates")
              : undefined
          }
          help={{
            short:
              "Number of candidate starting points evaluated before the main optimization begins.",
            anchor: "initial_point_candidates",
          }}
        >
          <NumberSlider
            id="advanced-vqe-initial-point-candidates-input"
            value={values.initial_point_candidates}
            min={RUN_CONSTRAINTS.vqe.initial_point_candidates.min}
            max={RUN_CONSTRAINTS.vqe.initial_point_candidates.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_vqe.initial_point_candidates", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue(
                "advanced_vqe.initial_point_candidates",
                values.initial_point_candidates,
                {
                  shouldTouch: true,
                  shouldValidate: true,
                },
              )
            }
            disabled={disabled}
          />
        </FormField>

        <div className="md:col-span-2">
          <FormField
            label="Max Iterations"
            htmlFor="advanced-vqe-max-iterations-input"
            required
            error={
              isRunFormFieldTouched(form, "advanced_vqe.max_iterations")
                ? getRunFormError(form, "advanced_vqe.max_iterations")
                : undefined
            }
            help={{
              short: "Cap optimizer steps for the main VQE solve.",
              anchor: "max_iterations",
            }}
          >
            <NumberSlider
              id="advanced-vqe-max-iterations-input"
              value={values.max_iterations}
              min={RUN_CONSTRAINTS.vqe.max_iterations.min}
              max={RUN_CONSTRAINTS.vqe.max_iterations.max}
              step={1}
              onChange={(next) =>
                form.setValue("advanced_vqe.max_iterations", next, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue("advanced_vqe.max_iterations", values.max_iterations, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>
        </div>

        <div className="md:col-span-2">
          <FormField
            label="Max Function Evaluations"
            htmlFor="advanced-vqe-max-function-evaluations-input"
            required
            error={
              isRunFormFieldTouched(form, "advanced_vqe.max_function_evaluations")
                ? getRunFormError(form, "advanced_vqe.max_function_evaluations")
                : undefined
            }
            help={{
              short: "Hard cap on objective evaluations, including candidate-start probing.",
              anchor: "max_function_evaluations",
            }}
          >
            <NumberSlider
              id="advanced-vqe-max-function-evaluations-input"
              value={values.max_function_evaluations}
              min={RUN_CONSTRAINTS.vqe.max_function_evaluations.min}
              max={RUN_CONSTRAINTS.vqe.max_function_evaluations.max}
              step={1}
              onChange={(next) =>
                form.setValue("advanced_vqe.max_function_evaluations", next, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue(
                  "advanced_vqe.max_function_evaluations",
                  values.max_function_evaluations,
                  {
                    shouldTouch: true,
                    shouldValidate: true,
                  },
                )
              }
              disabled={disabled}
            />
          </FormField>
        </div>
      </div>

      <ExpertDisclosure description="Tune solver thresholds and pass JSON payloads straight into the supported runtime hooks.">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormField
            label="Seed"
            htmlFor="advanced-vqe-seed-input"
            error={
              isRunFormFieldTouched(form, "advanced_vqe.seed")
                ? getRunFormError(form, "advanced_vqe.seed")
                : undefined
            }
            help={{
              short: "Fix the VQE random seed for reproducible candidate sampling.",
              anchor: "seed",
            }}
          >
            <Input
              id="advanced-vqe-seed-input"
              type="number"
              step={1}
              min={0}
              value={values.seed ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_vqe.seed",
                  event.target.value === "" ? null : Number(event.target.value),
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              onBlur={() =>
                form.setValue("advanced_vqe.seed", values.seed, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>

          <FormField
            label="Convergence Threshold"
            htmlFor="advanced-vqe-convergence-threshold-input"
            error={
              isRunFormFieldTouched(form, "advanced_vqe.convergence_threshold")
                ? getRunFormError(form, "advanced_vqe.convergence_threshold")
                : undefined
            }
            help={{
              short: "Optional stopping threshold on optimizer convergence.",
              anchor: "convergence_threshold",
            }}
          >
            <Input
              id="advanced-vqe-convergence-threshold-input"
              type="number"
              step="any"
              min={0}
              value={values.convergence_threshold ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_vqe.convergence_threshold",
                  event.target.value === "" ? null : Number(event.target.value),
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              onBlur={() =>
                form.setValue("advanced_vqe.convergence_threshold", values.convergence_threshold, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>

          <FormField
            label="Optimizer Options"
            htmlFor="advanced-vqe-optimizer-options-text"
            error={
              isRunFormFieldTouched(form, "advanced_vqe.optimizer_options_text")
                ? getRunFormError(form, "advanced_vqe.optimizer_options_text")
                : undefined
            }
            help={{
              short: "Optional JSON object filtered against the allowed optimizer option keys.",
              anchor: "optimizer_options",
            }}
          >
            <Textarea
              id="advanced-vqe-optimizer-options-text"
              value={values.optimizer_options_text}
              onChange={(event) =>
                form.setValue("advanced_vqe.optimizer_options_text", event.target.value, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue(
                  "advanced_vqe.optimizer_options_text",
                  values.optimizer_options_text,
                  {
                    shouldTouch: true,
                    shouldValidate: true,
                  },
                )
              }
              placeholder='{"tol": 1e-4}'
              disabled={disabled}
            />
          </FormField>

          <FormField
            label="Initial Parameters"
            htmlFor="advanced-vqe-initial-parameters-text"
            error={
              isRunFormFieldTouched(form, "advanced_vqe.initial_parameters_text")
                ? getRunFormError(form, "advanced_vqe.initial_parameters_text")
                : undefined
            }
            help={{
              short: "Optional JSON array of explicit starting parameters.",
              anchor: "initial_parameters",
            }}
          >
            <Textarea
              id="advanced-vqe-initial-parameters-text"
              value={values.initial_parameters_text}
              onChange={(event) =>
                form.setValue("advanced_vqe.initial_parameters_text", event.target.value, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue(
                  "advanced_vqe.initial_parameters_text",
                  values.initial_parameters_text,
                  {
                    shouldTouch: true,
                    shouldValidate: true,
                  },
                )
              }
              placeholder="[0, 0, 0, 0]"
              disabled={disabled}
            />
          </FormField>

          <div className="md:col-span-2">
            <FormField
              label="Parameter Bounds"
              htmlFor="advanced-vqe-parameter-bounds-text"
              error={
                isRunFormFieldTouched(form, "advanced_vqe.parameter_bounds_text")
                  ? getRunFormError(form, "advanced_vqe.parameter_bounds_text")
                  : undefined
              }
              help={{
                short: "Optional JSON array of [min, max] pairs for each variational parameter.",
                anchor: "parameter_bounds",
              }}
            >
              <Textarea
                id="advanced-vqe-parameter-bounds-text"
                value={values.parameter_bounds_text}
                onChange={(event) =>
                  form.setValue("advanced_vqe.parameter_bounds_text", event.target.value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
                onBlur={() =>
                  form.setValue(
                    "advanced_vqe.parameter_bounds_text",
                    values.parameter_bounds_text,
                    {
                      shouldTouch: true,
                      shouldValidate: true,
                    },
                  )
                }
                placeholder="[[-3.14, 3.14], [-3.14, 3.14]]"
                disabled={disabled}
              />
            </FormField>
          </div>
        </div>
      </ExpertDisclosure>
    </div>
  );
}
