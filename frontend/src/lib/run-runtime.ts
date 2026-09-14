import type {
  RunEventResponse,
  RunResponse,
  RunResultResponse,
  RunSummaryResponse,
} from "@/types/run";

type RunRuntimeLike = Pick<RunResponse, "status" | "updated_at" | "metadata"> | RunSummaryResponse;

function metadataNumber(run: RunRuntimeLike, key: string): number | null {
  const value = run.metadata?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function runtimeSecondsFromRun(run: RunRuntimeLike, _nowMs = Date.now()): number | null {
  const storedRuntime = metadataNumber(run, "runtime_seconds");
  return storedRuntime !== null && storedRuntime >= 0 ? storedRuntime : null;
}

export function runtimeSecondsFromEvents(
  run: RunResponse,
  _events: RunEventResponse[],
  _result?: RunResultResponse | null,
  nowMs = Date.now(),
): number | null {
  return runtimeSecondsFromRun(run, nowMs);
}
