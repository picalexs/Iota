import type { ComponentType } from "react";
import { Atom, Cpu, SlidersHorizontal, Zap } from "lucide-react";

import type { InfoComponentId } from "@/content/info/components";
import type { NoiseModelId } from "@/content/info/noise-models";
import {
  BACKEND_TARGETS,
  RUN_ALGORITHMS,
  type BackendTarget,
  type RunAlgorithm,
} from "@/types/run";

export type InfoCollectionKey = "algorithms" | "components" | "backends" | "noise-models";

export interface InfoCollectionDefinition {
  key: InfoCollectionKey;
  title: string;
  description: string;
  to: "/info/algorithms" | "/info/components" | "/info/backends" | "/info/noise-models";
  icon: ComponentType<{ className?: string }>;
  highlights: string[];
  detailsMinHeightClassName?: string;
}

export interface RelatedTopic {
  label: string;
  description: string;
  to:
    | "/info/algorithms"
    | "/info/components"
    | "/info/backends"
    | "/info/noise-models"
    | "/help/parameters"
    | "/info/algorithms/$algorithmId"
    | "/info/components/$componentId"
    | "/info/backends/$backendId"
    | "/info/noise-models/$noiseModelId";
  params?: {
    algorithmId?: RunAlgorithm;
    componentId?: InfoComponentId;
    backendId?: BackendTarget;
    noiseModelId?: NoiseModelId;
  };
}

export const ALGORITHM_IDS: RunAlgorithm[] = [...RUN_ALGORITHMS];
export const BACKEND_IDS: BackendTarget[] = [...BACKEND_TARGETS];

export const INFO_COLLECTIONS: InfoCollectionDefinition[] = [
  {
    key: "algorithms",
    title: "Algorithms",
    description:
      "Reference notes for the chemistry solvers, subspace methods, and sample-based workflows available in Quantum Studio.",
    to: "/info/algorithms",
    icon: Atom,
    highlights: ["Ground-state baselines", "Projected subspaces", "Sample-driven diagonalization"],
  },
  {
    key: "components",
    title: "Components",
    description:
      "Longer notes for ansatzes, optimizers, basis sets, and reference-state choices that shape how the algorithms behave.",
    to: "/info/components",
    icon: SlidersHorizontal,
    highlights: ["Ansatz depth", "Optimizer behavior", "Chemistry setup"],
  },
  {
    key: "backends",
    title: "Backends",
    description:
      "Execution targets covering exact simulation, local shot-based studies, and managed IBM hardware primitives.",
    to: "/info/backends",
    icon: Cpu,
    highlights: ["Ideal verification", "Shot-based simulation", "Hardware routing"],
    detailsMinHeightClassName: "sm:min-h-[10rem]",
  },
  {
    key: "noise-models",
    title: "Noise Models",
    description:
      "Error presets and backend-derived calibration models for studying how noise changes algorithm behavior.",
    to: "/info/noise-models",
    icon: Zap,
    highlights: ["Gate errors", "Relaxation and readout", "Calibration snapshots"],
    detailsMinHeightClassName: "sm:min-h-[10rem]",
  },
];

