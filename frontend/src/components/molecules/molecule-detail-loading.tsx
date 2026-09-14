import { Skeleton } from "@/components/ui/skeleton";
import { SkeletonCardGrid } from "@/components/ui/loading-skeleton-blocks";

export function MoleculeDetailLoadingSkeleton() {
  return (
    <div
      className="flex flex-col gap-4 w-full overflow-x-hidden px-2 min-w-0"
      aria-busy="true"
      aria-label="Loading molecule details"
    >
      <div className="flex items-end justify-between gap-4 flex-wrap shrink-0">
        <div className="flex flex-col gap-1.5 min-w-0 flex-1">
          <Skeleton className="h-9 w-48" />
          <div className="flex items-center gap-2.5 flex-wrap">
            <Skeleton className="h-6 w-20" />
            <Skeleton className="h-6 w-24" />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-20" />
        </div>
      </div>

      <div className="space-y-4">
        <Skeleton className="h-80 w-full rounded-lg" />
        <SkeletonCardGrid cardCount={3} />
      </div>
    </div>
  );
}
