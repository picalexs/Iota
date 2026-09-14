import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface WorkflowStep {
  readonly label: string;
  readonly value: ReactNode;
  readonly hint?: ReactNode;
}

interface WorkflowRailProps {
  readonly steps: WorkflowStep[];
  readonly className?: string;
}

export function WorkflowRail({ steps, className }: WorkflowRailProps) {
  return (
    <div
      className={cn(
        "grid overflow-hidden rounded-md border border-border/60 bg-muted/20",
        steps.length > 1 ? "sm:grid-cols-2 xl:grid-cols-none xl:grid-flow-col xl:auto-cols-fr" : "",
        className,
      )}
    >
      {steps.map((step, index) => (
        <div
          key={step.label}
          className={cn(
            "flex min-w-0 flex-col gap-1 px-3 py-2.5",
            index > 0 && "border-t border-border/60 sm:border-t-0 xl:border-l",
          )}
        >
          <span className="text-[10px] font-medium uppercase text-muted-foreground">
            {step.label}
          </span>
          <div className="min-w-0 text-sm font-medium leading-5">{step.value}</div>
          {step.hint ? (
            <div className="min-w-0 text-[11px] leading-4 text-muted-foreground">{step.hint}</div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
