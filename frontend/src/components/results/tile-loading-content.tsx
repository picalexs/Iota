import { Skeleton } from "@/components/ui/skeleton";

function SummaryMetricSkeleton() {
  return (
    <div className="rounded-xl border border-border/70 bg-muted/25 px-4 py-3">
      <Skeleton className="h-3 w-16" />
      <Skeleton className="mt-2 h-5 w-24 max-w-full" />
      <Skeleton className="mt-2 h-3 w-20 max-w-full" />
    </div>
  );
}

function TimelineRowSkeleton() {
  return (
    <div className="flex gap-3 px-4 py-3">
      <Skeleton className="mt-0.5 size-4 rounded-full" />
      <div className="flex-1 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-16" />
        </div>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    </div>
  );
}

function BenchmarkBarSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border border-border/60 bg-muted/15 p-3">
      <div className="flex items-center justify-between gap-2">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="h-5 w-full rounded-full" />
    </div>
  );
}

const SUMMARY_METRIC_SKELETONS = Array.from({ length: 8 }, (_, index) => (
  <SummaryMetricSkeleton key={`summary-metric-${index}`} />
));

const TIMELINE_ROW_SKELETONS = Array.from({ length: 6 }, (_, index) => (
  <TimelineRowSkeleton key={`timeline-row-${index}`} />
));

const BENCHMARK_BAR_SKELETONS = Array.from({ length: 3 }, (_, index) => (
  <BenchmarkBarSkeleton key={`benchmark-bar-${index}`} />
));

export function SummaryTileLoadingContent() {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="grid gap-3 border-b border-border/60 pb-2.5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-8 w-52 max-w-full" />
        </div>
        <div className="flex flex-wrap items-center justify-start gap-x-4 gap-y-1 lg:justify-end">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>

      <div className="rounded-md border border-border/60 bg-muted/20 px-3 py-2">
        <div className="grid gap-3 md:grid-cols-2 md:items-center">
          <div className="flex flex-col items-center justify-center gap-2">
            <Skeleton className="h-8 w-32 rounded-full" />
            <Skeleton className="h-4 w-36" />
          </div>
          <div className="flex flex-col items-center justify-center gap-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-7 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      </div>

      <div className="grid auto-rows-fr gap-x-5 gap-y-2.5 sm:grid-cols-3">
        {SUMMARY_METRIC_SKELETONS}
      </div>
    </div>
  );
}

export function ConvergenceTileLoadingContent() {
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Skeleton className="h-8 w-36 rounded-lg" />
        <Skeleton className="h-8 w-40 rounded-lg" />
        <Skeleton className="h-8 w-28 rounded-lg" />
      </div>
      <Skeleton className="min-h-[18rem] w-full flex-1 rounded-xl" />
      <div className="grid gap-2 sm:grid-cols-3">
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
      </div>
    </div>
  );
}

export function TimelineTileLoadingContent() {
  return (
    <div className="-mx-3 -my-2 flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Skeleton className="h-5 w-12 rounded-full" />
        <div className="ml-auto flex items-center gap-2">
          <Skeleton className="h-5 w-24 rounded-full" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-8 rounded-full" />
        </div>
      </div>
      <div className="flex flex-1 flex-col divide-y">{TIMELINE_ROW_SKELETONS}</div>
    </div>
  );
}

export function BenchmarkTileLoadingContent() {
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="space-y-3">{BENCHMARK_BAR_SKELETONS}</div>
      <div className="mt-auto space-y-2">
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  );
}
