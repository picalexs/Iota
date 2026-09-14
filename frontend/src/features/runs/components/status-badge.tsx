import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/types/run";
import { getTimedOutFailureMessage } from "@/lib/run-failure";

type BadgeVariant = "success" | "destructive" | "warning" | "secondary" | "outline" | "info";

const STATUS_VARIANT: Record<RunStatus, BadgeVariant> = {
  COMPLETED: "success",
  FAILED: "destructive",
  RUNNING: "warning",
  PAUSING: "warning",
  PAUSED: "info",
  SUBMITTED_TO_IBM: "warning",
  QUEUED: "secondary",
  CREATED: "secondary",
  CANCELLED: "info",
  EXCLUDED: "outline",
};

const STATUS_LABEL: Record<RunStatus, string> = {
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  RUNNING: "RUNNING",
  PAUSING: "PAUSING",
  PAUSED: "PAUSED",
  SUBMITTED_TO_IBM: "IBM pending",
  QUEUED: "QUEUED",
  CREATED: "CREATED",
  CANCELLED: "CANCELLED",
  EXCLUDED: "EXCLUDED",
};

type StatusBadgeProps = Readonly<{
  status: RunStatus;
  metadata?: Record<string, unknown> | null;
}>;

export function StatusBadge({ status, metadata = null }: StatusBadgeProps) {
  const timeoutMessage = status === "FAILED" ? getTimedOutFailureMessage(metadata) : null;
  const variant = timeoutMessage === null ? STATUS_VARIANT[status] : "warning";
  const label = timeoutMessage === null ? STATUS_LABEL[status] : "TIMED OUT";

  return (
    <Badge variant={variant} aria-label={`Status: ${label}`}>
      {label}
    </Badge>
  );
}
