import { describe, expect, it } from "vitest";

import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { RunAlgorithm } from "@/types/run";
import * as featureControlSelectors from "./control-selectors";
import * as legacyControlSelectors from "@/pages/benchmark/benchmark-controls-state";
import {
  getBackendNameLabel,
  getBenchmarkCompletionRatio,
  getSelectedBlockedReasons,
  isBenchmarkRunDisabled,
  isBenchmarkWorkspaceLocked,
  shouldShowBenchmarkResetResults,
} from "./control-selectors";

describe("benchmark control state", () => {
  it("keeps the legacy module as an identity-preserving compatibility facade", () => {
    expect(legacyControlSelectors.getSelectedBlockedReasons).toBe(
      featureControlSelectors.getSelectedBlockedReasons,
    );
    expect(legacyControlSelectors.isBenchmarkRunDisabled).toBe(
      featureControlSelectors.isBenchmarkRunDisabled,
    );
  });

  it("derives labels and completion values without UI state", () => {
    expect(getBackendNameLabel("aer_simulator_backend_noise")).toBe("Noise reference backend");
    expect(getBackendNameLabel("statevector")).toBe("IBM backend");
    expect(getBenchmarkCompletionRatio(4, 1)).toBe(25);
    expect(getBenchmarkCompletionRatio(0, 0)).toBe(0);
  });

  it("keeps blocked molecule reasons in option order", () => {
    const h2 = BENCHMARK_MOLECULE_PRESETS.find((preset) => preset.key === "h2");
    expect(h2).toBeDefined();
    if (!h2) return;

    const blocked = { ...h2, key: "triplet-h2", multiplicity: 3 };
    expect(getSelectedBlockedReasons([blocked], new Set([blocked.key]))).toEqual([
      "Only singlet molecules can run in the current benchmark rollout.",
    ]);
  });

  it("locks the workspace for active or in-progress work", () => {
    expect(
      isBenchmarkWorkspaceLocked({
        total: 0,
        running: false,
        hasPausedBenchmark: false,
        actionInProgress: false,
      }),
    ).toBe(false);
    expect(
      isBenchmarkWorkspaceLocked({
        total: 1,
        running: false,
        hasPausedBenchmark: false,
        actionInProgress: false,
      }),
    ).toBe(true);
  });

  it("requires a molecule and algorithm for simple mode", () => {
    expect(
      isBenchmarkRunDisabled({
        workspaceLocked: false,
        selectedMolecules: new Set(),
        benchmarkMode: "simple",
        selectedAlgorithms: new Set(),
        algorithmVariants: [],
        hasBlockedSelection: false,
        backendReady: true,
      }),
    ).toBe(true);
    expect(
      isBenchmarkRunDisabled({
        workspaceLocked: false,
        selectedMolecules: new Set(["h2"]),
        benchmarkMode: "simple",
        selectedAlgorithms: new Set<RunAlgorithm>(["vqe"]),
        algorithmVariants: [],
        hasBlockedSelection: false,
        backendReady: true,
      }),
    ).toBe(false);
  });

  it("requires an advanced variant and hides reset while active", () => {
    expect(
      isBenchmarkRunDisabled({
        workspaceLocked: false,
        selectedMolecules: new Set(["h2"]),
        benchmarkMode: "advanced",
        selectedAlgorithms: new Set(),
        algorithmVariants: [],
        hasBlockedSelection: false,
        backendReady: true,
      }),
    ).toBe(true);
    expect(
      shouldShowBenchmarkResetResults({
        total: 1,
        running: true,
        hasPausedBenchmark: false,
        actionInProgress: false,
      }),
    ).toBe(false);
  });
});
