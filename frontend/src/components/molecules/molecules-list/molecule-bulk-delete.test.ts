import { describe, expect, it, vi } from "vitest";

import { deleteSelectedMolecules, type MoleculeDeleteProgress } from "./molecule-bulk-delete";
import type { MoleculeSummaryResponse } from "@/types/run";

function selectedMolecules(...ids: string[]): MoleculeSummaryResponse[] {
  return ids.map((id) => ({ id }) as MoleculeSummaryResponse);
}

describe("deleteSelectedMolecules", () => {
  it("deletes sequentially, reports progress, and keeps failed IDs", async () => {
    const deleteMoleculeFn = vi.fn(async (id: string) => {
      if (id === "mol-2") {
        throw new Error("molecule is still referenced");
      }
    });
    const progress: MoleculeDeleteProgress[] = [];

    const result = await deleteSelectedMolecules(selectedMolecules("mol-1", "mol-2", "mol-3"), {
      deleteAssociatedRuns: true,
      deleteMoleculeFn,
      onProgress: (nextProgress) => progress.push(nextProgress),
    });

    expect(deleteMoleculeFn).toHaveBeenNthCalledWith(1, "mol-1", {
      deleteAssociatedRuns: true,
    });
    expect(deleteMoleculeFn).toHaveBeenNthCalledWith(2, "mol-2", {
      deleteAssociatedRuns: true,
    });
    expect(deleteMoleculeFn).toHaveBeenNthCalledWith(3, "mol-3", {
      deleteAssociatedRuns: true,
    });
    expect(progress).toEqual([
      { completed: 1, total: 3 },
      { completed: 2, total: 3 },
      { completed: 3, total: 3 },
    ]);
    expect(result.failedIds).toEqual(["mol-2"]);
    expect(result.summary).toBe("Deleted 2 molecules, 1 failed. molecule is still referenced");
  });

  it("returns no error summary when every selected molecule is deleted", async () => {
    const result = await deleteSelectedMolecules(selectedMolecules("mol-1"), {
      deleteAssociatedRuns: false,
      deleteMoleculeFn: vi.fn().mockResolvedValue(undefined),
    });

    expect(result).toEqual({ failedIds: [], summary: null });
  });
});
