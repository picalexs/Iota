export interface LegendItem {
  readonly label: string;
  readonly color: string;
  readonly dashed?: boolean;
}

interface ChartLegendProps {
  readonly items: LegendItem[];
}

export function ChartLegend({ items }: ChartLegendProps) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <svg width="16" height="2" aria-hidden="true">
            <line
              x1="0"
              y1="1"
              x2="16"
              y2="1"
              stroke={item.color}
              strokeWidth="2"
              strokeDasharray={item.dashed ? "4 2" : undefined}
            />
          </svg>
          {item.label}
        </span>
      ))}
    </div>
  );
}
