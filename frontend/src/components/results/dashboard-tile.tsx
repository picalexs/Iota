import { useState, type ReactNode } from "react";
import { Expand, GripVertical, HelpCircle } from "lucide-react";
import { panelSurfaceClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { FullscreenPanel } from "@/components/ui/fullscreen-panel";

interface DashboardTileProps {
  readonly title: string;
  readonly icon?: ReactNode;
  readonly helpText?: string;
  readonly children: ReactNode;
  readonly className?: string;
  readonly actions?: ReactNode;
  readonly editMode?: boolean;
}

export function DashboardTile({
  title,
  icon,
  helpText,
  children,
  className,
  actions,
  editMode = false,
}: DashboardTileProps) {
  const [expanded, setExpanded] = useState(false);
  const headerActions = (
    <>
      {helpText ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground transition-colors hover:text-foreground"
                aria-label={`Help: ${title}`}
              >
                <HelpCircle className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs text-xs">
              {helpText}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : null}

      {actions}

      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="rounded-md p-1.5 transition-colors hover:bg-sidebar-accent"
        aria-label={`Expand ${title} fullscreen`}
      >
        <Expand className="size-3.5" />
      </button>
    </>
  );

  return (
    <>
      <div
        data-dashboard-tile=""
        data-tile-title={title}
        className={cn(
          "group flex h-full flex-col overflow-hidden rounded-lg border",
          panelSurfaceClassName,
          className,
        )}
      >
        <div className="flex shrink-0 items-center gap-2 border-b border-sidebar-border/70 px-3 py-2">
          {editMode ? (
            <span
              className="dashboard-tile-handle cursor-grab text-muted-foreground active:cursor-grabbing"
              aria-hidden="true"
            >
              <GripVertical className="size-4" />
            </span>
          ) : null}
          {icon ? <span className="text-muted-foreground">{icon}</span> : null}
          <span className="flex-1 truncate text-sm font-medium">{title}</span>
          <div className="ml-auto flex items-center gap-2 shrink-0">{headerActions}</div>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden px-3 py-2">{children}</div>
      </div>

      <FullscreenPanel
        open={expanded}
        onClose={() => setExpanded(false)}
        title={title}
        headerActions={actions}
      >
        {children}
      </FullscreenPanel>
    </>
  );
}
