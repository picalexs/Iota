import type { UseFormReturn } from "react-hook-form";

import type { RunAlgorithm, SimulationRunFormData } from "@/types/run";
import { isRunFormFieldTouched } from "./run-form-context-helpers";

export type RunFormSection = 1 | 2 | 3 | 4;
export type RunFormSectionStatus = "ok" | "error" | undefined;

interface UseFormSectionStatusOptions {
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>;
  values: SimulationRunFormData;
  errors: Record<string, string>;
  submitAttempted: boolean;
  incompatibleMoleculeIds: Map<string, string>;
}

const advancedPrefixByAlgorithm: Record<RunAlgorithm, string> = {
  vqe: "advanced_vqe.",
  sqd: "advanced_sqd.",
  skqd: "advanced_skqd.",
  kqd: "advanced_kqd.",
  qfd: "advanced_qfd.",
  qse: "advanced_qse.",
};

function shouldShowError(
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>,
  submitAttempted: boolean,
  field: keyof SimulationRunFormData | "easy_options.goal" | "backend_target",
): boolean {
  return submitAttempted || isRunFormFieldTouched(form, field);
}

function hasAnyErrorWithPrefixes(errors: Record<string, string>, prefixes: string[]): boolean {
  return Object.keys(errors).some((key) => prefixes.some((prefix) => key.startsWith(prefix)));
}

type RawSectionStatusContext = UseFormSectionStatusOptions & {
  activeAdvancedPrefix: string | null;
};

type RawSectionStatusResolver = (context: RawSectionStatusContext) => RunFormSectionStatus;

const backendErrorPrefixes = ["backend_target", "backend_options.", "noise_profile"];

function moleculeSectionStatus({
  form,
  values,
  errors,
  submitAttempted,
  incompatibleMoleculeIds,
}: RawSectionStatusContext): RunFormSectionStatus {
  if (shouldShowError(form, submitAttempted, "molecule_id") && errors.molecule_id) {
    return "error";
  }

  const selectedCompatibleMolecule =
    values.molecule_id != null && !incompatibleMoleculeIds.has(values.molecule_id);
  return selectedCompatibleMolecule && !errors.molecule_id ? "ok" : undefined;
}

function modeSectionStatus({
  form,
  values,
  errors,
  submitAttempted,
}: RawSectionStatusContext): RunFormSectionStatus {
  if (shouldShowError(form, submitAttempted, "mode") && errors.mode) {
    return "error";
  }

  return values.mode && !errors.mode ? "ok" : undefined;
}

function backendSectionStatus({
  form,
  values,
  errors,
  submitAttempted,
}: RawSectionStatusContext): RunFormSectionStatus {
  const hasBackendErrors = hasAnyErrorWithPrefixes(errors, backendErrorPrefixes);
  if (shouldShowError(form, submitAttempted, "backend_target") && hasBackendErrors) {
    return "error";
  }

  return values.backend_target && !hasBackendErrors ? "ok" : undefined;
}

function easyAlgorithmSectionStatus({
  form,
  values,
  errors,
  submitAttempted,
}: RawSectionStatusContext): RunFormSectionStatus {
  if (shouldShowError(form, submitAttempted, "easy_options.goal") && errors["easy_options.goal"]) {
    return "error";
  }

  return values.algorithm && values.easy_options.goal ? "ok" : undefined;
}

function advancedAlgorithmSectionStatus({
  errors,
  activeAdvancedPrefix,
}: RawSectionStatusContext): RunFormSectionStatus {
  if (activeAdvancedPrefix == null) {
    return undefined;
  }

  return hasAnyErrorWithPrefixes(errors, [activeAdvancedPrefix]) ? "error" : "ok";
}

function algorithmSectionStatus(context: RawSectionStatusContext): RunFormSectionStatus {
  const { form, values, errors, submitAttempted } = context;
  if (shouldShowError(form, submitAttempted, "algorithm") && errors.algorithm) {
    return "error";
  }

  return values.mode === "easy"
    ? easyAlgorithmSectionStatus(context)
    : advancedAlgorithmSectionStatus(context);
}

const rawSectionStatusBySection: Record<RunFormSection, RawSectionStatusResolver> = {
  1: moleculeSectionStatus,
  2: modeSectionStatus,
  3: backendSectionStatus,
  4: algorithmSectionStatus,
};

function rawSectionStatus(section: RunFormSection, context: RawSectionStatusContext) {
  return rawSectionStatusBySection[section](context);
}

function previousSectionsAreOk(section: RunFormSection, context: RawSectionStatusContext): boolean {
  for (let currentSection = 1; currentSection < section; currentSection += 1) {
    if (rawSectionStatus(currentSection as RunFormSection, context) !== "ok") {
      return false;
    }
  }

  return true;
}

export function useFormSectionStatus({
  form,
  values,
  errors,
  submitAttempted,
  incompatibleMoleculeIds,
}: UseFormSectionStatusOptions) {
  const activeAdvancedPrefix = values.algorithm
    ? advancedPrefixByAlgorithm[values.algorithm]
    : null;
  const context = {
    form,
    values,
    errors,
    submitAttempted,
    incompatibleMoleculeIds,
    activeAdvancedPrefix,
  };

  const sectionStatus = (section: RunFormSection): RunFormSectionStatus => {
    const currentStatus = rawSectionStatus(section, context);
    if (currentStatus !== "ok") {
      return currentStatus;
    }

    return previousSectionsAreOk(section, context) ? "ok" : undefined;
  };

  return sectionStatus;
}
