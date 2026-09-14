import { Atom, Grid3x3, Layers, Settings2, Sigma, Sparkles, Waves, Zap } from "lucide-react";
import { FormField } from "@/components/forms/form-field";
import { SelectableCard } from "@/components/ui/selectable-card";
import {
  elevatedSurfaceClassName,
  selectableCardIconClassName,
  selectableSurfaceClassName,
} from "@/lib/interactive-styles";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { RunAlgorithm } from "@/types/run";
import { useRunFormContext } from "./run-form-context";

const ALGORITHM_OPTIONS: {
  value: RunAlgorithm;
  label: string;
  subtitle: string;
  icon: typeof Atom;
}[] = [
  { value: "vqe", label: "VQE", subtitle: "Variational", icon: Atom },
  { value: "sqd", label: "SQD", subtitle: "Sampled", icon: Grid3x3 },
  { value: "kqd", label: "KQD", subtitle: "Krylov", icon: Layers },
  { value: "qfd", label: "QFD", subtitle: "Frequency", icon: Waves },
  { value: "qse", label: "QSE", subtitle: "Subspace", icon: Sigma },
  { value: "skqd", label: "SKQD", subtitle: "Hybrid", icon: Sparkles },
];

interface AlgorithmSectionProps {
  disabled?: boolean;
  disabledAlgorithms?: Map<RunAlgorithm, string>;
}

export function ModeSection({ disabled }: AlgorithmSectionProps) {
  const form = useRunFormContext();
  const mode = form.watch("mode");

  return (
    <FormField
      label="Mode"
      htmlFor="mode-option-easy"
      required
      help={{
        short:
          "Guided presets choose algorithm-specific budgets; manual mode exposes each parameter.",
        anchor: "mode",
      }}
    >
      <div
        role="group"
        aria-label="Mode selection"
        className="grid grid-cols-1 gap-3 md:grid-cols-2"
      >
        <SelectableCard
          id="mode-option-easy"
          selected={mode === "easy"}
          disabled={disabled}
          aria-pressed={mode === "easy"}
          onClick={() =>
            form.setValue("mode", "easy", {
              shouldDirty: true,
              shouldTouch: true,
              shouldValidate: true,
            })
          }
          className="items-start gap-3"
        >
          <div className={selectableCardIconClassName}>
            <Zap className="size-4" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-semibold">Easy</span>
            <span className="text-sm text-muted-foreground">
              Guided presets with visible budgets.
            </span>
          </div>
        </SelectableCard>

        <SelectableCard
          id="mode-option-advanced"
          selected={mode === "advanced"}
          disabled={disabled}
          aria-pressed={mode === "advanced"}
          onClick={() =>
            form.setValue("mode", "advanced", {
              shouldDirty: true,
              shouldTouch: true,
              shouldValidate: true,
            })
          }
          className="items-start gap-3"
        >
          <div className={selectableCardIconClassName}>
            <Settings2 className="size-4" />
          </div>
          <div className="flex flex-col gap-1">
            <span className="font-semibold">Manual</span>
            <span className="text-sm text-muted-foreground">
              Direct control over each supported parameter.
            </span>
          </div>
        </SelectableCard>
      </div>
    </FormField>
  );
}

export function AlgorithmSection({ disabled, disabledAlgorithms }: AlgorithmSectionProps) {
  const form = useRunFormContext();
  const algorithm = form.watch("algorithm");

  return (
    <div className="flex flex-col gap-4">
      <FormField
        label="Algorithm"
        htmlFor="algorithm-option-vqe"
        required
        help={{
          short: "Pick the quantum workflow used to approximate the molecule's energy.",
          anchor: "algorithm",
        }}
      >
        <div
          role="group"
          aria-label="Algorithm selection"
          className="grid grid-cols-3 gap-2 md:grid-cols-6"
        >
          {ALGORITHM_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const disabledReason = disabledAlgorithms?.get(opt.value);
            const isDisabledByMolecule = disabledReason != null;
            const isDisabled = disabled || isDisabledByMolecule;

            const btn = (
              <button
                key={opt.value}
                id={`algorithm-option-${opt.value}`}
                type="button"
                disabled={isDisabled}
                aria-pressed={algorithm === opt.value}
                data-selected={algorithm === opt.value && !isDisabled ? "true" : "false"}
                onClick={() => {
                  if (isDisabled) return;
                  form.setValue("algorithm", opt.value, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  });
                }}
                className={cn(
                  "relative flex min-h-24 w-full flex-col items-center justify-center gap-2 rounded-xl border px-3 py-4 text-center text-xs",
                  elevatedSurfaceClassName,
                  selectableSurfaceClassName,
                  isDisabledByMolecule && "cursor-not-allowed opacity-40",
                  disabled && !isDisabledByMolecule && "cursor-not-allowed opacity-50",
                )}
              >
                <Icon className="size-4" />
                <span className="font-semibold tracking-wide">{opt.label}</span>
                <span className="opacity-75">{opt.subtitle}</span>
              </button>
            );

            if (isDisabledByMolecule) {
              return (
                <Tooltip key={opt.value}>
                  <TooltipTrigger asChild>
                    <span className="block">{btn}</span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64 text-center text-xs">
                    {disabledReason}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return btn;
          })}
        </div>
      </FormField>
    </div>
  );
}
