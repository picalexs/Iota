import type {
  AdvancedConfig,
  AlgorithmAwareRunCreate,
  BackendOptions,
  EasyGoal,
  RunAlgorithm,
} from "@/types/run";
import { getDefaultBenchmarkShots, type BenchmarkExecutionSettings } from "@/types/benchmark";

type BenchmarkRunConfigBase = Omit<AlgorithmAwareRunCreate, "easy_options" | "advanced_config">;

function resolveBackendTarget(
  execution: BenchmarkExecutionSettings,
): AlgorithmAwareRunCreate["backend_target"] {
  return execution.mode === "aer_simulator_backend_noise" ? "aer_simulator" : execution.mode;
}

function buildBackendOptions(
  execution: BenchmarkExecutionSettings,
  backendTarget: AlgorithmAwareRunCreate["backend_target"],
): BackendOptions {
  const isAer = backendTarget === "aer_simulator";
  const useGpuShotBatching =
    isAer &&
    execution.mode === "aer_simulator_backend_noise" &&
    execution.device === "GPU";
  return {
    selection_policy: "manual",
    backend_name: execution.backendName,
    shots: execution.shots ?? getDefaultBenchmarkShots(execution.mode),
    optimization_level: 1,
    seed_simulator: null,
    seed_transpiler: null,
    aer_method: isAer ? (execution.aerMethod ?? "automatic") : "automatic",
    device: isAer ? (execution.device ?? null) : null,
    batched_shots_gpu: useGpuShotBatching ? true : null,
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

  return {
    molecule_id: "",
    client_request_id: options.clientRequestId,
    algorithm,
    mode: "easy",
    backend_target: backendTarget,
    backend_options: buildBackendOptions(execution, backendTarget),
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
