import { CheckCircle2, XCircle } from "lucide-react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { ConvergenceInsight } from "@/lib/results/convergence-status";
import { getRunProgressLabel } from "@/lib/run-status-display";
import type { RunResultResponse, RunStatus } from "@/types/run";

interface ConvergenceStatusIndicatorProps {
  readonly result: RunResultResponse | null;
  readonly status?: RunStatus | null;
  readonly isRunning?: boolean;
  readonly insight: ConvergenceInsight | null;
}

function renderStatus(
  result: RunResultResponse | null,
  status?: RunStatus | null,
  isRunning?: boolean,
) {
  if (result == null) {
    const nextStatus = status ?? (isRunning ? "RUNNING" : null);
    return <span className="text-muted-foreground">{getRunProgressLabel(nextStatus)}</span>;
  }

  return result.converged ? (
    <span className="inline-flex items-center gap-1.5 text-success">
      <CheckCircle2 className="size-4" /> Yes
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-destructive">
      <XCircle className="size-4" /> No
    </span>
  );
}

export function ConvergenceStatusIndicator({
  result,
  status,
  isRunning,
  insight,
}: ConvergenceStatusIndicatorProps) {
  const statusNode = renderStatus(result, status, isRunning);

  if (insight == null) {
    return statusNode;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-sm text-inherit transition hover:underline decoration-dotted underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            aria-label="Convergence status details"
          >
            {statusNode}
          </button>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          align="start"
          sideOffset={6}
          collisionPadding={16}
          className="max-w-[min(24rem,calc(100vw-2rem))] px-3 py-2"
        >
          <div className="space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wide text-background/70">
              {insight.label}
            </p>
            <p className="font-medium text-background">{insight.value}</p>
            {insight.helper ? (
              <p className="text-[11px] leading-snug text-background/80">{insight.helper}</p>
            ) : null}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
