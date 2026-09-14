import type { ReactNode } from "react";
import { Expand, GripVertical } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

interface PanelCardProps {
  readonly title: string;
  readonly onExpand: () => void;
  readonly badge?: ReactNode;
  readonly headerRight?: ReactNode;
  readonly children: ReactNode;
  readonly editMode?: boolean;
}

export function PanelCard({
  title,
  onExpand,
  badge,
  headerRight,
  children,
  editMode = false,
}: PanelCardProps) {
  return (
    <Card className="h-full flex flex-col group">
      <CardHeader className="shrink-0 px-3 pt-2 pb-1">
        <div className="flex items-center gap-2 min-w-0">
          {editMode && (
            <GripVertical
              className="drag-handle size-4 text-muted-foreground cursor-grab active:cursor-grabbing shrink-0"
              aria-hidden="true"
            />
          )}
          <CardTitle className="text-sm truncate">{title}</CardTitle>
          {badge}
          {headerRight && (
            <div className="ml-auto flex items-center gap-2 shrink-0">{headerRight}</div>
          )}
          <button
            type="button"
            onClick={onExpand}
            className={`${headerRight ? "" : "ml-auto"} p-1.5 rounded-md hover:bg-accent opacity-0 group-hover:opacity-100 transition-opacity shrink-0`}
            aria-label={`Expand ${title} fullscreen`}
          >
            <Expand className="size-3.5" />
          </button>
        </div>
      </CardHeader>
      {children}
    </Card>
  );
}
