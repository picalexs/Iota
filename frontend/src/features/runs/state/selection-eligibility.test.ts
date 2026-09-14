import { describe, expect, it } from "vitest";
import type { RunSummaryResponse } from "@/types/run";
import { getRunSelectionEligibility } from "./selection-eligibility";

function run(id: string, status: RunSummaryResponse["status"]): RunSummaryResponse {
  return { id, status } as RunSummaryResponse;
}

describe("getRunSelectionEligibility", () => {
  it("groups selected runs by supported bulk action", () => {
    const runs = [
      run("created", "CREATED"),
      run("paused", "PAUSED"),
      run("completed", "COMPLETED"),
      run("running", "RUNNING"),
    ];

    const eligibility = getRunSelectionEligibility(
      runs,
      new Set(["created", "paused", "completed", "running"]),
    );

    expect(eligibility.selectedRuns.map((item) => item.id)).toEqual([
      "created",
      "paused",
      "completed",
      "running",
    ]);
    expect(eligibility.pausableSelectedRuns.map((item) => item.id)).toEqual(["created", "running"]);
    expect(eligibility.resumableSelectedRuns.map((item) => item.id)).toEqual(["paused"]);
    expect(eligibility.restartableSelectedRuns.map((item) => item.id)).toEqual([
      "paused",
      "completed",
    ]);
    expect(eligibility.cancellableSelectedRuns.map((item) => item.id)).toEqual([
      "created",
      "paused",
      "running",
    ]);
  });

  it("ignores selected IDs that are not on the current page", () => {
    const eligibility = getRunSelectionEligibility(
      [run("visible", "FAILED")],
      new Set(["missing", "visible"]),
    );

    expect(eligibility.selectedRuns.map((item) => item.id)).toEqual(["visible"]);
    expect(eligibility.resumableSelectedRuns.map((item) => item.id)).toEqual(["visible"]);
    expect(eligibility.restartableSelectedRuns.map((item) => item.id)).toEqual(["visible"]);
    expect(eligibility.pausableSelectedRuns).toEqual([]);
    expect(eligibility.cancellableSelectedRuns).toEqual([]);
  });
});
