import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  isRunAlgorithm,
  isRunEventType,
  isRunStatus,
  BACKEND_TARGETS,
  EASY_GOALS,
  RUN_ALGORITHMS,
  RUN_EVENT_TYPES,
  RUN_STATUSES,
} from "./run-status";

interface SharedIdentifierFixture {
  run_statuses: string[];
  algorithms: string[];
  backend_targets: string[];
  easy_goals: string[];
  run_event_types: string[];
}

const sharedIdentifierFixture = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "..", "shared", "contracts", "identifier-fixtures.json"),
    "utf8",
  ),
) as SharedIdentifierFixture;

function asSet(values: readonly string[]): Set<string> {
  return new Set(values);
}

describe("generated run identifier guards", () => {
  it("accepts every generated status and algorithm value", () => {
    expect(RUN_STATUSES.every(isRunStatus)).toBe(true);
    expect(RUN_ALGORITHMS.every(isRunAlgorithm)).toBe(true);
  });

  it("keeps the complete runtime tuples aligned with the wire contract", () => {
    expect(asSet(RUN_STATUSES)).toEqual(asSet(sharedIdentifierFixture.run_statuses));
    expect(asSet(RUN_ALGORITHMS)).toEqual(asSet(sharedIdentifierFixture.algorithms));
    expect(asSet(BACKEND_TARGETS)).toEqual(asSet(sharedIdentifierFixture.backend_targets));
    expect(asSet(EASY_GOALS)).toEqual(asSet(sharedIdentifierFixture.easy_goals));
    expect(asSet(RUN_EVENT_TYPES)).toEqual(asSet(sharedIdentifierFixture.run_event_types));
  });

  it("accepts every generated event value", () => {
    expect(RUN_EVENT_TYPES.every(isRunEventType)).toBe(true);
  });

  it("rejects unknown wire values", () => {
    expect(isRunStatus("unknown")).toBe(false);
    expect(isRunAlgorithm("unknown")).toBe(false);
    expect(isRunEventType("unknown")).toBe(false);
  });
});
