import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { NumberSlider } from "@/components/ui/number-slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormField } from "@/components/forms/form-field";
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";

interface QFDPanelProps {
  disabled?: boolean;
  onResetRecommended?: () => void;
}

export function QFDPanel({ disabled, onResetRecommended }: QFDPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_qfd");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Tune the time grid, evolution window, and projected-solve tolerance.
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
        <FormField
          label="Number of Time Points"
          htmlFor="advanced-qfd-time-points-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_qfd.num_time_points")
              ? getRunFormError(form, "advanced_qfd.num_time_points")
              : undefined
          }
          help={{
            short: "Choose how many points QFD samples across the time window.",
            anchor: "num_time_points",
          }}
        >
          <NumberSlider
            id="advanced-qfd-time-points-input"
            value={values.num_time_points}
            min={RUN_CONSTRAINTS.qfd.num_time_points.min}
            max={RUN_CONSTRAINTS.qfd.num_time_points.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_qfd.num_time_points", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_qfd.num_time_points", values.num_time_points, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Max Time"
          htmlFor="advanced-qfd-max-time-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_qfd.max_time")
              ? getRunFormError(form, "advanced_qfd.max_time")
              : undefined
          }
          help={{
            short: "Set the end of the QFD evolution window.",
            anchor: "max_time",
          }}
        >
          <Input
            id="advanced-qfd-max-time-input"
            type="number"
            inputMode="decimal"
            min={RUN_CONSTRAINTS.qfd.max_time.min}
            step="any"
            value={values.max_time ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_qfd.max_time",
                event.target.value === "" ? null : Number(event.target.value),
                { shouldDirty: true, shouldValidate: true },
              )
            }
            onBlur={() =>
              form.setValue("advanced_qfd.max_time", values.max_time, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            aria-invalid={!!getRunFormError(form, "advanced_qfd.max_time")}
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Time Grid Type"
          htmlFor="advanced-qfd-time-grid-type-select"
          required
          error={
            isRunFormFieldTouched(form, "advanced_qfd.time_grid_type")
              ? getRunFormError(form, "advanced_qfd.time_grid_type")
              : undefined
          }
          help={{
            short: "Choose how the time samples are spaced across the evolution interval.",
            anchor: "time_grid_type",
          }}
        >
          <Select
            value={values.time_grid_type}
            onValueChange={(v) => {
              form.setValue("advanced_qfd.time_grid_type", v as "linear" | "geometric", {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              });
            }}
          >
            <SelectTrigger
              id="advanced-qfd-time-grid-type-select"
              disabled={disabled}
              aria-invalid={!!getRunFormError(form, "advanced_qfd.time_grid_type")}
            >
              <SelectValue placeholder="Select time grid type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="linear">linear</SelectItem>
              <SelectItem value="geometric">geometric</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField
          label="Trotter Steps"
          htmlFor="advanced-qfd-trotter-steps-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_qfd.trotter_steps")
              ? getRunFormError(form, "advanced_qfd.trotter_steps")
              : undefined
          }
          help={{
            short: "Split QFD time-evolution circuits into more product-formula steps.",
            anchor: "trotter_steps",
          }}
        >
          <NumberSlider
            id="advanced-qfd-trotter-steps-input"
            value={values.trotter_steps}
            min={RUN_CONSTRAINTS.qfd.trotter_steps.min}
            max={RUN_CONSTRAINTS.qfd.trotter_steps.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_qfd.trotter_steps", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_qfd.trotter_steps", values.trotter_steps, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <div className="md:col-span-2">
          <FormField
            label="Residual Tolerance"
            htmlFor="advanced-qfd-residual-tolerance-input"
            required
            error={
              isRunFormFieldTouched(form, "advanced_qfd.residual_tolerance")
                ? getRunFormError(form, "advanced_qfd.residual_tolerance")
                : undefined
            }
            help={{
              short: "Stopping threshold for the dense classical solve (smaller is stricter).",
              anchor: "residual_tolerance",
            }}
          >
            <Input
              id="advanced-qfd-residual-tolerance-input"
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={values.residual_tolerance ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_qfd.residual_tolerance",
                  event.target.value === "" ? null : Number(event.target.value),
                  { shouldDirty: true, shouldValidate: true },
                )
              }
              onBlur={() =>
                form.setValue("advanced_qfd.residual_tolerance", values.residual_tolerance, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              aria-invalid={!!getRunFormError(form, "advanced_qfd.residual_tolerance")}
              disabled={disabled}
            />
          </FormField>
        </div>
      </div>
    </div>
  );
}
