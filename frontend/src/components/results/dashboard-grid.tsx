import { type ReactNode } from "react";
import { GridLayout, verticalCompactor, useContainerWidth } from "react-grid-layout";
import type { LayoutItem } from "react-grid-layout";

interface DashboardGridProps {
  readonly layout: LayoutItem[];
  readonly layoutKey?: string;
  readonly onLayoutChange: (layout: LayoutItem[]) => void;
  readonly editMode: boolean;
  readonly children: ReactNode;
  readonly rowHeight?: number;
  readonly cols?: number;
}

export function DashboardGrid({
  layout,
  layoutKey,
  onLayoutChange,
  editMode,
  children,
  rowHeight = 80,
  cols = 12,
}: DashboardGridProps) {
  const { width, mounted, containerRef } = useContainerWidth({ measureBeforeMount: true });

  return (
    <div ref={containerRef} className="w-full" aria-busy={!mounted}>
      {mounted ? (
        <GridLayout
          key={layoutKey}
          width={width}
          layout={layout}
          gridConfig={{
            cols,
            rowHeight,
            margin: [8, 8] as const,
            containerPadding: [0, 0] as const,
          }}
          dragConfig={
            editMode
              ? { enabled: true, handle: ".dashboard-tile-handle", bounded: true, threshold: 3 }
              : { enabled: false, bounded: false, threshold: 3 }
          }
          resizeConfig={
            editMode
              ? { enabled: true, handles: ["se"] as const }
              : { enabled: false, handles: ["se"] as const }
          }
          compactor={verticalCompactor}
          onLayoutChange={(l) => {
            if (editMode) onLayoutChange([...l]);
          }}
          autoSize
        >
          {children}
        </GridLayout>
      ) : (
        <div className="grid grid-cols-2 gap-2">{children}</div>
      )}
    </div>
  );
}
