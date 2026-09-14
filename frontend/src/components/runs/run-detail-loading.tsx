import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";

type TileFrameSkeletonProps = Readonly<{
  titleWidth: string;
  body: ReactNode;
  className?: string;
}>;

function TileFrameSkeleton({ titleWidth, body, className = "" }: TileFrameSkeletonProps) {
  return (
    <div
      className={`flex h-full min-h-0 flex-col overflow-hidden rounded-lg border bg-card ${className}`.trim()}
    >
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Skeleton className="size-4 rounded-sm" />
        <Skeleton className={`h-4 ${titleWidth}`} />
        <div className="ml-auto flex items-center gap-2">
          <Skeleton className="size-4 rounded-sm" />
          <Skeleton className="size-7 rounded-md" />
        </div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col px-3 py-2">{body}</div>
    </div>
  );
}

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

function SecondaryPanelMetricSkeleton() {
  return (
    <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
      <Skeleton className="h-3 w-14" />
      <Skeleton className="mt-2 h-4 w-20" />
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

const SECONDARY_PANEL_METRIC_SKELETONS = Array.from({ length: 3 }, (_, index) => (
  <SecondaryPanelMetricSkeleton key={`secondary-panel-metric-${index}`} />
));

function SummaryTileSkeleton() {
  return (
    <TileFrameSkeleton
      titleWidth="w-24"
      className="min-h-[28rem]"
      body={
        <div className="flex h-full flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/60 pb-4">
            <div className="min-w-0 flex-1 space-y-3">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-9 w-52 max-w-full" />
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Skeleton className="h-7 w-16 rounded-full" />
              <Skeleton className="h-7 w-24 rounded-full" />
              <Skeleton className="h-7 w-20 rounded-full" />
            </div>
          </div>

          <div className="rounded-xl border border-amber-200/60 bg-amber-50/50 px-4 py-4 dark:border-amber-400/15 dark:bg-amber-500/5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-3">
                <Skeleton className="h-8 w-32 rounded-full" />
                <Skeleton className="h-6 w-16" />
              </div>
              <div className="space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-[4.5rem]" />
              </div>
            </div>
          </div>

          <div className="grid h-full gap-3 sm:grid-cols-3">{SUMMARY_METRIC_SKELETONS}</div>
        </div>
      }
    />
  );
}

function ConvergenceTileSkeleton() {
  return (
    <TileFrameSkeleton
      titleWidth="w-28"
      className="min-h-[28rem]"
      body={
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
      }
    />
  );
}

function TimelineTileSkeleton() {
  return (
    <TileFrameSkeleton
      titleWidth="w-24"
      className="min-h-[32rem]"
      body={
        <div className="flex h-full flex-col">
          <div className="-mx-3 flex items-center gap-2 border-b px-3 py-2">
            <Skeleton className="h-5 w-12 rounded-full" />
            <div className="ml-auto flex items-center gap-2">
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-5 w-8 rounded-full" />
            </div>
          </div>
          <div className="-mx-3 flex flex-1 flex-col divide-y">{TIMELINE_ROW_SKELETONS}</div>
        </div>
      }
    />
  );
}

function BenchmarkTileSkeleton() {
  return (
    <TileFrameSkeleton
      titleWidth="w-36"
      className="min-h-[23rem]"
      body={
        <div className="flex h-full flex-col gap-3">
          <div className="space-y-3">{BENCHMARK_BAR_SKELETONS}</div>
          <div className="mt-auto space-y-2">
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      }
    />
  );
}

function SecondaryPanelSkeleton({ titleWidth }: Readonly<{ titleWidth: string }>) {
  return (
    <TileFrameSkeleton
      titleWidth={titleWidth}
      className="min-h-[26rem]"
      body={
        <div className="flex h-full flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">{SECONDARY_PANEL_METRIC_SKELETONS}</div>
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="min-h-[12rem] w-full flex-1 rounded-xl" />
        </div>
      }
    />
  );
}

export function RunDetailLoadingSkeleton() {
  return (
    <div className="flex w-full flex-col gap-6" aria-busy="true" aria-label="Loading run details">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <Skeleton className="h-6 w-28 rounded-full" />
          <Skeleton className="h-4 w-10" />
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Skeleton className="h-10 w-40 rounded-lg" />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Skeleton className="h-10 w-28 rounded-lg" />
        <Skeleton className="h-10 w-36 rounded-lg" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="xl:col-span-6">
          <SummaryTileSkeleton />
        </div>
        <div className="xl:col-span-6">
          <ConvergenceTileSkeleton />
        </div>

        <div className="xl:col-span-6">
          <TimelineTileSkeleton />
        </div>
        <div className="xl:col-span-6">
          <BenchmarkTileSkeleton />
        </div>

        <div className="xl:col-span-6">
          <SecondaryPanelSkeleton titleWidth="w-28" />
        </div>
        <div className="xl:col-span-6">
          <SecondaryPanelSkeleton titleWidth="w-32" />
        </div>
      </div>
    </div>
  );
}
