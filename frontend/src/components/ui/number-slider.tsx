import { useMemo, useRef, useState } from "react";

import { Input } from "./input";
import { Slider } from "./slider";

type NumberSliderProps = Readonly<{
  id: string;
  value: number | null;
  onChange: (next: number) => void;
  min: number;
  max: number;
  step: number;
  disabled?: boolean;
  onBlur?: () => void;
}>;

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function countDecimals(step: number): number {
  const stepText = step.toString();
  const dotIndex = stepText.indexOf(".");
  if (dotIndex < 0) return 0;
  return stepText.length - dotIndex - 1;
}

function formatValue(value: number, step: number): string {
  const decimals = countDecimals(step);
  if (decimals === 0) return String(Math.round(value));
  return value.toFixed(decimals);
}

export function NumberSlider({
  id,
  value,
  onChange,
  min,
  max,
  step,
  disabled,
  onBlur,
}: NumberSliderProps) {
  const current = useMemo(() => clamp(value ?? min, min, max), [value, min, max]);
  const [inputValue, setInputValue] = useState<string>(() => formatValue(current, step));
  const syncedValueRef = useRef({ current, step });
  if (syncedValueRef.current.current !== current || syncedValueRef.current.step !== step) {
    syncedValueRef.current = { current, step };
    setInputValue(formatValue(current, step));
  }

  const commitInput = () => {
    const parsed = Number(inputValue);
    if (!Number.isFinite(parsed)) {
      setInputValue(formatValue(current, step));
      onBlur?.();
      return;
    }

    const next = clamp(parsed, min, max);
    onChange(next);
    setInputValue(formatValue(next, step));
    onBlur?.();
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_7rem] grid-rows-[auto_auto] items-center gap-x-3">
      <div className="row-start-1 self-center">
        <Slider
          value={[current]}
          onValueChange={([next]) => {
            if (next == null) return;
            onChange(clamp(next, min, max));
          }}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          aria-label={id}
        />
      </div>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        step={step}
        min={min}
        max={max}
        value={inputValue}
        onChange={(event) => setInputValue(event.target.value)}
        onBlur={commitInput}
        disabled={disabled}
        className="row-start-1 self-center"
      />

      <div className="row-start-2 flex items-center justify-between text-xs text-muted-foreground tabular-nums">
        <span>{formatValue(min, step)}</span>
        <span>{formatValue(max, step)}</span>
      </div>
    </div>
  );
}
