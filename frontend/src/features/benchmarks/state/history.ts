import type {
  BenchmarkRunHistoryStatus,
  SavedBenchmarkRun,
  SavedBenchmarkRunSummary,
} from "@/types/benchmark";
import {
  isCancellableBenchmarkEntry,
  isPausedBenchmarkEntry,
  isPausableBenchmarkEntry,
} from "@/features/benchmarks/state/selectors";
import { getAssociatedBenchmarkRunIds } from "@/pages/benchmark/benchmark-utils";

export type { BenchmarkRunHistoryStatus };
export type BenchmarkHistoryRun = SavedBenchmarkRun | SavedBenchmarkRunSummary;

export type BenchmarkSortField = "name" | "rows" | "backend" | "updated" | "status";
export type BenchmarkSortOrder = "asc" | "desc";

export const BENCHMARK_HISTORY_BACKEND_LABELS = {
  statevector: "Statevector",
  aer_simulator: "Aer",
  aer_simulator_backend_noise: "Aer noise",
  ibm_runtime: "IBM",
} as const;

export const BENCHMARK_HISTORY_STATUS_LABELS: Record<BenchmarkRunHistoryStatus, string> = {
  draft: "Draft",
  running: "Running",
  paused: "Paused",
  finished: "Completed",
  partial: "Partial",
  failed: "Failed",
  cancelled: "Cancelled",
  planned: "Planned",
  excluded: "Excluded",
};

export function formatSavedBenchmarkDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString();
}

export function summarizeSavedBenchmarkRows(run: BenchmarkHistoryRun) {
  if ("rowCount" in run) {
    return {
      total: run.rowCount,
      done: run.completedCount,
      active: run.activeCount,
      paused: run.pausedCount,
      cancelled: run.cancelledCount,
      failed: run.failedCount,
      planned: run.plannedCount,
      excluded: run.excludedCount,
    };
  }

  const total = run.entries.length;
  const done = run.entries.filter((entry) => entry.status === "completed").length;
  const active = run.entries.filter((entry) =>
    ["queued", "running", "submitting", "acquiring_molecule", "pausing"].includes(entry.status),
  ).length;
  const paused = run.entries.filter((entry) => entry.status === "paused").length;
  const cancelled = run.entries.filter((entry) => entry.status === "cancelled").length;
  const failed = run.entries.filter((entry) => entry.status === "failed").length;
  const planned = run.entries.filter((entry) => entry.status === "planned").length;
  const excluded = run.entries.filter((entry) => entry.status === "excluded").length;

  return { total, done, active, paused, cancelled, failed, planned, excluded };
}

export function getSavedBenchmarkStatus(run: BenchmarkHistoryRun): BenchmarkRunHistoryStatus {
  if ("rowCount" in run) return run.status;

  const summary = summarizeSavedBenchmarkRows(run);
  if (summary.active > 0) {
    return "running";
  }
  if (summary.paused > 0) {
    return "paused";
  }
  const terminalKinds = [summary.done > 0, summary.failed > 0, summary.cancelled > 0].filter(
    Boolean,
  ).length;
  if (terminalKinds > 1) {
    return "partial";
  }
  if (summary.total > 0 && summary.done > 0) {
    return "finished";
  }
  if (summary.failed > 0) {
    return "failed";
  }
  if (summary.cancelled > 0) {
    return "cancelled";
  }
  if (summary.planned > 0) {
    return "planned";
  }
  if (summary.excluded > 0) {
    return "excluded";
  }
  return "draft";
}

export function canPauseSavedBenchmark(run: BenchmarkHistoryRun): boolean {
  if ("rowCount" in run) return run.activeCount > 0;
  return run.entries.some(isPausableBenchmarkEntry);
}

export function canResumeSavedBenchmark(run: BenchmarkHistoryRun): boolean {
  if ("rowCount" in run) return run.pausedCount > 0;
  return run.entries.some(isPausedBenchmarkEntry);
}

export function canRestartSavedBenchmark(run: BenchmarkHistoryRun): boolean {
  return canResumeSavedBenchmark(run);
}

