import { Check } from "lucide-react";

import type { EasyGoal } from "@/types/run";
import { GUIDED_GOAL_OPTIONS, guidedPresetHighlights } from "@/lib/easy-mode-presets";
import { elevatedSurfaceClassName, selectableSurfaceClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import { useRunFormContext } from "./run-form-context";

interface EasyGoalSliderProps {
  id: string;
  disabled?: boolean;
}

export function EasyGoalSlider({ id, disabled }: EasyGoalSliderProps) {
  const form = useRunFormContext();
  const algorithm = form.watch("algorithm");
  const value = form.watch("easy_options.goal");
  const onChange = (nextGoal: EasyGoal) => {
    form.setValue("easy_options.goal", nextGoal, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    });
  };

  return (
    <div
      id={id}
      role="group"
      aria-label="Accuracy preset selection"
      className="grid gap-3 md:grid-cols-3"
    >
      {GUIDED_GOAL_OPTIONS.map((option) => {
        const selected = option.value === value;
        const highlights = guidedPresetHighlights(algorithm, option.value);

        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            data-selected={selected ? "true" : "false"}
            onClick={() => onChange(option.value)}
            className={cn(
              "flex min-h-40 flex-col items-start gap-2 rounded-lg px-4 py-4 text-left",
              elevatedSurfaceClassName,
              selectableSurfaceClassName,
              disabled && "cursor-not-allowed opacity-50",
            )}
          >
            <div className="flex w-full items-center justify-between gap-3">
              <span className="text-sm font-semibold">{option.label}</span>
              {selected ? <Check className="size-4 text-primary" aria-hidden="true" /> : null}
            </div>
            <span className="text-sm text-muted-foreground">{option.description}</span>
            <span className="flex flex-col gap-1 text-xs text-muted-foreground">
              {highlights.map((highlight) => (
                <span key={highlight}>{highlight}</span>
              ))}
            </span>
          </button>
        );
      })}
    </div>
  );
}
