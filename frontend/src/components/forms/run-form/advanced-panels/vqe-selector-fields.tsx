import type { FieldPath } from "react-hook-form";

import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
} from "@/components/forms/run-form/run-form-context-helpers";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  ConfigChoiceMetadata,
  RunConfigMetadataResponse,
  SimulationRunFormData,
} from "@/types/run";

interface VqeSelectorFieldsProps {
  ansatzPath: FieldPath<SimulationRunFormData>;
  optimizerPath: FieldPath<SimulationRunFormData>;
  ansatzValue: string;
  optimizerValue: string;
  metadata: RunConfigMetadataResponse | null;
  disabled?: boolean;
  ansatzLabel?: string;
  optimizerLabel?: string;
  ansatzHelpAnchor?: string;
  optimizerHelpAnchor?: string;
}

function allowedOptimizerOptions(choice: ConfigChoiceMetadata | undefined): string[] {
  const raw =
    choice?.metadata.allowed_option_keys ??
    choice?.metadata.allowed_options ??
    choice?.metadata.allowedOptions;

  return Array.isArray(raw)
    ? raw.filter((value): value is string => typeof value === "string")
    : [];
}

export function VqeSelectorFields({
  ansatzPath,
  optimizerPath,
  ansatzValue,
  optimizerValue,
  metadata,
  disabled = false,
  ansatzLabel = "Ansatz",
  optimizerLabel = "Optimizer",
  ansatzHelpAnchor = "ansatz",
  optimizerHelpAnchor = "optimizer",
}: VqeSelectorFieldsProps) {
  const form = useRunFormContext();
  const ansatzes = metadata?.ansatzes ?? [];
  const optimizers = metadata?.optimizers ?? [];
  const selectedOptimizer = optimizers.find((choice) => choice.id === optimizerValue);
  const allowedOptions = allowedOptimizerOptions(selectedOptimizer);

  return (
    <>
      <FormField
        label={ansatzLabel}
        htmlFor={`${ansatzPath}-select`}
        required
        error={
          isRunFormFieldTouched(form, ansatzPath) ? getRunFormError(form, ansatzPath) : undefined
        }
        help={{
          short: "Select the circuit template used to prepare the trial wavefunction.",
          anchor: ansatzHelpAnchor,
          href: "/info/components/ansatzes",
        }}
      >
        <Select
          value={ansatzValue}
          onValueChange={(value) =>
            form.setValue(ansatzPath, value, {
              shouldDirty: true,
              shouldTouch: true,
              shouldValidate: true,
            })
          }
        >
          <SelectTrigger
            id={`${ansatzPath}-select`}
            disabled={disabled || ansatzes.length === 0}
            aria-invalid={!!getRunFormError(form, ansatzPath)}
          >
            <SelectValue
              placeholder={ansatzes.length === 0 ? "Loading ansatzes..." : "Select ansatz"}
            />
          </SelectTrigger>
          <SelectContent>
            {ansatzes.map((choice) => (
              <SelectItem key={choice.id} value={choice.id}>
                {choice.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FormField>

      <FormField
        label={optimizerLabel}
        htmlFor={`${optimizerPath}-select`}
        required
        error={
          isRunFormFieldTouched(form, optimizerPath)
            ? getRunFormError(form, optimizerPath)
            : undefined
        }
        help={{
          short: "Choose the classical optimizer that updates variational parameters.",
          anchor: optimizerHelpAnchor,
          href: "/info/components/optimizers",
        }}
      >
        <div className="space-y-2">
          <Select
            value={optimizerValue}
            onValueChange={(value) =>
              form.setValue(optimizerPath, value, {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              })
            }
          >
            <SelectTrigger
              id={`${optimizerPath}-select`}
              disabled={disabled || optimizers.length === 0}
              aria-invalid={!!getRunFormError(form, optimizerPath)}
            >
              <SelectValue
                placeholder={optimizers.length === 0 ? "Loading optimizers..." : "Select optimizer"}
              />
            </SelectTrigger>
            <SelectContent>
              {optimizers.map((choice) => (
                <SelectItem key={choice.id} value={choice.id}>
                  {choice.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {allowedOptions.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              Allowed JSON option keys: <code>{allowedOptions.join(", ")}</code>
            </p>
          ) : null}
        </div>
      </FormField>
    </>
  );
}
