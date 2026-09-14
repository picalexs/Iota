import { Spinner } from "@/components/ui/spinner";

interface ChartEmptyStateProps {
  readonly message?: string;
  readonly pending?: boolean;
  readonly pendingMessage?: string;
}

export function ChartEmptyState({
  message = "No data available",
  pending = false,
  pendingMessage,
}: ChartEmptyStateProps) {
  const displayMessage = pending ? (pendingMessage ?? message) : message;
  const content = (
    <div className="flex items-center gap-2 text-sm italic text-muted-foreground">
      {pending ? <Spinner /> : null}
      <span>{displayMessage}</span>
    </div>
  );

  if (pending) {
    return (
      <output className="flex h-full min-h-[120px] items-center justify-center" aria-live="polite">
        {content}
      </output>
    );
  }

  return <div className="flex h-full min-h-[120px] items-center justify-center">{content}</div>;
}
