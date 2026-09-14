import type { ReactNode } from "react";
import type { FieldPath } from "react-hook-form";

import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import { ExpertDisclosure } from "./expert-disclosure";
import { NumberSlider } from "@/components/ui/number-slider";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SimulationRunFormData } from "@/types/run";

type SharedSamplingPath = "advanced_sqd" | "advanced_skqd";

interface SharedSamplingValues {
  samples_per_batch: number | null;
  num_batches: number | null;
  max_iterations: number | null;
  num_elec_a: number | null;
  num_elec_b: number | null;
  energy_tol: number | null;
  occupancies_tol: number | null;
  min_selected_configurations: number | null;
  seed: number | null;
  max_dim_mode: "shared" | "spin_resolved";
  max_dim: number | null;
  max_dim_a: number | null;
  max_dim_b: number | null;
  spin_sq_target: number | null;
  sci_solver_options_text: string;
}

interface SharedSamplingSectionProps {
  basePath: SharedSamplingPath;
  values: SharedSamplingValues;
  disabled?: boolean;
  constraints: {
    samples_per_batch: { min: number; max: number };
    num_batches: { min: number; max: number };
    max_iterations: { min: number; max: number };
  };
  extraPrimary?: ReactNode;
}

function pathFor(
  basePath: SharedSamplingPath,
  field: keyof SharedSamplingValues,
): FieldPath<SimulationRunFormData> {
  return `${basePath}.${field}` as FieldPath<SimulationRunFormData>;
}

