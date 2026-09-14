import type React from "react";

interface OutcomeStatProps {
  label: string;
  value: React.ReactNode;
  helper?: React.ReactNode;
  className?: string;
  valueClassName?: string;
}

export function OutcomeStat({ label, value, helper, className, valueClassName }: OutcomeStatProps) {
  return (
    <div
      className={["rounded-lg border border-border/80 bg-muted/30 px-4 py-3", className]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={["mt-1 text-lg font-semibold tabular-nums", valueClassName]
          .filter(Boolean)
          .join(" ")}
      >
        {value}
      </div>
      {helper ? <div className="mt-1 text-xs text-muted-foreground">{helper}</div> : null}
    </div>
  );
}

interface IterationStatProps {
  label: string;
  value: React.ReactNode;
  valueNow: number | null;
  valueMax: number;
  showIncomplete: boolean;
}

export function IterationStat({
  label,
  value,
  valueNow,
  valueMax,
  showIncomplete,
}: IterationStatProps) {
  const progress =
    valueNow != null && valueMax > 0 ? Math.min(100, (valueNow / valueMax) * 100) : 0;

  return (
    <div className="rounded-lg border border-border/80 bg-muted/30 px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
      {valueNow != null && valueMax > 0 && (
        <div className="relative mt-1.5">
          <progress
            className="h-1.5 w-full overflow-hidden rounded-full bg-muted [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:rounded-full [&::-moz-progress-bar]:bg-primary"
            value={valueNow}
            max={valueMax}
            aria-label="Iteration progress"
          />
          {showIncomplete && valueNow < valueMax && (
            <div
              className="absolute inset-y-0 rounded-r-full"
              style={{
                left: `${progress}%`,
                right: 0,
                backgroundImage:
                  "repeating-linear-gradient(45deg, color-mix(in srgb, var(--primary) 35%, transparent) 0 3px, transparent 3px 7px)",
              }}
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </div>
  );
}
