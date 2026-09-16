import { fetchRunConfigMetadata } from "@/api/runs";
import { BACKEND_TARGETS, EASY_GOALS, RUN_ALGORITHMS } from "@/types/run-status";
import {
  buildRecommendedAdvancedPatch,
  CHEMICAL_ACCURACY_TARGET_OPTIONS,
  goalForChemicalAccuracyTarget,
} from "@/lib/run-form-recommendations";
import type {
  ConfigChoiceMetadata,
  MoleculeResponse,
  RunConfigMetadataResponse,
  QSEComplexScalar,
  RunAlgorithm,
  SimulationRunFormData,
  QSEProvidedSectorRow,
  QSEReferenceScalar,
  QSESectorAmplitude,
} from "@/types/run";

interface ParseResult<T> {
  values: T | null;
  error?: string;
}

type ManualSettingsPatch = Partial<
  Pick<
    SimulationRunFormData,
    | "easy_options"
    | "advanced_vqe"
    | "advanced_sqd"
    | "advanced_kqd"
    | "advanced_qfd"
    | "advanced_qse"
    | "advanced_skqd"
  >
>;

let runFormConfigMetadataCache: RunConfigMetadataResponse | null = null;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseJson(text: string): { value: unknown; error?: string } {
  try {
    return { value: JSON.parse(text) };
  } catch {
    return { value: null, error: "Enter valid JSON" };
  }
}

function normalizeComplexScalar(value: unknown): QSEReferenceScalar | null {
  if (isFiniteNumber(value)) {
    return value;
  }

  if (Array.isArray(value) && value.length === 2) {
    const [real, imag] = value;
    if (isFiniteNumber(real) && isFiniteNumber(imag)) {
      return { real, imag };
    }
  }

  if (typeof value === "object" && value !== null) {
    const real = (value as Record<string, unknown>).real;
    const imag = (value as Record<string, unknown>).imag ?? 0;
    if (isFiniteNumber(real) && isFiniteNumber(imag)) {
      return { real, imag } satisfies QSEComplexScalar;
    }
  }

  return null;
}

export function parseProvidedStateVectorInput(text: string): ParseResult<QSEReferenceScalar[]> {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { values: null, error: "Provide a state vector for the QSE reference" };
  }

  const parsed = parseJson(trimmed);
  if (parsed.error) {
    return { values: null, error: parsed.error };
  }
  if (!Array.isArray(parsed.value)) {
    return { values: null, error: "State vector JSON must be an array" };
  }

  const values = parsed.value.map(normalizeComplexScalar);
  if (values.some((value) => value == null)) {
    return {
      values: null,
      error: "State vector entries must be numbers or { real, imag } objects",
    };
  }

  return { values: values as QSEReferenceScalar[] };
}

export function parseProvidedSectorRowsInput(
  rows: QSEProvidedSectorRow[],
): ParseResult<QSESectorAmplitude[]> {
  const cleanedRows = rows.filter(
    (row) =>
      row.bitstring.trim().length > 0 || row.real.trim().length > 0 || row.imag.trim().length > 0,
  );

  if (cleanedRows.length === 0) {
    return { values: null, error: "Provide at least one determinant amplitude" };
  }

  const values: QSESectorAmplitude[] = [];
  for (const row of cleanedRows) {
    const bitstring = row.bitstring.trim();
    if (!/^[01]+$/.test(bitstring)) {
      return { values: null, error: "Bitstrings must contain only 0 and 1" };
    }

    const real = Number(row.real);
    const imagText = row.imag.trim();
    const imag = imagText.length === 0 ? 0 : Number(imagText);
    if (!Number.isFinite(real) || !Number.isFinite(imag)) {
      return { values: null, error: "Determinant amplitudes must be numeric" };
    }

    values.push({
      bitstring,
      amplitude: imag === 0 ? real : { real, imag },
    });
  }

  return { values };
}

export function parseRecordInput(
  text: string,
  label: string,
): ParseResult<Record<string, unknown>> {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { values: null };
  }

  const parsed = parseJson(trimmed);
  if (parsed.error) {
    return { values: null, error: `${label} must be valid JSON` };
  }
  if (typeof parsed.value !== "object" || parsed.value === null || Array.isArray(parsed.value)) {
    return { values: null, error: `${label} must be a JSON object` };
  }

  return { values: parsed.value as Record<string, unknown> };
}

export function parseNumberArrayInput(text: string, label: string): ParseResult<number[]> {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { values: null };
  }

  const parsed = parseJson(trimmed);
  if (parsed.error) {
    return { values: null, error: `${label} must be valid JSON` };
  }
  if (!Array.isArray(parsed.value) || !parsed.value.every(isFiniteNumber)) {
    return { values: null, error: `${label} must be a JSON array of numbers` };
  }

  return { values: parsed.value };
}

