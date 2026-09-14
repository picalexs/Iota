import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ArtifactPanelTab {
  readonly id: string;
  readonly label: string;
  readonly content: ReactNode;
  readonly actions?: ReactNode;
  readonly disabled?: boolean;
}

interface ArtifactPanelProps {
  readonly tabs: ArtifactPanelTab[];
  readonly defaultTabId?: string;
  readonly emptyMessage?: string;
  readonly className?: string;
  readonly contentClassName?: string;
  readonly headerActions?: ReactNode;
  readonly tabsClassName?: string;
  readonly activeTabId?: string | null;
  readonly onActiveTabChange?: (tabId: string) => void;
}

export function ArtifactPanel({
  tabs,
  defaultTabId,
  emptyMessage = "No artifacts recorded",
  className,
  contentClassName,
  headerActions,
  tabsClassName,
  activeTabId,
  onActiveTabChange,
}: ArtifactPanelProps) {
  const availableTabs = useMemo(() => tabs.filter((tab) => !tab.disabled), [tabs]);
  const firstAvailableTab = availableTabs[0];
  const fallbackTabId = defaultTabId ?? firstAvailableTab?.id ?? null;
  const [internalActiveTabId, setInternalActiveTabId] = useState<string | null>(fallbackTabId);

  useEffect(() => {
    if (activeTabId !== undefined) {
      return;
    }
    if (availableTabs.some((tab) => tab.id === internalActiveTabId)) {
      return;
    }
    setInternalActiveTabId(fallbackTabId);
  }, [activeTabId, availableTabs, fallbackTabId, internalActiveTabId]);

  if (availableTabs.length === 0 || !firstAvailableTab) {
    return <ChartEmptyState message={emptyMessage} />;
  }

  const resolvedActiveTabId = activeTabId ?? internalActiveTabId ?? fallbackTabId;
  const activeTab =
    availableTabs.find((tab) => tab.id === resolvedActiveTabId) ?? firstAvailableTab;

  function handleTabChange(tabId: string) {
    if (activeTabId === undefined) {
      setInternalActiveTabId(tabId);
    }
    onActiveTabChange?.(tabId);
  }

  return (
    <div className={cn("flex h-full min-h-0 flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          className={cn(
            "flex flex-wrap items-center gap-1 rounded-md border border-border/60 bg-muted/20 p-1",
            tabsClassName,
          )}
        >
          {availableTabs.map((tab) => (
            <Button
              key={tab.id}
              type="button"
              variant={activeTab.id === tab.id ? "secondary" : "ghost"}
              size="sm"
              className="h-7 px-2.5 text-xs"
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        {headerActions || activeTab.actions ? (
          <div className="flex shrink-0 items-center gap-2">
            {headerActions}
            {activeTab.actions ? <div>{activeTab.actions}</div> : null}
          </div>
        ) : null}
      </div>

      <div className={cn("min-h-0 flex-1 overflow-hidden", contentClassName)}>
        {activeTab.content}
      </div>
    </div>
  );
}
