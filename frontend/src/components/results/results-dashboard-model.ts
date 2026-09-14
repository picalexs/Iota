import type { LayoutItem } from "react-grid-layout";
import { verticalCompactor } from "react-grid-layout";

import { numberOrNull } from "@/components/runs/run-detail/use-run-event-timeline";
import { resolveChemicalAccuracyTargetHa } from "@/lib/results/accuracy";
import { extractClassicalReferences, type ClassicalReferences } from "@/lib/results/benchmarks";
import { getRunExecutionMetadata } from "@/lib/results/execution-metadata";
import {
  parseAlgorithmMetrics,
  type ParsedAlgorithmMetrics,
} from "@/lib/results/parse-algorithm-metrics";
import { runtimeSecondsFromEvents } from "@/lib/run-runtime";
import { tilesForAlgorithm, type AlgorithmType, type TileKey } from "@/lib/results/layout-presets";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

interface ResultsDashboardModelInput {
  readonly run: RunResponse;
  readonly result: RunResultResponse | null;
  readonly events: RunEventResponse[];
  readonly layout: LayoutItem[];
  readonly moleculePending: boolean;
  readonly eventsPending: boolean;
  readonly resultPending: boolean;
}

export interface ResultsDashboardModel {
  readonly algorithm: AlgorithmType;
  readonly execution: ReturnType<typeof getRunExecutionMetadata>;
  readonly parsed: ParsedAlgorithmMetrics;
  readonly currentIteration: number | null;
  readonly currentEnergy: number | null;
  readonly liveBestEnergy: number | null;
  readonly refs: ClassicalReferences;
  readonly runtimeSeconds: number | null;
  readonly chemicalAccuracyHa: number;
  readonly skqdSpectrumEnergies: number[];
  readonly visibleTileIds: TileKey[];
  readonly visibleLayout: LayoutItem[];
  readonly hiddenLayout: LayoutItem[];
  readonly activeTiles: ReadonlySet<string>;
  readonly pending: {
    readonly summary: boolean;
    readonly convergence: boolean;
    readonly timeline: boolean;
    readonly benchmark: boolean;
    readonly algorithm: boolean;
  };
}

function compactVisibleLayout(layout: LayoutItem[]): LayoutItem[] {
  return [
    ...verticalCompactor.compact(
      layout.map((item) => ({ ...item })),
      12,
    ),
  ];
}

function latestMonotonicIteration(events: RunEventResponse[]): number | null {
  let offset = 0;
  let previousRaw: number | null = null;
  let previousDisplay: number | null = null;

  for (const event of events) {
    const raw =
      numberOrNull(event.payload.completed_iterations) ?? numberOrNull(event.payload.iteration);
    if (raw === null) continue;
    if (previousRaw !== null && raw < previousRaw) {
      offset = previousDisplay ?? previousRaw;
    }
    let display = offset + raw;
    if (previousDisplay !== null && display < previousDisplay) {
      display = previousDisplay;
    }
    previousRaw = raw;
    previousDisplay = display;
  }

  return previousDisplay;
}

function latestNumericEnergy(events: RunEventResponse[]): number | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index]?.payload.step === "hardware_matrix_elements") continue;
    const energy = numberOrNull(events[index]?.payload.energy);
    if (energy === null) continue;
    return energy;
  }
  return null;
}

function firstNumericEventValue(events: RunEventResponse[], key: string): number | null {
  for (const event of events) {
    const value = numberOrNull(event.payload[key]);
    if (value !== null) return value;
  }
  return null;
}

function latestNumericEventValue(events: RunEventResponse[], key: string): number | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const value = numberOrNull(events[index]?.payload[key]);
    if (value !== null) return value;
  }
  return null;
}

function bestNumericEnergy(events: RunEventResponse[]): number | null {
  return events.reduce<number | null>((best, event) => {
    if (event.payload.step === "hardware_matrix_elements") return best;
    const energy = numberOrNull(event.payload.energy);
    if (energy === null) return best;
    return best === null || energy < best ? energy : best;
  }, null);
}

function finiteNumbers(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (entry): entry is number => typeof entry === "number" && Number.isFinite(entry),
  );
}

function visibleTileIdsForLayout(
  layoutTileSet: Set<string>,
  algorithm: AlgorithmType,
  backendTarget: RunResponse["backend_target"],
): TileKey[] {
  return tilesForAlgorithm(algorithm).filter((tileId) => {
    if (tileId === "hardware-mapping" && backendTarget !== "ibm_runtime") {
      return false;
    }
    return layoutTileSet.has(tileId);
  });
}

function liveReferences(iterationEvents: RunEventResponse[], resultRefs: ClassicalReferences) {
  return {
    hf: resultRefs.hf ?? firstNumericEventValue(iterationEvents, "hf_energy") ?? undefined,
    fci: resultRefs.fci ?? latestNumericEventValue(iterationEvents, "casci_energy") ?? undefined,
  } satisfies ClassicalReferences;
}

export function buildResultsDashboardModel({
  run,
  result,
  events,
  layout,
  moleculePending,
  eventsPending,
  resultPending,
}: ResultsDashboardModelInput): ResultsDashboardModel {
  const algorithm = run.algorithm ?? "unknown";
  const parsed = parseAlgorithmMetrics(algorithm, result?.algorithm_metrics);
  const iterationEvents = events.filter((event) => event.type === "iteration_update");
  const resultRefs = result ? extractClassicalReferences(result) : {};
  const visibleTileIds = visibleTileIdsForLayout(
    new Set(layout.map((item) => item.i)),
    parsed.type,
    run.backend_target,
  );
  const visibleTileSet = new Set<string>(visibleTileIds);
  const visibleLayout = compactVisibleLayout(layout.filter((item) => visibleTileSet.has(item.i)));
  const resultPanelsPending = eventsPending || resultPending;

  return {
    algorithm,
    execution: getRunExecutionMetadata(run, events, result),
    parsed,
    currentIteration: latestMonotonicIteration(iterationEvents),
    currentEnergy: latestNumericEnergy(iterationEvents),
    liveBestEnergy: bestNumericEnergy(iterationEvents),
    refs: liveReferences(iterationEvents, resultRefs),
    runtimeSeconds: runtimeSecondsFromEvents(run, events, result),
    chemicalAccuracyHa: resolveChemicalAccuracyTargetHa(run),
    skqdSpectrumEnergies:
      parsed.type === "skqd"
        ? finiteNumbers(parsed.metrics.krylov_extension_diagnostics?.["ritz_values"])
        : [],
    visibleTileIds,
    visibleLayout,
    hiddenLayout: layout.filter((item) => !visibleTileSet.has(item.i)),
    activeTiles: new Set(visibleLayout.map((item) => item.i)),
    pending: {
      summary: moleculePending || resultPanelsPending,
      convergence: resultPanelsPending,
      timeline: eventsPending,
      benchmark: resultPanelsPending,
      algorithm: resultPending,
    },
  };
}
