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
import { kqdUsesKnownBranchEstimatorPath } from "@/lib/run-form-recommendations";

interface KQDPanelProps {
  disabled?: boolean;
  onResetRecommended?: () => void;
}

export function KQDPanel({ disabled, onResetRecommended }: KQDPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_kqd");
  const backendTarget = form.watch("backend_target");
  const hasNoiseProfile = form.watch("noise_profile") !== null;
  const requiresBranchEstimator = kqdUsesKnownBranchEstimatorPath(backendTarget, hasNoiseProfile);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Tune the Krylov basis size, time evolution, and projected-solve tolerance.
            {requiresBranchEstimator
              ? " IBM Runtime and noisy Aer paths require Trotter circuit evolution."
              : " Exact evolution uses a local matrix path."}
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
          label="Krylov Dimension"
          htmlFor="advanced-kqd-krylov-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_kqd.krylov_dim")
              ? getRunFormError(form, "advanced_kqd.krylov_dim")
              : undefined
          }
          help={{
            short: "Control the size of the Krylov subspace used during the KQD solve.",
            anchor: "krylov_dim",
          }}
        >
          <NumberSlider
            id="advanced-kqd-krylov-input"
            value={values.krylov_dim}
            min={RUN_CONSTRAINTS.kqd.krylov_dim.min}
            max={RUN_CONSTRAINTS.kqd.krylov_dim.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_kqd.krylov_dim", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_kqd.krylov_dim", values.krylov_dim, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Time Step"
          htmlFor="advanced-kqd-time-step-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_kqd.time_step")
              ? getRunFormError(form, "advanced_kqd.time_step")
              : undefined
          }
          help={{
            short: "Set the evolution step size used to build the Krylov basis.",
            anchor: "time_step",
          }}
        >
          <Input
            id="advanced-kqd-time-step-input"
            type="number"
            inputMode="decimal"
            min={RUN_CONSTRAINTS.kqd.time_step.min}
            step="any"
            value={values.time_step ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_kqd.time_step",
                event.target.value === "" ? null : Number(event.target.value),
                { shouldDirty: true, shouldValidate: true },
              )
            }
            onBlur={() =>
              form.setValue("advanced_kqd.time_step", values.time_step, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            aria-invalid={!!getRunFormError(form, "advanced_kqd.time_step")}
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Evolution Method"
          htmlFor="advanced-kqd-evolution-method-select"
          required
          error={
            isRunFormFieldTouched(form, "advanced_kqd.evolution_method")
              ? getRunFormError(form, "advanced_kqd.evolution_method")
              : undefined
          }
          help={{
            short: "Pick whether the time evolution is computed exactly or via Trotterization.",
            anchor: "evolution_method",
          }}
        >
          <Select
            value={values.evolution_method}
            onValueChange={(v) => {
              form.setValue("advanced_kqd.evolution_method", v as "exact" | "trotter", {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              });
            }}
          >
            <SelectTrigger
              id="advanced-kqd-evolution-method-select"
              disabled={disabled}
              aria-invalid={!!getRunFormError(form, "advanced_kqd.evolution_method")}
            >
              <SelectValue placeholder="Select evolution method" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="trotter">trotter</SelectItem>
              <SelectItem value="exact" disabled={requiresBranchEstimator}>
                exact
              </SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        {values.evolution_method === "trotter" && (
          <FormField
            label="Trotter Steps"
            htmlFor="advanced-kqd-trotter-steps-input"
            required
            error={
              isRunFormFieldTouched(form, "advanced_kqd.trotter_steps")
                ? getRunFormError(form, "advanced_kqd.trotter_steps")
                : undefined
            }
            help={{
              short:
                "Increase this to use finer Trotter splitting when the evolution method is Trotter.",
              anchor: "trotter_steps",
            }}
          >
            <Input
              id="advanced-kqd-trotter-steps-input"
              type="number"
              min={RUN_CONSTRAINTS.kqd.trotter_steps.min}
              max={RUN_CONSTRAINTS.kqd.trotter_steps.max}
              step={1}
              value={values.trotter_steps ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_kqd.trotter_steps",
                  event.target.value === "" ? null : Number(event.target.value),
                  { shouldDirty: true, shouldValidate: true },
                )
              }
              onBlur={() =>
                form.setValue("advanced_kqd.trotter_steps", values.trotter_steps, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              aria-invalid={!!getRunFormError(form, "advanced_kqd.trotter_steps")}
              disabled={disabled}
            />
          </FormField>
        )}

        <FormField
          label="Residual Tolerance"
          htmlFor="advanced-kqd-residual-tolerance-input"
          required
          error={
            isRunFormFieldTouched(form, "advanced_kqd.residual_tolerance")
              ? getRunFormError(form, "advanced_kqd.residual_tolerance")
              : undefined
          }
          help={{
            short: "Stopping threshold for the dense classical solve (smaller is stricter).",
            anchor: "residual_tolerance",
          }}
        >
          <Input
            id="advanced-kqd-residual-tolerance-input"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            value={values.residual_tolerance ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_kqd.residual_tolerance",
                event.target.value === "" ? null : Number(event.target.value),
                { shouldDirty: true, shouldValidate: true },
              )
            }
            onBlur={() =>
              form.setValue("advanced_kqd.residual_tolerance", values.residual_tolerance, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            aria-invalid={!!getRunFormError(form, "advanced_kqd.residual_tolerance")}
            disabled={disabled}
          />
        </FormField>
      </div>
    </div>
  );
}
