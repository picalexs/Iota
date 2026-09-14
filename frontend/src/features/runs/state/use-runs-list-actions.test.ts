import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RunSummaryResponse } from "@/types/run";
import { useRunsListActions } from "./use-runs-list-actions";

const performRunAction = vi.hoisted(() => vi.fn());
const deleteRun = vi.hoisted(() => vi.fn());

vi.mock("./run-actions", () => ({ performRunAction }));
vi.mock("@/api/runs", () => ({ deleteRun }));

const run: RunSummaryResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "RUNNING",
  algorithm: "vqe",
  backend_target: "statevector",
  backend_name: null,
  converged: null,
  chemical_accurate: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useRunsListActions", () => {
  it("refreshes and applies a successful bulk-action override", async () => {
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const refetchRuns = vi.fn().mockResolvedValue(undefined);
    const selection = { replaceSelection: vi.fn() };
    const serverRuns = [run];
    performRunAction.mockResolvedValue({ id: run.id, status: "PAUSING" });

    const { result } = renderHook(() =>
      useRunsListActions({
        serverRuns,
        invalidateRunsList,
        refetchRuns,
      }),
    );

    await act(async () => {
      await result.current.handleSelectedRunsAction("pause", [run], [run], selection);
    });

    expect(performRunAction).toHaveBeenCalledWith("pause", run.id);
    expect(invalidateRunsList).toHaveBeenCalledOnce();
    expect(refetchRuns).toHaveBeenCalledOnce();
    expect(selection.replaceSelection).toHaveBeenCalledWith([]);
    expect(result.current.runsWithOverrides[0]?.status).toBe("PAUSING");
    expect(result.current.pendingBulkAction).toBeNull();
  });

  it("opens and closes the bulk-delete dialog through the action boundary", () => {
    const { result } = renderHook(() =>
      useRunsListActions({
        serverRuns: [],
      }),
    );

    act(() => {
      result.current.openDeleteSelection();
    });
    expect(result.current.deleteSelectionOpen).toBe(true);

    act(() => {
      result.current.setDeleteSelectionOpen(false);
    });
    expect(result.current.deleteSelectionOpen).toBe(false);
    expect(result.current.deleteProgress).toBeNull();
  });
});
