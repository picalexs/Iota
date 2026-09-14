import { useEffect, useRef, useState } from "react";
import { deleteRun } from "@/api/runs";
import { getErrorMessage } from "@/lib/error-handler";
import type { RunSummaryResponse, UUID } from "@/types/run";
import { type RunRowAction } from "../components/runs-list-row";
import { truncateId } from "../components/runs-list-row-utils";
import {
  ROW_ACTION_LABELS,
  buildBulkActionErrorSummary,
  buildDeleteRunsErrorSummary,
  runStatusOverride,
  type BulkRunAction,
  type ConfirmableRunAction,
  type RunDeleteProgress,
  type RunSummaryOverride,
} from "./selection-actions";
import { performRunAction } from "./run-actions";

export interface RunsSelectionState {
  readonly replaceSelection: (ids: readonly UUID[]) => void;
}

export interface UseRunsListActionsOptions {
  readonly serverRuns: readonly RunSummaryResponse[];
  readonly invalidateRunsList?: () => Promise<unknown>;
  readonly refetchRuns?: () => Promise<unknown>;
}

export function useRunsListActions({
  serverRuns,
  invalidateRunsList,
  refetchRuns,
}: UseRunsListActionsOptions) {
  const [pendingBulkAction, setPendingBulkAction] = useState<BulkRunAction>(null);
  const [confirmingBulkAction, setConfirmingBulkActionState] =
    useState<ConfirmableRunAction | null>(null);
  const [deleteSelectionOpen, setDeleteSelectionOpenState] = useState(false);
  const [deleteProgress, setDeleteProgress] = useState<RunDeleteProgress | null>(null);
  const [bulkActionError, setBulkActionError] = useState<string | null>(null);
  const [pendingRowActions, setPendingRowActions] = useState<Partial<Record<UUID, RunRowAction>>>(
    {},
  );
  const pendingRowActionsRef = useRef(pendingRowActions);
  pendingRowActionsRef.current = pendingRowActions;
  const [pendingRowDeletes, setPendingRowDeletes] = useState<Partial<Record<UUID, true>>>({});
  const [runOverrides, setRunOverrides] = useState<Partial<Record<UUID, RunSummaryOverride>>>({});

  useEffect(() => {
    if (serverRuns.length === 0) {
      return;
    }

    setRunOverrides((current) => {
      let changed = false;
      const next = { ...current };

      for (const run of serverRuns) {
        if (pendingRowActionsRef.current[run.id] != null || next[run.id] == null) {
          continue;
        }

        delete next[run.id];
        changed = true;
      }

      return changed ? next : current;
    });
  }, [serverRuns]);

  const runsWithOverrides = serverRuns.map((run) => ({
    ...run,
    ...runOverrides[run.id],
  }));
  const rowActionInProgress =
    Object.keys(pendingRowActions).length > 0 || Object.keys(pendingRowDeletes).length > 0;

  async function refreshRunsList() {
    await Promise.allSettled([invalidateRunsList?.(), refetchRuns?.()]);
  }

  async function handleSelectedRunsAction(
    action: RunRowAction,
    targetRuns: RunSummaryResponse[],
    selectedRuns: RunSummaryResponse[],
    selection: RunsSelectionState,
  ) {
    if (targetRuns.length === 0) {
      return;
    }

    setPendingBulkAction(action);
    setBulkActionError(null);

    try {
      const results = await Promise.allSettled(
        targetRuns.map(async (run) => {
          const response = await performRunAction(action, run.id);
          return { run, response };
        }),
      );

      setRunOverrides((current) => {
        const next = { ...current };
        results.forEach((result) => {
          if (result.status === "fulfilled") {
            next[result.value.run.id] = runStatusOverride(
              result.value.run,
              action,
              result.value.response,
            );
          }
        });
        return next;
      });

      await refreshRunsList();

      const failedIds = results.flatMap((result, index) => {
        const targetRun = targetRuns[index];
        return result.status === "rejected" && targetRun ? [targetRun.id] : [];
      });
      const eligibleIds = new Set(targetRuns.map((run) => run.id));
      const skippedIds = selectedRuns
        .filter((run) => !eligibleIds.has(run.id))
        .map((run) => run.id);
      selection.replaceSelection([...skippedIds, ...failedIds]);

      const summary = buildBulkActionErrorSummary(action, results);
      if (summary) {
        setBulkActionError(summary);
      }
    } catch (actionError) {
      setBulkActionError(getErrorMessage(actionError, `Failed to ${action} selected runs.`));
    } finally {
      setPendingBulkAction(null);
      setConfirmingBulkActionState(null);
    }
  }

  async function deleteSelectedRuns(
    selectedRuns: RunSummaryResponse[],
    selection: RunsSelectionState,
  ) {
    if (selectedRuns.length === 0) {
      return;
    }

    setPendingBulkAction("delete");
    setDeleteProgress({ completed: 0, total: selectedRuns.length });
    setBulkActionError(null);

    try {
      const results: PromiseSettledResult<string>[] = [];

      for (const [index, run] of selectedRuns.entries()) {
        try {
          await deleteRun(run.id);
          results.push({ status: "fulfilled", value: run.id });
        } catch (error) {
          results.push({ status: "rejected", reason: error });
        } finally {
          setDeleteProgress({ completed: index + 1, total: selectedRuns.length });
        }
      }

      await refreshRunsList();

      const failedIds = results.flatMap((result, index) => {
        const selectedRun = selectedRuns[index];
        return result.status === "rejected" && selectedRun ? [selectedRun.id] : [];
      });
      selection.replaceSelection(failedIds);

      if (failedIds.length > 0) {
        setBulkActionError(buildDeleteRunsErrorSummary(results, failedIds));
        return;
      }

      setDeleteSelectionOpenState(false);
    } catch (actionError) {
      setBulkActionError(getErrorMessage(actionError, "Failed to delete selected runs."));
    } finally {
      setPendingBulkAction(null);
      setDeleteProgress(null);
    }
  }

  async function handleRunAction(run: RunSummaryResponse, action: RunRowAction) {
    setPendingRowActions((current) => ({ ...current, [run.id]: action }));
    setBulkActionError(null);

    try {
      const response = await performRunAction(action, run.id);
      setRunOverrides((current) => ({
        ...current,
        [run.id]: runStatusOverride(run, action, response),
      }));
      await refreshRunsList();
    } catch (actionError) {
      setBulkActionError(
        getErrorMessage(
          actionError,
          `Failed to ${ROW_ACTION_LABELS[action]} run ${truncateId(run.id)}.`,
        ),
      );
    } finally {
      setPendingRowActions((current) => {
        const next = { ...current };
        delete next[run.id];
        return next;
      });
    }
  }

  async function handleDeleteRun(run: RunSummaryResponse) {
    setPendingRowDeletes((current) => ({ ...current, [run.id]: true }));
    setBulkActionError(null);

    try {
      await deleteRun(run.id);
      await refreshRunsList();
    } catch (actionError) {
      setBulkActionError(
        getErrorMessage(actionError, `Failed to delete run ${truncateId(run.id)}.`),
      );
    } finally {
      setPendingRowDeletes((current) => {
        const next = { ...current };
        delete next[run.id];
        return next;
      });
    }
  }

  function setConfirmingBulkAction(action: ConfirmableRunAction | null) {
    setConfirmingBulkActionState(action);
    if (action === null) {
      setDeleteProgress(null);
    }
  }

  function setDeleteSelectionOpen(open: boolean) {
    setDeleteSelectionOpenState(open);
    if (!open) {
      setDeleteProgress(null);
    }
  }

  function openDeleteSelection() {
    setBulkActionError(null);
    setDeleteSelectionOpenState(true);
  }

  return {
    runsWithOverrides,
    pendingBulkAction,
    confirmingBulkAction,
    deleteSelectionOpen,
    deleteProgress,
    bulkActionError,
    pendingRowActions,
    pendingRowDeletes,
    rowActionInProgress,
    setBulkActionError,
    setConfirmingBulkAction,
    setDeleteSelectionOpen,
    openDeleteSelection,
    handleSelectedRunsAction,
    deleteSelectedRuns,
    handleRunAction,
    handleDeleteRun,
  };
}
