import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { createBenchmarkRun, deleteBenchmarkRun, listBenchmarkRuns } from "@/api/benchmarks";
import { useBulkDeleteShortcut } from "@/components/bulk-actions/use-bulk-delete-shortcut";
import { useBulkSelection } from "@/components/bulk-actions/use-bulk-selection";
import {
  invalidateBenchmarkRunQueries,
  invalidateRunsQueries,
  useListBenchmarkRuns,
} from "@/hooks/use-query-hooks";
import { BENCHMARK_ALGORITHMS, DEFAULT_CHEMICAL_ACCURACY_HA } from "@/lib/benchmark-presets";
import {
  type BenchmarkBackendFilter,
  type BenchmarkStatusFilter,
} from "./benchmark-history-filters";
import {
  buildBenchmarkActionSummary,
  buildDeleteBenchmarksSummary,
  getSkippedSelectedBenchmarkIds,
  removeSavedBenchmarksFromCache,
  runDeleteSelectedBenchmarksBatch,
  runSelectedBenchmarkActionBatch,
  updateSavedBenchmarksInCache,
  type BenchmarkDeleteProgress,
  type BenchmarkExecutableAction,
} from "@/features/benchmarks/state/history-actions";
import {
  deriveBenchmarkHistorySelection,
  filterAndSortSavedBenchmarkRuns,
  type BenchmarkSortField,
  type BenchmarkSortOrder,
} from "@/features/benchmarks/state/history";
import {
  buildSavedBenchmarkRunName,
  SAVED_BENCHMARK_LIST_LIMIT,
  type SavedBenchmarkRun,
} from "./benchmark-storage";
import {
  type BenchmarkBulkAction,
  type BenchmarkConfirmableAction,
} from "./benchmark-history-action-dialogs";

const BENCHMARK_LIST_PARAMS = { limit: SAVED_BENCHMARK_LIST_LIMIT, offset: 0 } as const;
const EMPTY_SAVED_BENCHMARK_RUNS: SavedBenchmarkRun[] = [];

type PendingRowAction = {
  readonly runId: string;
  readonly action: BenchmarkExecutableAction;
};

