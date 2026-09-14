import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { formatDuration } from "@/lib/format-duration";
import type { RunEstimate } from "@/types/run";
import { useRunFormContext } from "./run-form-context";

interface EstimateSummaryProps {
  estimate: RunEstimate | null;
  loading: boolean;
}

export function EstimateSummary({ estimate, loading }: EstimateSummaryProps) {
  const {
    formState: { isValid },
  } = useRunFormContext();

  if (!isValid) return null;

  if (loading) {
    return (
      <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
        <Skeleton className="h-5 w-full" />
      </div>
    );
  }

  if (!estimate) return null;

  const primaryIterations =
    estimate.estimated_primary_iterations ?? estimate.estimated_total_iterations;
  const hasReferenceWork =
    estimate.estimated_reference_iterations != null && estimate.reference_workload != null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
      <span>
        ~
        <span className="font-mono tabular-nums text-foreground">
          {primaryIterations ?? "—"}
        </span>{" "}
        native work units
      </span>
      {hasReferenceWork && (
        <>
          <span aria-hidden="true">·</span>
          <span>
            plus {estimate.estimated_reference_iterations} {estimate.reference_workload} evaluations
          </span>
        </>
      )}
      {estimate.estimated_total_seconds != null && (
        <>
          <span aria-hidden="true">·</span>
          <span>
            ~
            <span className="font-mono tabular-nums text-foreground">
              {formatDuration(estimate.estimated_total_seconds)}
            </span>
          </span>
        </>
      )}
      {estimate.confidence != null && (
        <>
          <span aria-hidden="true">·</span>
          <span className="flex items-center gap-2">
            Confidence:
            <Badge variant="secondary" className="font-mono tabular-nums">
              {Math.round(estimate.confidence * 100)}%
            </Badge>
          </span>
        </>
      )}
    </div>
  );
}
