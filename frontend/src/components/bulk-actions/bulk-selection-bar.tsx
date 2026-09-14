import { useId, type ComponentProps } from "react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

export interface BulkSelectionAction {
  readonly key: string;
  readonly label: string;
  readonly onClick: () => void | Promise<void>;
  readonly icon?: LucideIcon;
  readonly variant?: ComponentProps<typeof Button>["variant"];
  readonly disabled?: boolean;
}

interface BulkSelectionBarProps {
  readonly itemLabel: string;
  readonly totalVisibleCount: number;
  readonly selectedCount: number;
  readonly allVisibleSelected: boolean;
  readonly someVisibleSelected: boolean;
  readonly actions: readonly BulkSelectionAction[];
  readonly onToggleSelectAllVisible: (selected: boolean) => void;
  readonly onClearSelection: () => void;
  readonly actionError?: string | null;
  readonly className?: string;
}

function getBulkSelectionCheckedState(
  allVisibleSelected: boolean,
  someVisibleSelected: boolean,
): boolean | "indeterminate" {
  if (allVisibleSelected) {
    return true;
  }

  return someVisibleSelected ? "indeterminate" : false;
}

export function BulkSelectionBar({
  itemLabel,
  totalVisibleCount,
  selectedCount,
  allVisibleSelected,
  someVisibleSelected,
  actions,
  onToggleSelectAllVisible,
  onClearSelection,
  actionError,
  className,
}: BulkSelectionBarProps) {
  const selectAllId = useId();
  const selectionSummary = `${selectedCount} selected`;
  const visibilitySummary = `${totalVisibleCount} visible on this page`;
  const selectAllState = getBulkSelectionCheckedState(allVisibleSelected, someVisibleSelected);

  return (
    <div
      role="toolbar"
      aria-label={`Bulk actions for ${itemLabel}`}
      className={cn(
        "flex flex-col gap-3 border-b bg-muted/20 px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor={selectAllId} className="inline-flex items-center gap-2 text-sm font-medium">
          <Checkbox
            id={selectAllId}
            aria-label={`Select all visible ${itemLabel}`}
            checked={selectAllState}
            onCheckedChange={(checked) => onToggleSelectAllVisible(Boolean(checked))}
          />
          <span>Select all</span>
        </label>
        <Badge variant="secondary" className="rounded-sm px-2 py-1 text-xs font-medium">
          {selectionSummary}
        </Badge>
        <span className="text-xs text-muted-foreground">{visibilitySummary}</span>
      </div>

      <div className="flex flex-col gap-2 sm:items-end">
        <div className="flex flex-wrap justify-start gap-2 sm:justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 text-xs"
            onClick={onClearSelection}
            disabled={selectedCount === 0}
          >
            Clear
          </Button>
          {actions.map(({ key, label, onClick, icon: Icon, variant = "outline", disabled }) => (
            <Button
              key={key}
              type="button"
              variant={variant}
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                onClick();
              }}
              disabled={disabled}
            >
              {Icon ? <Icon className="size-3.5" /> : null}
              {label}
            </Button>
          ))}
        </div>
        {actionError ? (
          <p role="alert" className="text-xs text-destructive sm:max-w-96 sm:text-right">
            {actionError}
          </p>
        ) : null}
      </div>
    </div>
  );
}