const ALGORITHM_RELATED: Record<RunAlgorithm, RelatedTopic[]> = {
  vqe: [
    {
      label: "Statevector Simulator",
      description: "Best for baseline VQE convergence checks before adding sampling noise.",
      to: "/info/backends/$backendId",
      params: { backendId: "statevector" },
    },
    {
      label: "Aer Simulator",
      description: "Use it when you want shots, simulator methods, or local noise presets.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
    {
      label: "Ansatz families",
      description:
        "The circuit template and `reps` choice usually explain most VQE behavior shifts.",
      to: "/info/components/$componentId",
      params: { componentId: "ansatzes" },
    },
    {
      label: "Thermal Relaxation",
      description: "Useful when ansatz depth or gate scheduling starts to dominate energy drift.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "thermal_relaxation" },
    },
  ],
  qse: [
    {
      label: "VQE",
      description:
        "QSE often starts from a variational reference, so the VQE page is the natural companion.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
    {
      label: "Statevector Simulator",
      description: "Strong reference studies are easiest to inspect on an exact backend first.",
      to: "/info/backends/$backendId",
      params: { backendId: "statevector" },
    },
    {
      label: "Readout Bias",
      description:
        "Measurement confusion can distort the projected matrix elements QSE depends on.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "readout_bias" },
    },
    {
      label: "Reference states",
      description:
        "QSE quality is often dominated by the choice of Hartree-Fock, VQE, or user-provided reference.",
      to: "/info/components/$componentId",
      params: { componentId: "reference-states" },
    },
  ],
  kqd: [
    {
      label: "QFD",
      description:
        "Both methods build projected subspaces from time evolution and share similar diagnostics.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qfd" },
    },
    {
      label: "IBM Quantum Runtime",
      description:
        "Hardware Krylov runs route through Runtime primitives once backend resolution succeeds.",
      to: "/info/backends/$backendId",
      params: { backendId: "ibm_runtime" },
    },
    {
      label: "Backend-Derived Noise",
      description:
        "Helpful when you want a hardware-calibrated context for projected matrix measurements.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "backend_derived" },
    },
  ],
  qfd: [
    {
      label: "KQD",
      description:
        "A close neighboring subspace method if you want to compare Krylov and filter constructions.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "kqd" },
    },
    {
      label: "Aer Simulator",
      description:
        "Good for testing time grids and filter conditioning without hardware queue time.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
    {
      label: "Depolarizing CX Noise",
      description:
        "A quick way to stress-test long entangling evolutions in filtered subspace runs.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "depolarizing_cx" },
    },
  ],
  sqd: [
    {
      label: "SKQD",
      description:
        "SKQD merges samples from several Krylov states before the selected-CI solve, so this is the most direct follow-on read.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "skqd" },
    },
    {
      label: "IBM Quantum Runtime",
      description:
        "Sampling-heavy paths can target IBM hardware when credentials and algorithm support align.",
      to: "/info/backends/$backendId",
      params: { backendId: "ibm_runtime" },
    },
    {
      label: "Readout Bias",
      description:
        "Bitstring-based workflows are especially sensitive to assignment errors after measurement.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "readout_bias" },
    },
  ],
  skqd: [
    {
      label: "SQD",
      description:
        "SKQD reports its sampled Krylov-state union and selected-CI path so coverage can be checked directly.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "sqd" },
    },
    {
      label: "KQD",
      description:
        "The Krylov extension logic mirrors many of the ideas explained in the KQD reference.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "kqd" },
    },
    {
      label: "Aer Simulator",
      description:
        "A solid local target for sampling experiments before hardware constraints enter the picture.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
  ],
};

const BACKEND_RELATED: Record<BackendTarget, RelatedTopic[]> = {
  statevector: [
    {
      label: "VQE",
      description: "Ideal for deterministic convergence baselines and debugging ansatz choices.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
    {
      label: "QSE",
      description:
        "Useful when you want exact projected-matrix comparisons before moving to sampled paths.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qse" },
    },
  ],
  aer_simulator: [
    {
      label: "Noise Models",
      description:
        "Aer is the page to pair with the local noise presets and backend-derived calibration workflows.",
      to: "/info/noise-models",
    },
    {
      label: "Thermal Relaxation",
      description: "One of the most informative presets when testing depth-heavy circuits locally.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "thermal_relaxation" },
    },
    {
      label: "QFD",
      description:
        "A strong fit for time-evolution experiments where you want configurable simulator methods.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qfd" },
    },
  ],
  ibm_runtime: [
    {
      label: "Backend-Derived Noise",
      description:
        "Use this alongside Runtime when you want calibration-informed local rehearsal before hardware runs.",
      to: "/info/noise-models/$noiseModelId",
      params: { noiseModelId: "backend_derived" },
    },
    {
      label: "KQD",
      description:
        "One of the projected algorithms with a hardware execution path worth comparing against local simulation.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "kqd" },
    },
    {
      label: "SQD",
      description:
        "Sampling-based workflows pair naturally with managed hardware primitives and queue-aware planning.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "sqd" },
    },
  ],
};

const NOISE_RELATED: Record<NoiseModelId, RelatedTopic[]> = {
  depolarizing_cx: [
    {
      label: "Aer Simulator",
      description:
        "This preset runs locally through Aer, where two-qubit gate errors can be stressed quickly.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
    {
      label: "VQE",
      description:
        "Entangling ansatz depth makes VQE a useful benchmark for CX-heavy error studies.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "vqe" },
    },
  ],
  thermal_relaxation: [
    {
      label: "Aer Simulator",
      description:
        "Thermal relaxation is easiest to iterate on locally while comparing methods and shot budgets.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
    {
      label: "QFD",
      description:
        "Time-evolution circuits tend to expose the schedule-dependent nature of relaxation noise.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qfd" },
    },
  ],
  readout_bias: [
    {
      label: "SQD",
      description:
        "Bitstring sampling quality is directly exposed to assignment errors after measurement.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "sqd" },
    },
    {
      label: "QSE",
      description:
        "Projected overlaps can shift when the measured bitstrings are biased at readout time.",
      to: "/info/algorithms/$algorithmId",
      params: { algorithmId: "qse" },
    },
  ],
  backend_derived: [
    {
      label: "IBM Quantum Runtime",
      description:
        "This model is built from IBM calibration data, so the Runtime page explains the target environment behind it.",
      to: "/info/backends/$backendId",
      params: { backendId: "ibm_runtime" },
    },
    {
      label: "Aer Simulator",
      description:
        "The calibration snapshot is still executed locally through Aer once the model has been constructed.",
      to: "/info/backends/$backendId",
      params: { backendId: "aer_simulator" },
    },
  ],
};

export function getAlgorithmRelated(id: RunAlgorithm) {
  return ALGORITHM_RELATED[id];
}

export function getBackendRelated(id: BackendTarget) {
  return BACKEND_RELATED[id];
}

export function getNoiseRelated(id: NoiseModelId) {
  return NOISE_RELATED[id];
}
