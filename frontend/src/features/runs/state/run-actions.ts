import { cancelRun, pauseRun, restartRun, resumeRun } from "@/api/runs";
import type { RunActionResponse } from "./selection-actions";
import type { RunRowAction } from "../components/runs-list-row";
import type { UUID } from "@/types/run";

export async function performRunAction(
  action: RunRowAction,
  runId: UUID,
): Promise<RunActionResponse> {
  switch (action) {
    case "pause":
      return pauseRun(runId);
    case "resume":
      return resumeRun(runId);
    case "restart":
      return restartRun(runId);
    case "cancel":
      return cancelRun(runId);
  }
}