export function useBenchmarkHistoryController() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<BenchmarkSortField>("updated");
  const [sortOrder, setSortOrder] = useState<BenchmarkSortOrder>("desc");
  const [statusFilter, setStatusFilter] = useState<BenchmarkStatusFilter>("all");
  const [backendFilter, setBackendFilter] = useState<BenchmarkBackendFilter>("all");
  const [deleteSelectionOpen, setDeleteSelectionOpen] = useState(false);
  const [deleteAssociatedRuns, setDeleteAssociatedRuns] = useState(false);
  const [deletingSelection, setDeletingSelection] = useState(false);
  const [deleteProgress, setDeleteProgress] = useState<BenchmarkDeleteProgress | null>(null);
  const [bulkActionError, setBulkActionError] = useState<string | null>(null);
  const [pendingBulkAction, setPendingBulkAction] = useState<BenchmarkBulkAction>(null);
  const [pendingRowAction, setPendingRowAction] = useState<PendingRowAction | null>(null);
  const [confirmingBulkAction, setConfirmingBulkAction] = useState<Extract<
    BenchmarkBulkAction,
    "pause" | "restart" | "cancel"
  > | null>(null);
  const [confirmingRowAction, setConfirmingRowAction] = useState<{
    readonly action: Extract<BenchmarkBulkAction, "pause" | "restart" | "cancel">;
    readonly run: SavedBenchmarkRun;
  } | null>(null);
  const {
    data,
    isLoading: loading,
    error,
    refetch,
  } = useListBenchmarkRuns(listBenchmarkRuns, BENCHMARK_LIST_PARAMS);

  const savedBenchmarkRuns = data?.items ?? EMPTY_SAVED_BENCHMARK_RUNS;
  const filteredAndSortedRuns = useMemo(
    () =>
      filterAndSortSavedBenchmarkRuns(
        savedBenchmarkRuns,
        statusFilter,
        backendFilter,
        sortField,
        sortOrder,
      ),
    [backendFilter, savedBenchmarkRuns, sortField, sortOrder, statusFilter],
  );

  const bulkSelection = useBulkSelection(filteredAndSortedRuns.map((run) => run.id));
  const {
    selectedRuns,
    associatedRunCount,
    pausableSelectedRuns,
    resumableSelectedRuns,
    restartableSelectedRuns,
    cancellableSelectedRuns,
  } = useMemo(
    () => deriveBenchmarkHistorySelection(filteredAndSortedRuns, bulkSelection.selectedIdSet),
    [bulkSelection.selectedIdSet, filteredAndSortedRuns],
  );
  const hasActiveFilters = statusFilter !== "all" || backendFilter !== "all";
  const actionPending =
    pendingBulkAction !== null || pendingRowAction !== null || deletingSelection;

  useBulkDeleteShortcut({
    enabled:
      bulkSelection.isEditing &&
      bulkSelection.selectedCount > 0 &&
      !deleteSelectionOpen &&
      pendingBulkAction === null &&
      !deletingSelection,
    onDelete: () => {
      setBulkActionError(null);
      setDeleteSelectionOpen(true);
    },
  });

  function updateSort(field: BenchmarkSortField) {
    if (sortField === field) {
      setSortOrder((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortField(field);
    setSortOrder(field === "updated" ? "desc" : "asc");
  }

  function clearFilters() {
    setStatusFilter("all");
    setBackendFilter("all");
  }

  async function createNewBenchmark() {
    setCreating(true);
    setCreateError(null);
    try {
      const createdAt = new Date().toISOString();
      const draft = await createBenchmarkRun({
        name: buildSavedBenchmarkRunName({
          createdAt,
          moleculeCount: 0,
          algorithmCount: BENCHMARK_ALGORITHMS.length,
          basis: "sto-3g",
        }),
        selectedMoleculeKeys: [],
        selectedAlgorithms: BENCHMARK_ALGORITHMS.map((algorithm) => algorithm.value),
        selectedBasis: "sto-3g",
        selectedBackendMode: "statevector",
        selectedBackendName: null,
        chemicalAccuracyHa: DEFAULT_CHEMICAL_ACCURACY_HA,
        customMolecules: [],
        entries: [],
      });
      await invalidateBenchmarkRunQueries(queryClient);
      void navigate({ to: "/benchmarks/$benchmarkId", params: { benchmarkId: draft.id } });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create benchmark");
    } finally {
      setCreating(false);
    }
  }

  async function deleteSavedBenchmark(
    savedRunId: string,
    options: { deleteAssociatedRuns: boolean },
  ) {
    await deleteBenchmarkRun(savedRunId, options);
    removeSavedBenchmarksFromCache(queryClient, [savedRunId]);
    await invalidateBenchmarkRunQueries(queryClient);
    if (options.deleteAssociatedRuns) {
      await invalidateRunsQueries(queryClient);
    }
  }

  async function deleteSelectedBenchmarks() {
    if (selectedRuns.length === 0) {
      return;
    }

    setDeletingSelection(true);
    setDeleteProgress({ completed: 0, total: selectedRuns.length });
    setBulkActionError(null);

    try {
      const { results, failedIds, deletedIds } = await runDeleteSelectedBenchmarksBatch(
        selectedRuns,
        deleteAssociatedRuns,
        setDeleteProgress,
      );

      if (deletedIds.length > 0) {
        removeSavedBenchmarksFromCache(queryClient, deletedIds);
      }

      await invalidateBenchmarkRunQueries(queryClient);
      if (deleteAssociatedRuns) {
        await invalidateRunsQueries(queryClient);
      }

      bulkSelection.replaceSelection(failedIds);

      if (failedIds.length > 0) {
        setBulkActionError(buildDeleteBenchmarksSummary(results, failedIds));
        return;
      }

      setDeleteAssociatedRuns(false);
      setDeleteSelectionOpen(false);
    } finally {
      setDeletingSelection(false);
      setDeleteProgress(null);
    }
  }

  async function handleSelectedBenchmarksAction(
    action: BenchmarkExecutableAction,
    eligibleRuns: readonly SavedBenchmarkRun[],
  ) {
    if (eligibleRuns.length === 0) {
      return;
    }

    setPendingBulkAction(action);
    setBulkActionError(null);

    try {
      const { results, updatedRuns, failedIds, partialIds } = await runSelectedBenchmarkActionBatch(
        action,
        eligibleRuns,
      );
      const skippedIds = getSkippedSelectedBenchmarkIds(selectedRuns, eligibleRuns);

      if (updatedRuns.length > 0) {
        updateSavedBenchmarksInCache(queryClient, updatedRuns);
      }

      await invalidateBenchmarkRunQueries(queryClient);
      await invalidateRunsQueries(queryClient);

      bulkSelection.replaceSelection([...new Set([...skippedIds, ...failedIds, ...partialIds])]);
      const firstError = results.find((result) => result.status === "rejected");
      setBulkActionError(
        buildBenchmarkActionSummary(
          action,
          eligibleRuns.length,
          failedIds.length,
          partialIds.length,
          firstError?.status === "rejected" ? firstError.reason : undefined,
        ),
      );
    } finally {
      setPendingBulkAction(null);
      setConfirmingBulkAction(null);
    }
  }

  async function handleRowBenchmarkAction(
    run: SavedBenchmarkRun,
    action: BenchmarkExecutableAction,
  ) {
    setPendingRowAction({ runId: run.id, action });
    setBulkActionError(null);

    try {
      const { results, updatedRuns, failedIds, partialIds } = await runSelectedBenchmarkActionBatch(
        action,
        [run],
      );

      if (updatedRuns.length > 0) {
        updateSavedBenchmarksInCache(queryClient, updatedRuns);
      }

      await invalidateBenchmarkRunQueries(queryClient);
      await invalidateRunsQueries(queryClient);

      const firstError = results.find((result) => result.status === "rejected");
      setBulkActionError(
        buildBenchmarkActionSummary(
          action,
          1,
          failedIds.length,
          partialIds.length,
          firstError?.status === "rejected" ? firstError.reason : undefined,
        ),
      );
    } finally {
      setPendingRowAction(null);
      setConfirmingRowAction(null);
    }
  }

  function confirmBulkAction(action: BenchmarkConfirmableAction) {
    let eligibleRuns = cancellableSelectedRuns;
    if (action === "pause") eligibleRuns = pausableSelectedRuns;
    if (action === "restart") eligibleRuns = restartableSelectedRuns;
    void handleSelectedBenchmarksAction(action, eligibleRuns);
  }

  function requestRowAction(run: SavedBenchmarkRun, action: BenchmarkExecutableAction) {
    setBulkActionError(null);
    if (action === "resume") {
      void handleRowBenchmarkAction(run, action);
      return;
    }
    setConfirmingRowAction({ run, action });
  }

  function handleDeleteSelectionOpenChange(open: boolean) {
    setDeleteSelectionOpen(open);
    if (!open) {
      setDeleteProgress(null);
      setDeleteAssociatedRuns(false);
    }
  }

  return {
    savedBenchmarkRuns,
    filteredAndSortedRuns,
    loading,
    error,
    refetch,
    sortField,
    sortOrder,
    statusFilter,
    backendFilter,
    hasActiveFilters,
    creating,
    createError,
    actionPending,
    isEditing: bulkSelection.isEditing,
    selectedRunIds: bulkSelection.selectedIdSet,
    selectedCount: bulkSelection.selectedCount,
    allVisibleSelected: bulkSelection.allVisibleSelected,
    someVisibleSelected: bulkSelection.someVisibleSelected,
    bulkActionError,
    pausableCount: pausableSelectedRuns.length,
    resumableCount: resumableSelectedRuns.length,
    restartableCount: restartableSelectedRuns.length,
    cancellableCount: cancellableSelectedRuns.length,
    confirmingBulkAction,
    confirmingRowAction,
    pendingBulkAction,
    pendingRowAction,
    selectedRuns,
    associatedRunCount,
    deleteSelectionOpen,
    deleteAssociatedRuns,
    deleteProgress,
    deletingSelection,
    clearFilters,
    updateSort,
    setStatusFilter,
    setBackendFilter,
    createNewBenchmark,
    toggleEditing: bulkSelection.toggleEditing,
    loadBenchmark: (benchmarkId: string) => {
      void navigate({ to: "/benchmarks/$benchmarkId", params: { benchmarkId } });
    },
    deleteSavedBenchmark,
    requestRowAction,
    toggleBenchmarkSelection: (benchmarkId: string) => {
      setBulkActionError(null);
      bulkSelection.toggleSelected(benchmarkId);
    },
    toggleSelectAllVisible: (selected: boolean) => {
      setBulkActionError(null);
      bulkSelection.setAllVisibleSelected(selected);
    },
    clearSelection: () => {
      setBulkActionError(null);
      bulkSelection.clearSelection();
    },
    confirmPauseSelection: () => setConfirmingBulkAction("pause"),
    resumeSelection: () => handleSelectedBenchmarksAction("resume", resumableSelectedRuns),
    confirmRestartSelection: () => setConfirmingBulkAction("restart"),
    confirmCancelSelection: () => setConfirmingBulkAction("cancel"),
    openDeleteSelection: () => setDeleteSelectionOpen(true),
    closeActionDialogs: () => {
      setConfirmingBulkAction(null);
      setConfirmingRowAction(null);
    },
    confirmBulkAction,
    confirmRowAction: (run: SavedBenchmarkRun, action: BenchmarkConfirmableAction) =>
      void handleRowBenchmarkAction(run, action),
    handleDeleteSelectionOpenChange,
    setDeleteAssociatedRuns,
    deleteSelectedBenchmarks,
  };
}
