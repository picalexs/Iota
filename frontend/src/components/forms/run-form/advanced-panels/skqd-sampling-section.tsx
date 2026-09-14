import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import { ExpertDisclosure } from "./expert-disclosure";
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
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import type { FieldPath } from "react-hook-form";
import type { SimulationRunFormData } from "@/types/run";

type SKQDField = keyof SimulationRunFormData["advanced_skqd"];

function fieldPath(field: SKQDField): FieldPath<SimulationRunFormData> {
  return `advanced_skqd.${field}` as FieldPath<SimulationRunFormData>;
}

function NumberInputField({
  field,
  label,
  help,
  value,
  disabled,
}: Readonly<{
  field: SKQDField;
  label: string;
  help: string;
  value: number | null;
  disabled: boolean;
}>) {
  const form = useRunFormContext();
  const path = fieldPath(field);
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
        onBlur={() => form.setValue(path, value, { shouldTouch: true, shouldValidate: true })}
        disabled={disabled}
      />
    </FormField>
  );
}

export function SKQDSamplingSection({ disabled = false }: Readonly<{ disabled?: boolean }>) {
  const form = useRunFormContext();
  const values = form.watch("advanced_skqd");
  const maxDimModePath = fieldPath("max_dim_mode");
  const sciOptionsPath = fieldPath("sci_solver_options_text");

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <FormField
        label="Samples per Krylov State"
        htmlFor={fieldPath("samples_per_state")}
        required
        error={
          isRunFormFieldTouched(form, fieldPath("samples_per_state"))
            ? getRunFormError(form, fieldPath("samples_per_state"))
            : undefined
        }
        help={{
          short: "Number of computational-basis samples collected for each Krylov state.",
          anchor: "samples_per_state",
        }}
      >
        <NumberSlider
          id={fieldPath("samples_per_state")}
          value={values.samples_per_state}
          min={RUN_CONSTRAINTS.skqd.samples_per_state.min}
          max={RUN_CONSTRAINTS.skqd.samples_per_state.max}
          step={1}
          onChange={(next) =>
            form.setValue(fieldPath("samples_per_state"), next, {
              shouldDirty: true,
              shouldValidate: true,
            })
          }
          disabled={disabled}
        />
      </FormField>

      <FormField
        label="Selected-CI Cap"
        htmlFor={maxDimModePath}
        help={{
          short: "Limit the sampled determinant union used by the SKQD solve.",
          anchor: "max_dim",
        }}
      >
        <div className="space-y-3">
          <Select
            value={values.max_dim_mode}
            onValueChange={(value) =>
              form.setValue(maxDimModePath, value as "shared" | "spin_resolved", {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              })
            }
          >
            <SelectTrigger id={maxDimModePath} disabled={disabled}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="shared">One determinant cap</SelectItem>
              <SelectItem value="spin_resolved">Alpha/beta caps</SelectItem>
            </SelectContent>
          </Select>
          {values.max_dim_mode === "shared" ? (
            <NumberInputField
              field="max_dim"
              label="Shared Determinant Cap"
              help="Use one selected-CI determinant limit for both spin sectors."
              value={values.max_dim}
              disabled={disabled}
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <NumberInputField
                field="max_dim_a"
                label="Alpha Determinant Cap"
                help="Selected-CI cap for alpha determinants."
                value={values.max_dim_a}
                disabled={disabled}
              />
              <NumberInputField
                field="max_dim_b"
                label="Beta Determinant Cap"
                help="Selected-CI cap for beta determinants."
                value={values.max_dim_b}
                disabled={disabled}
              />
            </div>
          )}
        </div>
      </FormField>

      <div className="md:col-span-2">
        <ExpertDisclosure description="Expose sector, selection, and selected-CI solver settings.">
          <div className="grid gap-4 md:grid-cols-2">
            <NumberInputField
              field="num_elec_a"
              label="Alpha Electrons"
              help="Override the alpha-electron count used for sector postselection."
              value={values.num_elec_a}
              disabled={disabled}
            />
            <NumberInputField
              field="num_elec_b"
              label="Beta Electrons"
              help="Override the beta-electron count used for sector postselection."
              value={values.num_elec_b}
              disabled={disabled}
            />
            <NumberInputField
              field="min_selected_configurations"
              label="Minimum Determinants"
              help="Keep at least this many sampled determinants when available."
              value={values.min_selected_configurations}
              disabled={disabled}
            />
            <NumberInputField
              field="seed"
              label="Seed"
              help="Fix the SKQD sampling RNG for reproducible runs."
              value={values.seed}
              disabled={disabled}
            />
            <NumberInputField
              field="spin_sq_target"
              label="Spin S² Target"
              help="Optional target used for spin diagnostics."
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
                short: "Optional JSON forwarded to selected-CI solving.",
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
