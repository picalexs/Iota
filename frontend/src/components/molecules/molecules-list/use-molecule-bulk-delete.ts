import { useState } from "react";

import type { MoleculeSummaryResponse } from "@/types/run";
import { deleteSelectedMolecules, type MoleculeDeleteProgress } from "./molecule-bulk-delete";

interface UseMoleculeBulkDeleteOptions {
  selectedMolecules: readonly MoleculeSummaryResponse[];
  deleteAssociatedRuns: boolean;
  invalidateMoleculesList: () => Promise<unknown>;
  replaceSelection: (ids: string[]) => void;
  onDeleteSuccess: () => void;
}

export function useMoleculeBulkDelete({
  selectedMolecules,
  deleteAssociatedRuns,
  invalidateMoleculesList,
  replaceSelection,
  onDeleteSuccess,
}: UseMoleculeBulkDeleteOptions) {
  const [deleteInProgress, setDeleteInProgress] = useState(false);
  const [deleteProgress, setDeleteProgress] = useState<MoleculeDeleteProgress | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function clearActionError() {
    setActionError(null);
  }

  function clearDeleteProgress() {
    setDeleteProgress(null);
  }

  async function deleteSelected() {
    if (selectedMolecules.length === 0) {
      return;
    }

    setDeleteInProgress(true);
    setDeleteProgress({ completed: 0, total: selectedMolecules.length });
    clearActionError();

    try {
      const result = await deleteSelectedMolecules(selectedMolecules, {
        deleteAssociatedRuns,
        onProgress: setDeleteProgress,
      });

      await invalidateMoleculesList();
      replaceSelection(result.failedIds);

      if (result.summary !== null) {
        setActionError(result.summary);
        return;
      }

      onDeleteSuccess();
    } finally {
      setDeleteInProgress(false);
      setDeleteProgress(null);
    }
  }

  return {
    actionError,
    clearActionError,
    clearDeleteProgress,
    deleteInProgress,
    deleteProgress,
    deleteSelected,
  };
}
