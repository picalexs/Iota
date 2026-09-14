import { describe, expect, it } from "vitest";
import {
  buildBulkActionErrorSummary,
  buildDeleteRunsErrorSummary,
  describeRunSelectionAction,
  getDeleteRunsDescription,
  getDeleteRunsStatus,
  getDeleteRunsTitle,
  getSelectionActionLabel,
  runStatusOverride,
  type RunActionResponse,
} from "./selection-actions";
import type { RunSummaryResponse } from "@/types/run";

const run = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  status: "RUNNING",
} as RunSummaryResponse;

describe("runs selection action policy", () => {
  it("normalizes restart responses that create a child run", () => {
    const override = runStatusOverride(run, "restart", {
      child_run_id: "bbbbbbbb-0000-0000-0000-000000000001",
    });

    expect(override.status).toBe("QUEUED");
    expect(override.updated_at).toEqual(expect.any(String));
  });

  it("describes skipped selection actions and delete progress", () => {
    expect(describeRunSelectionAction("pause", 1, 2)).toContain("2 selected runs are");
    expect(getSelectionActionLabel("Pause", 3)).toBe("Pause (3)");
    expect(getDeleteRunsTitle(1)).toBe("Delete selected run?");
    expect(getDeleteRunsDescription(1)).toContain("cancelled before removal");
    expect(getDeleteRunsStatus({ completed: 1, total: 3 })).toBe("Deleting 1 of 3...");
  });

  it("summarizes partial bulk-action and deletion failures", () => {
    const results: PromiseSettledResult<{
      run: RunSummaryResponse;
      response: RunActionResponse;
    }>[] = [
      { status: "fulfilled", value: { run, response: {} as RunActionResponse } },
      { status: "rejected", reason: new Error("backend unavailable") },
    ];

    expect(buildBulkActionErrorSummary("pause", results)).toBe(
      "Paused 1 run, 1 failed. backend unavailable",
    );
    expect(
      buildDeleteRunsErrorSummary(
        [
          { status: "fulfilled", value: run.id },
          { status: "rejected", reason: new Error("delete failed") },
        ],
        ["bbbbbbbb-0000-0000-0000-000000000001"],
      ),
    ).toBe("Deleted 1 run, 1 failed. delete failed");
  });
});
