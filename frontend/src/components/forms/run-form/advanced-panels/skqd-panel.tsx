import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumberSlider } from "@/components/ui/number-slider";
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import { SKQDSamplingSection } from "./skqd-sampling-section";

interface SKQDPanelProps {
  disabled?: boolean;
  onResetRecommended?: () => void;
}

export function SKQDPanel({ disabled = false, onResetRecommended }: SKQDPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_skqd");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Sample each Krylov state, merge the sampled union, and solve its selected-CI space.
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

      <SKQDSamplingSection disabled={disabled} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField
          label="Time Step"
          htmlFor="advanced-skqd-time-step-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_skqd.time_step")
              ? getRunFormError(form, "advanced_skqd.time_step")
              : undefined
          }
          help={{
            short: "Sampling time step forwarded into the Krylov-extension stage.",
            anchor: "time_step",
          }}
        >
          <Input
            id="advanced-skqd-time-step-input"
            type="number"
            inputMode="decimal"
            step="any"
            min={RUN_CONSTRAINTS.skqd.time_step.min}
            value={values.time_step ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_skqd.time_step",
                event.target.value === "" ? null : Number(event.target.value),
                {
                  shouldDirty: true,
                  shouldValidate: true,
                },
              )
            }
            onBlur={() =>
              form.setValue("advanced_skqd.time_step", values.time_step, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Krylov Extension Dimension"
          htmlFor="advanced-skqd-krylov-extension-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_skqd.krylov_extension_dim")
              ? getRunFormError(form, "advanced_skqd.krylov_extension_dim")
              : undefined
          }
          help={{
            short: "Number of sampled Krylov states included in the cumulative union.",
            anchor: "krylov_extension_dim",
          }}
        >
          <NumberSlider
            id="advanced-skqd-krylov-extension-input"
            value={values.krylov_extension_dim}
            min={RUN_CONSTRAINTS.skqd.krylov_extension_dim.min}
            max={RUN_CONSTRAINTS.skqd.krylov_extension_dim.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_skqd.krylov_extension_dim", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_skqd.krylov_extension_dim", values.krylov_extension_dim, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Residual Tolerance"
          htmlFor="advanced-skqd-residual-tolerance-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_skqd.residual_tolerance")
              ? getRunFormError(form, "advanced_skqd.residual_tolerance")
              : undefined
          }
          help={{
            short: "Stopping threshold for the projected SKQD solve.",
            anchor: "residual_tolerance",
          }}
        >
          <Input
            id="advanced-skqd-residual-tolerance-input"
            type="number"
            inputMode="decimal"
            step="any"
            min={0}
            value={values.residual_tolerance ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_skqd.residual_tolerance",
                event.target.value === "" ? null : Number(event.target.value),
                {
                  shouldDirty: true,
                  shouldValidate: true,
                },
              )
            }
            onBlur={() =>
              form.setValue("advanced_skqd.residual_tolerance", values.residual_tolerance, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>
      </div>
    </div>
  );
}
