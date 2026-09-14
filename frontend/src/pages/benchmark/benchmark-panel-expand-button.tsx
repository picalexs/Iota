import { Expand } from "lucide-react";

export function ExpandPanelButton({
  label,
  onClick,
}: Readonly<{ label: string; onClick: () => void }>) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      aria-label={`Expand ${label} fullscreen`}
      title={`Expand ${label} fullscreen`}
    >
      <Expand className="size-3.5" />
    </button>
  );
}
