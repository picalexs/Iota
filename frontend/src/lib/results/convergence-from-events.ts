import type { RunEventResponse } from "@/types/run";

export interface ConvergencePoint {
  iteration: number;
  energy: number;
  deltaEnergy?: number;
  parameterL2Norm?: number;
}

function payloadNumber(payload: Record<string, unknown>, key: string): number | undefined {
  const value = payload[key];
  return typeof value === "number" ? value : undefined;
}

function eventConvergenceEnergy(event: RunEventResponse): number | null {
  if (event.type !== "iteration_update") return null;
  if (event.payload.step === "hardware_matrix_elements") return null;
  return payloadNumber(event.payload, "energy") ?? null;
}

function eventIteration(
  payload: Record<string, unknown>,
  hardwareIteration: number | null,
  fallbackIteration: number,
): number {
  if (hardwareIteration !== null) return hardwareIteration;
  const convergenceIteration = payloadNumber(payload, "convergence_iteration");
  if (convergenceIteration !== undefined) return convergenceIteration;
  if (payload.step === "measured_matrix_elements" || payload.step === "solve") {
    return fallbackIteration;
  }
  return (
    payloadNumber(payload, "completed_iterations") ??
    payloadNumber(payload, "iteration") ??
    fallbackIteration
  );
}

function convergencePoint(
  payload: Record<string, unknown>,
  iteration: number,
  energy: number,
): ConvergencePoint {
  return {
    iteration,
    energy,
    deltaEnergy: payloadNumber(payload, "delta_energy"),
    parameterL2Norm: payloadNumber(payload, "parameter_l2_norm"),
  };
}

export function convergenceFromEvents(events: RunEventResponse[]): ConvergencePoint[] {
  const pointsByIteration = new Map<number, ConvergencePoint>();
  let fallbackIteration = 0;

  for (const ev of events) {
    const p = ev.payload;
    const energy = eventConvergenceEnergy(ev);
    if (energy === null) continue;

    fallbackIteration += 1;
    const step = eventIteration(p, null, fallbackIteration);

    pointsByIteration.set(step, convergencePoint(p, step, energy));
  }

  return Array.from(pointsByIteration.values()).sort((a, b) => a.iteration - b.iteration);
}

export function mergeConvergenceTrace(
  events: RunEventResponse[],
  algorithmMetrics: Record<string, unknown> | null | undefined,
): ConvergencePoint[] {
  const fromEvents = convergenceFromEvents(events);
  if (fromEvents.length > 0) return fromEvents;

  // Fallback: VQE convergence_trace or SQD sci_energies
  if (!algorithmMetrics) return [];

  const trace = algorithmMetrics["convergence_trace"];
  if (Array.isArray(trace)) {
    return trace
      .filter((energy): energy is number => typeof energy === "number")
      .map((energy, i) => ({ iteration: i + 1, energy }));
  }

  const sciEnergies = algorithmMetrics["sci_energies"];
  if (Array.isArray(sciEnergies)) {
    return sciEnergies
      .filter((energy): energy is number => typeof energy === "number")
      .map((energy, i) => ({ iteration: i + 1, energy }));
  }

  return [];
}
