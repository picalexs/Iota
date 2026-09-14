import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface BackendRefreshButtonProps {
  onClick?: () => void;
  disabled?: boolean;
  refreshing?: boolean;
  "aria-label"?: string;
}

export function BackendRefreshButton({
  onClick,
  disabled,
  refreshing,
  "aria-label": ariaLabel = "Refresh",
}: BackendRefreshButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || refreshing}
      aria-label={ariaLabel}
      className="flex w-11 shrink-0 self-stretch items-center justify-center rounded-md border border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
    >
      <RefreshCw className={cn("size-4", refreshing && "animate-spin")} />
    </button>
  );
}
