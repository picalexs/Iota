import { describe, expect, it } from "vitest";
import { benchmarkKeys, moleculeKeys, runKeys } from "./query-keys";

describe("query key factories", () => {
  it("keeps list keys stable for equivalent parameter objects", () => {
    expect(runKeys.list({ limit: 25 })).toEqual(["runs", "list", { limit: 25 }]);
    expect(runKeys.list({ limit: 25 })).toEqual(runKeys.list({ limit: 25 }));
    expect(moleculeKeys.list({ q: "water" })).toEqual(["molecules", "list", { q: "water" }]);
  });

  it("separates detail, summary, and collection keys", () => {
    expect(runKeys.detail("run-1")).toEqual(["runs", "detail", "run-1"]);
    expect(runKeys.events("run-1")).toEqual(["runs", "events", "run-1"]);
    expect(runKeys.allSummaries).toEqual(["runs", "summaries", "all"]);
    expect(benchmarkKeys.list()).toEqual(["benchmarks", "list", undefined]);
  });
});
