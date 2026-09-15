import type {
  AdvancedConfig,
  AlgorithmAwareRunCreate,
  BackendOptions,
  EasyGoal,
  RunAlgorithm,
} from "@/types/run";
import type { BenchmarkExecutionSettings } from "@/types/benchmark";

type BenchmarkRunConfigBase = Omit<AlgorithmAwareRunCreate, "easy_options" | "advanced_config">;

function resolveBackendTarget(
  execution: BenchmarkExecutionSettings,
): AlgorithmAwareRunCreate["backend_target"] {
  return execution.mode === "aer_simulator_backend_noise" ? "aer_simulator" : execution.mode;
}

function resolveBackendName(
  execution: BenchmarkExecutionSettings,
  backendTarget: AlgorithmAwareRunCreate["backend_target"],
): string | null {
  if (backendTarget === "statevector") {
    return null;
  }

  return execution.backendName;
}

function buildBackendOptions(backendName: string | null): BackendOptions {
  return {
    selection_policy: "manual",
    backend_name: backendName,
    shots: 4096,
    optimization_level: 1,
    seed_simulator: null,
    seed_transpiler: null,
    aer_method: "automatic",
  };
}

function buildNoiseProfile(
  execution: BenchmarkExecutionSettings,
): AlgorithmAwareRunCreate["noise_profile"] {
  if (execution.mode !== "aer_simulator_backend_noise") {
    return null;
  }

  return {
    source: "backend_derived",
    reference_backend: execution.backendName ?? "",
  };
}

function buildBaseRunConfig(
  algorithm: RunAlgorithm,
  basis: string,
  execution: BenchmarkExecutionSettings,
  options: { ibmRuntimeConfirmed?: boolean; clientRequestId?: string },
): BenchmarkRunConfigBase {
  const backendTarget = resolveBackendTarget(execution);
  const backendName = resolveBackendName(execution, backendTarget);

  return {
    molecule_id: "",
    client_request_id: options.clientRequestId,
    algorithm,
    mode: "easy",
    backend_target: backendTarget,
    backend_options: buildBackendOptions(backendName),
    basis_set_override: basis,
    noise_profile: buildNoiseProfile(execution),
    ibm_runtime_confirmed: options.ibmRuntimeConfirmed ?? false,
  };
}

export function buildSimpleBenchmarkRunConfig(
  algorithm: RunAlgorithm,
  basis: string,
  execution: BenchmarkExecutionSettings,
  goal: EasyGoal,
  options: { ibmRuntimeConfirmed?: boolean; clientRequestId?: string } = {},
): AlgorithmAwareRunCreate {
  return {
    ...buildBaseRunConfig(algorithm, basis, execution, options),
    mode: "easy",
    easy_options: { goal },
  };
}

export function buildAdvancedBenchmarkRunConfig(
  algorithm: RunAlgorithm,
  basis: string,
  execution: BenchmarkExecutionSettings,
  advancedConfig: AdvancedConfig,
  options: { ibmRuntimeConfirmed?: boolean; clientRequestId?: string } = {},
): AlgorithmAwareRunCreate {
  return {
    ...buildBaseRunConfig(algorithm, basis, execution, options),
    mode: "advanced",
    advanced_config: advancedConfig,
  };
}
