import { Card, CardContent, CardHeader } from "./card";
import { Skeleton } from "./skeleton";
import { cn } from "@/lib/utils";

const EMPTY_INDICES: readonly number[] = [];
const DEFAULT_DETAIL_LINE_WIDTHS = ["w-full", "w-3/4", "w-1/2", "w-2/3"] as const;

function keyedValues<T>(
  values: readonly T[],
  prefix: string,
): Array<{ id: string; value: T; index: number }> {
  return values.map((value, index) => ({ id: `${prefix}-${index}`, value, index }));
}

function skeletonIds(count: number, prefix: string): string[] {
  return Array.from({ length: count }, (_, index) => `${prefix}-${index}`);
}

type TableSkeletonRowProps = Readonly<{
  gridClassName: string;
  cellWidths: readonly string[];
  rightAlignedIndices?: readonly number[];
  centeredIndices?: readonly number[];
}>;

export function TableSkeletonRow({
  gridClassName,
  cellWidths,
  rightAlignedIndices = EMPTY_INDICES,
  centeredIndices = EMPTY_INDICES,
}: TableSkeletonRowProps) {
  return (
    <tr className={cn("grid gap-4 items-center border-b px-4 py-3 last:border-0", gridClassName)}>
      {keyedValues(cellWidths, "cell").map(({ id, value: width, index }) => (
        <td key={id} className={cn(centeredIndices.includes(index) && "flex justify-center")}>
          <Skeleton
            className={cn("h-4", width, rightAlignedIndices.includes(index) && "ml-auto")}
          />
        </td>
      ))}
    </tr>
  );
}

type DetailCardSkeletonProps = Readonly<{
  titleWidth?: string;
  lineWidths?: readonly string[];
}>;

export function DetailCardSkeleton({
  titleWidth = "w-24",
  lineWidths = DEFAULT_DETAIL_LINE_WIDTHS,
}: DetailCardSkeletonProps) {
  return (
    <Card>
      <CardHeader>
        <Skeleton className={cn("h-5", titleWidth)} />
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {keyedValues(lineWidths, "detail-line").map(({ id, value: width }) => (
          <Skeleton key={id} className={cn("h-4", width)} />
        ))}
      </CardContent>
    </Card>
  );
}

type SkeletonLinesProps = Readonly<{
  lineWidths: readonly string[];
  className?: string;
}>;

export function SkeletonLines({ lineWidths, className }: SkeletonLinesProps) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {keyedValues(lineWidths, "line").map(({ id, value: width }) => (
        <Skeleton key={id} className={cn("h-4", width)} />
      ))}
    </div>
  );
}

type SkeletonCardGridProps = Readonly<{
  cardCount: number;
  cardHeightClassName?: string;
  gridClassName?: string;
}>;

export function SkeletonCardGrid({
  cardCount,
  cardHeightClassName = "h-40",
  gridClassName = "grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3",
}: SkeletonCardGridProps) {
  return (
    <div className={gridClassName}>
      {skeletonIds(cardCount, "card").map((id) => (
        <Skeleton key={id} className={cardHeightClassName} />
      ))}
    </div>
  );
}