function NumberInputField({
  basePath,
  field,
  label,
  help,
  value,
  disabled,
}: {
  basePath: SharedSamplingPath;
  field: keyof SharedSamplingValues;
  label: string;
  help: string;
  value: number | null;
  disabled?: boolean;
}) {
  const form = useRunFormContext();
  const path = pathFor(basePath, field);

  return (
    <FormField
      label={label}
      htmlFor={path}
      error={isRunFormFieldTouched(form, path) ? getRunFormError(form, path) : undefined}
      help={{ short: help, anchor: field }}
    >
      <Input
        id={path}
        type="number"
        inputMode="decimal"
        step="any"
        value={value ?? ""}
        onChange={(event) =>
          form.setValue(path, event.target.value === "" ? null : Number(event.target.value), {
            shouldDirty: true,
            shouldValidate: true,
          })
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
}

export function SqdSkqdSamplingSection({
  basePath,
  values,
  disabled = false,
  constraints,
  extraPrimary,
}: SharedSamplingSectionProps) {
  const form = useRunFormContext();
  const maxDimModePath = pathFor(basePath, "max_dim_mode");
  const sciOptionsPath = pathFor(basePath, "sci_solver_options_text");

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <FormField
        label="Samples per Draw"
        htmlFor={pathFor(basePath, "samples_per_batch")}
        required
        error={
          isRunFormFieldTouched(form, pathFor(basePath, "samples_per_batch"))
            ? getRunFormError(form, pathFor(basePath, "samples_per_batch"))
            : undefined
        }
        help={{
          short:
            "Bitstring samples collected in each SQD draw. Combined with draw count, this sets the total sampling budget.",
          anchor: "samples_per_batch",
        }}
      >
        <NumberSlider
          id={pathFor(basePath, "samples_per_batch")}
          value={values.samples_per_batch}
          min={constraints.samples_per_batch.min}
          max={constraints.samples_per_batch.max}
          step={1}
          onChange={(next) =>
            form.setValue(pathFor(basePath, "samples_per_batch"), next, {
              shouldDirty: true,
              shouldValidate: true,
            })
          }
          onBlur={() =>
            form.setValue(pathFor(basePath, "samples_per_batch"), values.samples_per_batch, {
              shouldTouch: true,
              shouldValidate: true,
            })
          }
          disabled={disabled}
        />
      </FormField>

      <FormField
        label="Draw Count"
        htmlFor={pathFor(basePath, "num_batches")}
        required
        error={
          isRunFormFieldTouched(form, pathFor(basePath, "num_batches"))
            ? getRunFormError(form, pathFor(basePath, "num_batches"))
            : undefined
        }
        help={{
          short: "Number of independent SQD draws per recovery round.",
          anchor: "num_batches",
        }}
      >
        <NumberSlider
          id={pathFor(basePath, "num_batches")}
          value={values.num_batches}
          min={constraints.num_batches.min}
          max={constraints.num_batches.max}
          step={1}
          onChange={(next) =>
            form.setValue(pathFor(basePath, "num_batches"), next, {
              shouldDirty: true,
              shouldValidate: true,
            })
          }
          onBlur={() =>
            form.setValue(pathFor(basePath, "num_batches"), values.num_batches, {
              shouldTouch: true,
              shouldValidate: true,
            })
          }
          disabled={disabled}
        />
      </FormField>

      <FormField
        label="Recovery Rounds"
        htmlFor={pathFor(basePath, "max_iterations")}
        required
        error={
          isRunFormFieldTouched(form, pathFor(basePath, "max_iterations"))
            ? getRunFormError(form, pathFor(basePath, "max_iterations"))
            : undefined
        }
        help={{
          short: "Cap the number of SQD recovery and selected-CI refinement rounds.",
          anchor: "max_iterations",
        }}
      >
        <NumberSlider
          id={pathFor(basePath, "max_iterations")}
          value={values.max_iterations}
          min={constraints.max_iterations.min}
          max={constraints.max_iterations.max}
          step={1}
          onChange={(next) =>
            form.setValue(pathFor(basePath, "max_iterations"), next, {
              shouldDirty: true,
              shouldValidate: true,
            })
          }
          onBlur={() =>
            form.setValue(pathFor(basePath, "max_iterations"), values.max_iterations, {
              shouldTouch: true,
              shouldValidate: true,
            })
          }
          disabled={disabled}
        />
      </FormField>

      <NumberInputField
        basePath={basePath}
        field="energy_tol"
        label="Energy Delta Tolerance"
        help="Stopping tolerance for the change in SQD recovery energy."
        value={values.energy_tol}
        disabled={disabled}
      />

      <NumberInputField
        basePath={basePath}
        field="occupancies_tol"
        label="Occupancy Delta Tolerance"
        help="Tolerance for orbital-occupancy stabilization between SQD rounds."
        value={values.occupancies_tol}
        disabled={disabled}
      />

      <FormField
        label="Selected-CI Cap"
        htmlFor={maxDimModePath}
        help={{
          short:
            "Cap the selected-CI determinant basis with one shared limit or separate alpha/beta limits.",
          anchor: "max_dim",
        }}
      >
        <div className="space-y-3">
          <Select
            value={values.max_dim_mode}
            onValueChange={(value) =>
              form.setValue(maxDimModePath, value as SharedSamplingValues["max_dim_mode"], {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              })
            }
          >
            <SelectTrigger id={maxDimModePath} disabled={disabled}>
              <SelectValue placeholder="Select max-dimension mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="shared">One determinant cap</SelectItem>
              <SelectItem value="spin_resolved">Alpha/beta caps</SelectItem>
            </SelectContent>
          </Select>

          {values.max_dim_mode === "shared" ? (
            <NumberInputField
              basePath={basePath}
              field="max_dim"
              label="Shared Determinant Cap"
              help="Use one selected-CI determinant limit for both spin sectors."
              value={values.max_dim}
              disabled={disabled}
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <NumberInputField
                basePath={basePath}
                field="max_dim_a"
                label="Alpha Determinant Cap"
                help="Selected-CI determinant cap for the alpha spin sector."
                value={values.max_dim_a}
                disabled={disabled}
              />
              <NumberInputField
                basePath={basePath}
                field="max_dim_b"
                label="Beta Determinant Cap"
                help="Selected-CI determinant cap for the beta spin sector."
                value={values.max_dim_b}
                disabled={disabled}
              />
            </div>
          )}
        </div>
      </FormField>

      {extraPrimary}

      <div className="md:col-span-2">
        <ExpertDisclosure description="Expose particle-count overrides and solver-level tuning when you need them.">
          <div className="grid gap-4 md:grid-cols-2">
            <NumberInputField
              basePath={basePath}
              field="num_elec_a"
              label="Alpha Electrons"
              help="Override the alpha-electron count used by the SQD core."
              value={values.num_elec_a}
              disabled={disabled}
            />
            <NumberInputField
              basePath={basePath}
              field="num_elec_b"
              label="Beta Electrons"
              help="Override the beta-electron count used by the SQD core."
              value={values.num_elec_b}
              disabled={disabled}
            />
            <NumberInputField
              basePath={basePath}
              field="min_selected_configurations"
              label="Minimum Determinants"
              help="Keep at least this many determinants in the recovered basis."
              value={values.min_selected_configurations}
              disabled={disabled}
            />
            <NumberInputField
              basePath={basePath}
              field="seed"
              label="Seed"
              help="Fix the SQD sampling RNG for reproducible runs."
              value={values.seed}
              disabled={disabled}
            />
            <NumberInputField
              basePath={basePath}
              field="spin_sq_target"
              label="Spin S^2 Target"
              help="Optional target for spin diagnostics during selected-CI refinement."
              value={values.spin_sq_target}
              disabled={disabled}
            />
            <FormField
              label="Selected-CI Solver JSON"
              htmlFor={sciOptionsPath}
              error={
                isRunFormFieldTouched(form, sciOptionsPath)
                  ? getRunFormError(form, sciOptionsPath)
                  : undefined
              }
              help={{
                short: "Optional JSON object forwarded to the selected-CI solver.",
                anchor: "sci_solver_options",
              }}
            >
              <Textarea
                id={sciOptionsPath}
                value={values.sci_solver_options_text}
                onChange={(event) =>
                  form.setValue(sciOptionsPath, event.target.value, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
                onBlur={() =>
                  form.setValue(sciOptionsPath, values.sci_solver_options_text, {
                    shouldTouch: true,
                    shouldValidate: true,
                  })
                }
                disabled={disabled}
                placeholder='{"max_cycle": 64}'
              />
            </FormField>
          </div>
        </ExpertDisclosure>
      </div>
    </div>
  );
}
