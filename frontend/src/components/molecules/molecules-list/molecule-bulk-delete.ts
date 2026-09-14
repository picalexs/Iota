import { deleteMolecule } from "@/api/molecules";
import { getErrorMessage } from "@/lib/error-handler";
import type { MoleculeSummaryResponse } from "@/types/run";

export type MoleculeDeleteProgress = { completed: number; total: number };

type DeleteMolecule = (
  moleculeId: string,
  options: { deleteAssociatedRuns: boolean },
) => Promise<unknown>;

export interface MoleculeBulkDeleteResult {
  failedIds: string[];
  summary: string | null;
}

interface MoleculeBulkDeleteOptions {
  deleteAssociatedRuns: boolean;
  onProgress?: (progress: MoleculeDeleteProgress) => void;
  deleteMoleculeFn?: DeleteMolecule;
}

function buildDeleteSummary(results: PromiseSettledResult<string>[], failedIds: string[]): string {
  const firstError = getErrorMessage(
    results.find((result) => result.status === "rejected")?.reason,
    "Failed to delete molecules.",
  );

  const deletedCount = results.length - failedIds.length;
  if (deletedCount === 0) {
    return firstError;
  }

  const moleculeLabel = deletedCount === 1 ? "molecule" : "molecules";
  return `Deleted ${deletedCount} ${moleculeLabel}, ${failedIds.length} failed. ${firstError}`;
}

export async function deleteSelectedMolecules(
  selectedMolecules: readonly MoleculeSummaryResponse[],
  {
    deleteAssociatedRuns,
    onProgress,
    deleteMoleculeFn = deleteMolecule,
  }: MoleculeBulkDeleteOptions,
): Promise<MoleculeBulkDeleteResult> {
  const results: PromiseSettledResult<string>[] = [];

  for (const [index, molecule] of selectedMolecules.entries()) {
    try {
      await deleteMoleculeFn(molecule.id, { deleteAssociatedRuns });
      results.push({ status: "fulfilled", value: molecule.id });
    } catch (error) {
      results.push({ status: "rejected", reason: error });
    } finally {
      onProgress?.({ completed: index + 1, total: selectedMolecules.length });
    }
  }

  const failedIds = results.flatMap((result, index) =>
    result.status === "rejected" && selectedMolecules[index] ? [selectedMolecules[index].id] : [],
  );

  return {
    failedIds,
    summary: failedIds.length > 0 ? buildDeleteSummary(results, failedIds) : null,
  };
}