export function canCancelSavedBenchmark(run: BenchmarkHistoryRun): boolean {
  if ("rowCount" in run) return run.activeCount > 0 || run.pausedCount > 0;
  return run.entries.some(isCancellableBenchmarkEntry);
}

export type BenchmarkHistorySelection = {
  readonly selectedRuns: BenchmarkHistoryRun[];
  readonly pausableSelectedRuns: BenchmarkHistoryRun[];
  readonly resumableSelectedRuns: BenchmarkHistoryRun[];
  readonly restartableSelectedRuns: BenchmarkHistoryRun[];
  readonly cancellableSelectedRuns: BenchmarkHistoryRun[];
  readonly associatedRunCount: number;
};

export function deriveBenchmarkHistorySelection(
  runs: readonly BenchmarkHistoryRun[],
  selectedIds: ReadonlySet<string>,
): BenchmarkHistorySelection {
  const selectedRuns = runs.filter((run) => selectedIds.has(run.id));

  return {
    selectedRuns,
    pausableSelectedRuns: selectedRuns.filter(canPauseSavedBenchmark),
    resumableSelectedRuns: selectedRuns.filter(canResumeSavedBenchmark),
    restartableSelectedRuns: selectedRuns.filter(canRestartSavedBenchmark),
    cancellableSelectedRuns: selectedRuns.filter(canCancelSavedBenchmark),
    associatedRunCount: new Set(
      selectedRuns.flatMap((run) =>
        "rowCount" in run ? [] : getAssociatedBenchmarkRunIds(run.entries),
      ),
    ).size,
  };
}

export function filterAndSortSavedBenchmarkRuns(
  runs: readonly BenchmarkHistoryRun[],
  statusFilter: BenchmarkRunHistoryStatus | "all",
  backendFilter: keyof typeof BENCHMARK_HISTORY_BACKEND_LABELS | "all",
  sortField: BenchmarkSortField,
  sortOrder: BenchmarkSortOrder,
): BenchmarkHistoryRun[] {
  const filteredRuns = runs.filter((run) => {
    if (statusFilter !== "all" && getSavedBenchmarkStatus(run) !== statusFilter) {
      return false;
    }
    if (backendFilter !== "all" && run.selectedBackendMode !== backendFilter) {
      return false;
    }
    return true;
  });

  return sortSavedBenchmarkRuns(filteredRuns, sortField, sortOrder);
}

const STATUS_SORT_RANK: Record<BenchmarkRunHistoryStatus, number> = {
  running: 0,
  paused: 1,
  finished: 2,
  partial: 3,
  failed: 4,
  cancelled: 5,
  planned: 6,
  excluded: 7,
  draft: 8,
};

export function sortSavedBenchmarkRuns(
  runs: readonly BenchmarkHistoryRun[],
  sortField: BenchmarkSortField,
  sortOrder: BenchmarkSortOrder,
): BenchmarkHistoryRun[] {
  const factor = sortOrder === "asc" ? 1 : -1;

  return [...runs].sort((left, right) => {
    let comparison = 0;

    switch (sortField) {
      case "name":
        comparison = left.name.localeCompare(right.name, undefined, { sensitivity: "base" });
        break;
      case "rows":
        comparison =
          ("rowCount" in left ? left.rowCount : left.entries.length) -
          ("rowCount" in right ? right.rowCount : right.entries.length);
        break;
      case "backend":
        comparison = (
          BENCHMARK_HISTORY_BACKEND_LABELS[left.selectedBackendMode] ?? left.selectedBackendMode
        ).localeCompare(
          BENCHMARK_HISTORY_BACKEND_LABELS[right.selectedBackendMode] ?? right.selectedBackendMode,
          undefined,
          { sensitivity: "base" },
        );
        break;
      case "updated":
        comparison = new Date(left.updatedAt).getTime() - new Date(right.updatedAt).getTime();
        break;
      case "status":
        comparison =
          STATUS_SORT_RANK[getSavedBenchmarkStatus(left)] -
          STATUS_SORT_RANK[getSavedBenchmarkStatus(right)];
        break;
    }

    if (comparison !== 0) {
      return comparison * factor;
    }

    return right.updatedAt.localeCompare(left.updatedAt) || left.name.localeCompare(right.name);
  });
}