export function parseParameterBoundsInput(text: string): ParseResult<Array<[number, number]>> {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { values: null };
  }

  const parsed = parseJson(trimmed);
  if (parsed.error) {
    return { values: null, error: "Parameter bounds must be valid JSON" };
  }
  if (
    !Array.isArray(parsed.value) ||
    !parsed.value.every(
      (entry) =>
        Array.isArray(entry) &&
        entry.length === 2 &&
        entry.every((value) => typeof value === "number" && Number.isFinite(value)),
    )
  ) {
    return {
      values: null,
      error: "Parameter bounds must be a JSON array of [min, max] numeric pairs",
    };
  }

  return { values: parsed.value as Array<[number, number]> };
}

function fallbackConfigMetadata(): RunConfigMetadataResponse {
  const buildChoice = (
    id: string,
    description: string,
    metadata: ConfigChoiceMetadata["metadata"],
  ): ConfigChoiceMetadata => ({
    id,
    label: id === "L_BFGS_B" ? "L-BFGS-B" : id,
    aliases: [],
    description,
    supported_algorithms: ["vqe", "qse"],
    metadata,
  });

  return {
    catalog_version: "2026-09-16-v22",
    algorithms: [...RUN_ALGORITHMS],
    backend_targets: [...BACKEND_TARGETS],
    easy_goals: [...EASY_GOALS],
    easy_goal_presets: [
      { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
      { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
      { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
    ],
    ansatzes: [
      buildChoice("EfficientSU2", "Hardware-efficient SU(2) ansatz.", {
        canonical_worker_id: "efficientsu2",
        default_reps: 2,
      }),
      buildChoice(
        "NumberPreserving",
        "Hartree-Fock-seeded electron-number-preserving ansatz.",
        {
          canonical_worker_id: "numberpreserving",
          default_reps: 2,
        },
      ),
      buildChoice("RealAmplitudes", "Real-valued Ry/CX ansatz.", {
        canonical_worker_id: "realamplitudes",
        default_reps: 2,
      }),
      buildChoice("TwoLocal", "Two-local Ry/Rz plus CX ansatz.", {
        canonical_worker_id: "twolocal",
        default_reps: 2,
      }),
    ],
    optimizers: [
      buildChoice("COBYLA", "Derivative-free constrained optimizer.", {
        kind: "scipy",
        allowed_options: ["catol", "f_target", "rhobeg", "rhoend", "tol"],
        supports_max_function_evaluations: false,
      }),
      buildChoice("SPSA", "Stochastic optimizer for noisy evaluations.", {
        kind: "spsa",
        allowed_options: ["allowed_increase", "blocking", "learning_rate", "perturbation"],
        supports_max_function_evaluations: false,
      }),
      buildChoice("SLSQP", "Gradient-based SciPy optimizer.", {
        kind: "scipy",
        allowed_options: ["eps", "ftol", "tol"],
        supports_max_function_evaluations: false,
      }),
      buildChoice("L_BFGS_B", "Bound-aware quasi-Newton optimizer.", {
        kind: "scipy",
        allowed_options: ["eps", "ftol", "gtol", "maxfun", "maxls", "tol"],
        supports_max_function_evaluations: true,
      }),
    ],
    defaults: {
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      qse_reference_ansatz_name: "NumberPreserving",
      qse_reference_optimizer_name: "COBYLA",
    },
    limits: {},
    capabilities: {},
  };
}

export function getRunFormConfigMetadata(): RunConfigMetadataResponse | null {
  return runFormConfigMetadataCache;
}

export async function loadRunFormConfigMetadata(): Promise<RunConfigMetadataResponse> {
  try {
    const metadata = await fetchRunConfigMetadata();
    runFormConfigMetadataCache = metadata;
    return metadata;
  } catch {
    if (runFormConfigMetadataCache == null) {
      runFormConfigMetadataCache = fallbackConfigMetadata();
    }
    return runFormConfigMetadataCache;
  }
}

export function recommendedSettingsSummary(thresholdHa: number | null | undefined): string {
  const goal = goalForChemicalAccuracyTarget(thresholdHa);
  const option = CHEMICAL_ACCURACY_TARGET_OPTIONS.find((candidate) => candidate.goal === goal);
  const label = option?.label ?? "1.6 mHa";
  switch (goal) {
    case "fastest":
      return `${label} maps to the quick-scan preset family with smaller budgets and looser tolerances.`;
    case "best_accuracy":
      return `${label} maps to the high-accuracy preset family with larger subspaces, samples, and variational depth.`;
    case "balanced":
    default:
      return `${label} maps to the balanced preset family used for day-to-day production comparisons.`;
  }
}

export function buildRecommendedManualSettings(
  algorithm: RunAlgorithm | null,
  thresholdHa: number | null | undefined,
  molecule: MoleculeResponse | null,
): ManualSettingsPatch | null {
  if (algorithm == null) {
    return null;
  }

  const goal = goalForChemicalAccuracyTarget(thresholdHa);
  const patch = buildRecommendedAdvancedPatch(
    algorithm,
    goal,
    molecule?.active_space ?? null,
    getRunFormConfigMetadata(),
  );
  return { [patch.field]: patch.value } as ManualSettingsPatch;
}
