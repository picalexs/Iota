/** Public compatibility facade for the benchmark workspace hook. */

import { useBenchmarkController } from "./benchmark-state/use-benchmark-controller";

export { clearBenchmarkWorkspaceViewCache } from "./benchmark-state/use-benchmark-controller";

export function useBenchmarkState(options: { benchmarkId?: string | null } = {}) {
  return useBenchmarkController(options);
}
