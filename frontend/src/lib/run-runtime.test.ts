import { describe, expect, it } from "vitest";

import { runtimeSecondsFromEvents, runtimeSecondsFromRun } from "./run-runtime";
import type { RunEventResponse, RunResponse } from "@/types/run";

const run: RunResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "COMPLETED",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "statevector",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2026-01-01T10:00:00Z",
  updated_at: "2026-01-01T10:30:00Z",
};

function event(
  sequence: number,
  type: RunEventResponse["type"],
  created_at: string,
  payload: Record<string, unknown>,
): RunEventResponse {
  return {
    id: sequence,
    run_id: run.id,
    sequence,
    type,
    payload,
    created_at,
  };
}

describe("run runtime helpers", () => {
  it("uses persisted runtime metadata when present", () => {
    expect(
      runtimeSecondsFromRun({
        ...run,
        metadata: { runtime_seconds: 42.5 },
      }),
    ).toBe(42.5);
  });

  it("does not estimate active runtime from wall-clock timestamps", () => {
    expect(
      runtimeSecondsFromRun(
        {
          ...run,
          status: "RUNNING",
          metadata: { run_started_at: "2026-01-01T10:10:00Z" },
        },
        new Date("2026-01-01T10:12:30Z").getTime(),
      ),
    ).toBeNull();
  });

  it("does not estimate runtime from event timestamps", () => {
    const events = [
      event(1, "status_changed", "2026-01-01T10:05:00Z", { status: "RUNNING" }),
      event(2, "iteration_update", "2026-01-01T10:05:10Z", { energy: -1 }),
      event(3, "status_changed", "2026-01-01T10:07:30Z", { status: "COMPLETED" }),
    ];

    expect(runtimeSecondsFromEvents(run, events)).toBeNull();
  });
});
