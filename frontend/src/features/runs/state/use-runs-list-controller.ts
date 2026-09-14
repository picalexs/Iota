import { useEffect } from "react";
import { useSearch } from "@tanstack/react-router";
import { useBulkDeleteShortcut } from "@/components/bulk-actions/use-bulk-delete-shortcut";
import { useBulkSelection } from "@/components/bulk-actions/use-bulk-selection";
import { useAllMoleculeSummaries, useInvalidateRunsList, useListRunSummaries } from "@/hooks";
import { useRunsListFilter } from "./filters";
import { getRunSelectionEligibility } from "./selection-eligibility";
import { useRunsListActions } from "./use-runs-list-actions";
import { useCompactRunsLayout } from "../components/runs-table";

const RUNS_PAGE_SIZE = 50;

function useActiveRunsPolling(hasActiveRuns: boolean, refetchRuns: () => Promise<unknown>) {
  useEffect(() => {
    if (!hasActiveRuns) return;
    const intervalId = globalThis.setInterval(() => {
      void refetchRuns?.();
    }, 2000);
    return () => globalThis.clearInterval(intervalId);
  }, [hasActiveRuns, refetchRuns]);
}

function useRunsPageCorrection(
  runsData: { total: number } | undefined,
  page: number,
  totalPages: number,
  goToPage: (nextPage: number) => void,
) {
  useEffect(() => {
    if (!runsData || page <= totalPages) return;
    goToPage(totalPages);
  }, [goToPage, page, runsData, totalPages]);
}

export function useRunsListController() {
  const search = useSearch({ from: "/runs" });
  const usesCompactRunsLayout = useCompactRunsLayout();
  const page = Math.max(1, search.page ?? 1);
  const selectedStatuses = search.statuses ?? [];
  const selectedMoleculeIds = search.molecule_ids ?? [];
  const serverStatus = selectedStatuses.length === 1 ? selectedStatuses[0] : undefined;
  const serverMoleculeId = selectedMoleculeIds.length === 1 ? selectedMoleculeIds[0] : undefined;
  const runsQuery = useListRunSummaries({
    limit: RUNS_PAGE_SIZE,
    offset: (page - 1) * RUNS_PAGE_SIZE,
    status: serverStatus,
    molecule_id: serverMoleculeId,
    backend_target: search.backend_target,
    chemical_accurate: search.chemical_accurate,
  });
  const moleculesQuery = useAllMoleculeSummaries();
  const invalidateRunsList = useInvalidateRunsList();
  const {
    data: runsData,
    error: runsError,
    isLoading: isRunsLoading,
    refetch: refetchRuns,
  } = runsQuery;
  const totalRuns = runsData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRuns / RUNS_PAGE_SIZE));
  const actionState = useRunsListActions({
    serverRuns: runsData?.items ?? [],
    invalidateRunsList,
    refetchRuns,
  });
  const filterState = useRunsListFilter({
    rawRuns: actionState.runsWithOverrides,
    moleculeItems: moleculesQuery.data ?? [],
  });
  const bulkSelection = useBulkSelection(filterState.runs.map((run) => run.id));
  const selectionEligibility = getRunSelectionEligibility(
    filterState.runs,
    bulkSelection.selectedIdSet,
  );
  const isMoleculeLookupLoading = moleculesQuery.isLoading && !moleculesQuery.data;
  const { hasActiveRuns, goToPage } = filterState;

  useBulkDeleteShortcut({
    enabled:
      bulkSelection.isEditing &&
      bulkSelection.selectedCount > 0 &&
      !actionState.deleteSelectionOpen &&
      actionState.pendingBulkAction === null &&
      !actionState.rowActionInProgress,
    onDelete: actionState.openDeleteSelection,
  });

  useActiveRunsPolling(hasActiveRuns, refetchRuns);
  useRunsPageCorrection(runsData, page, totalPages, goToPage);

  return {
    usesCompactRunsLayout,
    page,
    totalRuns,
    totalPages,
    isRunsLoading,
    isMoleculeLookupLoading,
    error: runsError,
    moleculeLookupError: moleculesQuery.error,
    molecules: moleculesQuery.data ?? [],
    refetchRuns,
    filterState,
    actionState,
    bulkSelection,
    selectionEligibility,
  };
}
