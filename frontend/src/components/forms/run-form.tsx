import { useCallback, useEffect, useMemo, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "framer-motion";
import { useForm, type FieldPath, type Resolver, type UseFormReturn } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FormField } from "./form-field";
import { useValidateRunDebounced } from "@/hooks/use-validate-run-debounced";
import { useAllMolecules, useRunConfigMetadata } from "@/hooks";
import { ErrorSummary } from "./run-form/error-summary";
import { FormSection } from "./run-form/form-section";
import { MoleculeSection } from "./run-form/molecule-section";
import { AlgorithmSection, ModeSection } from "./run-form/algorithm-section";
import { BackendSection } from "./run-form/backend-section";
import { EstimateSummary } from "./run-form/estimate-summary";
import { EasyGoalSlider } from "./run-form/easy-goal-slider";
import { VQEPanel } from "./run-form/advanced-panels/vqe-panel";
import { SQDPanel } from "./run-form/advanced-panels/sqd-panel";
import { KQDPanel } from "./run-form/advanced-panels/kqd-panel";
import { QFDPanel } from "./run-form/advanced-panels/qfd-panel";
import { QSEPanel } from "./run-form/advanced-panels/qse-panel";
import { SKQDPanel } from "./run-form/advanced-panels/skqd-panel";
import { forceRefreshBackendCapabilities, getBackendCapabilitiesCached } from "@/api/backends";
import { showErrorToast } from "@/lib/error-handler";
import { isMoleculeCompatible } from "@/lib/molecule-compat";
import { runFormSchema } from "@/lib/run-form-schema";
import type {
  BackendCapability,
  MoleculeResponse,
  RunConfigMetadataResponse,
  SimulationRunFormData,
} from "@/types/run";
import { RunFormProvider } from "./run-form/run-form-context";
import { getRunFormError, isRunFormFieldTouched } from "./run-form/run-form-context-helpers";
import { useFormSectionStatus } from "./run-form/use-form-section-status";
import { initialValues } from "./run-form/constants";
import { flattenErrors } from "./run-form/errors";
import { loadRunFormConfigMetadata } from "./run-form/manual-mode-config";
import { useRunFormSubmit } from "./run-form/use-run-form-submit";
import {
  buildRecommendedAdvancedPatch,
  getChemicalAccuracyTargetOptions,
  goalForChemicalAccuracyTarget,
} from "@/lib/run-form-recommendations";
import type { ChemicalAccuracyTargetOption } from "@/lib/run-form-recommendations";
import type { IbmBackendWarmupProgress } from "@/lib/ibm-profile-events";
import { subscribeToIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";
import {
  backendDefaultsForTarget,
  getSelectableDevices,
  resolveNoiseReference,
} from "./run-form/backend-section-shared";

const DEFAULT_BACKEND_CAPABILITIES: BackendCapability[] = [
  {
    target: "statevector",
    enabled: true,
    available: true,
    supports_noise_profile: false,
    supports_shots: false,
    supports_transpilation_preview: false,
    status: "available",
  },
  {
    target: "aer_simulator",
    enabled: true,
    available: true,
    supports_noise_profile: true,
    supports_shots: true,
    supports_transpilation_preview: true,
    status: "available",
    default_backend: "aer_simulator",
  },
  {
    target: "ibm_runtime",
    enabled: false,
    available: false,
    credential_configured: false,
    credentials_usable: false,
    supports_noise_profile: false,
    supports_shots: true,
    supports_transpilation_preview: true,
    status: "unavailable",
    reason: "Save and activate an encrypted IBM profile in Settings to enable hardware backends.",
  },
];

const EMPTY_MOLECULES: MoleculeResponse[] = [];
const BACKEND_CAPABILITIES_REFRESH_ERROR = "Failed to refresh backend capabilities.";

type RunFormErrorField = FieldPath<SimulationRunFormData>;

function mergeBackendCapabilities(items: BackendCapability[]): BackendCapability[] {
  const defaultTargets = new Set(DEFAULT_BACKEND_CAPABILITIES.map((b) => b.target));
  const merged = DEFAULT_BACKEND_CAPABILITIES.map((fallback) => {
    const item = items.find((candidate) => candidate.target === fallback.target);
    if (item == null) {
      return fallback;
    }

    return {
      ...fallback,
      ...item,
      reason: item.reason ?? null,
    };
  });
  const extras = items.filter((item) => !defaultTargets.has(item.target));
  return [...merged, ...extras];
}

type RunFormProps = Readonly<{
  initialMoleculeId?: string | null;
}>;

type RunFormControlProps = Readonly<{
  submitting: boolean;
  values: SimulationRunFormData;
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>;
  submitAttempted: boolean;
  recommendedSummary: string;
  applyRecommendedSettings: () => void;
  chemicalAccuracyTargetOptions: readonly ChemicalAccuracyTargetOption[];
}>;

type ManualAlgorithmPanelProps = Readonly<{
  algorithm: SimulationRunFormData["algorithm"];
  submitting: boolean;
  configMetadata: RunConfigMetadataResponse | null;
  onResetRecommended: () => void;
}>;

type PresetControlsProps = Readonly<{
  submitting: boolean;
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>;
  submitAttempted: boolean;
}>;

type AdvancedAlgorithmControlsProps = RunFormControlProps &
  Readonly<{
    configMetadata: RunConfigMetadataResponse | null;
    onResetRecommended: () => void;
  }>;

type AlgorithmControlsProps = AdvancedAlgorithmControlsProps &
  Readonly<{
    isAdvanced: boolean;
  }>;

function useRunFormConfigMetadata() {
  return useRunConfigMetadata(loadRunFormConfigMetadata).data ?? null;
}

function initialBackendCapabilities(): BackendCapability[] {
  const cachedCapabilities = getBackendCapabilitiesCached();
  return cachedCapabilities
    ? mergeBackendCapabilities(cachedCapabilities.backends)
    : DEFAULT_BACKEND_CAPABILITIES;
}

function syncBackendCapabilitiesFromCache(
  applyCapabilities: (items: BackendCapability[]) => void,
  setCapabilitiesError: (value: string | null) => void,
  profileId?: string | null,
): boolean {
  const cached = getBackendCapabilitiesCached(profileId ?? undefined);
  if (cached == null) {
    return false;
  }
  applyCapabilities(cached.backends);
  setCapabilitiesError(null);
  return true;
}

function applyBackendCapabilityRefreshDetail(
  detail: {
    activeProfileId?: string | null;
    backendCapabilitiesRefresh?: "started" | "progress" | "completed" | "failed";
    backendWarmupProgress?: IbmBackendWarmupProgress | null;
  },
  syncFromCache: (profileId?: string | null) => boolean,
  setActiveProfileId: (value: string | null) => void,
  setCapabilitiesLoading: (value: boolean) => void,
  setCapabilitiesRefreshing: (value: boolean) => void,
  setCapabilitiesError: (value: string | null) => void,
  setWarmupProgress: (value: IbmBackendWarmupProgress | null) => void,
): void {
  if (detail.activeProfileId !== undefined) {
    setActiveProfileId(detail.activeProfileId ?? null);
  }

  if (
    detail.backendCapabilitiesRefresh === "started" ||
    detail.backendCapabilitiesRefresh === "progress"
  ) {
    const synced = syncFromCache(detail.activeProfileId ?? undefined);
    setCapabilitiesLoading(!synced);
    setCapabilitiesRefreshing(true);
    setCapabilitiesError(null);
    setWarmupProgress(detail.backendWarmupProgress ?? null);
    return;
  }

  const synced = syncFromCache(detail.activeProfileId ?? undefined);
  if (!synced && detail.backendCapabilitiesRefresh === "failed") {
    setCapabilitiesError(BACKEND_CAPABILITIES_REFRESH_ERROR);
  } else if (synced) {
    setCapabilitiesError(null);
  }

  setCapabilitiesLoading(false);
  setCapabilitiesRefreshing(false);
  setWarmupProgress(detail.backendWarmupProgress ?? null);
}

function useBackendCapabilitiesState() {
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [backendCapabilities, setBackendCapabilities] = useState(initialBackendCapabilities);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(
    () => getBackendCapabilitiesCached() == null,
  );
  const [capabilitiesRefreshing, setCapabilitiesRefreshing] = useState(false);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const [backendWarmupProgress, setBackendWarmupProgress] =
    useState<IbmBackendWarmupProgress | null>(null);

  const applyCapabilities = useCallback((items: BackendCapability[]) => {
    setBackendCapabilities(mergeBackendCapabilities(items));
  }, []);

  const syncCapabilitiesFromCache = useCallback(
    (profileId?: string | null) => {
      return syncBackendCapabilitiesFromCache(
        applyCapabilities,
        setCapabilitiesError,
        profileId ?? undefined,
      );
    },
    [applyCapabilities],
  );

  useEffect(() => {
    if (syncCapabilitiesFromCache()) {
      setCapabilitiesLoading(false);
      return;
    }

    let cancelled = false;
    setCapabilitiesLoading(true);
    setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });

    void forceRefreshBackendCapabilities(activeProfileId ?? undefined)
      .then((data) => {
        if (cancelled) {
          return;
        }
        applyCapabilities(data.backends);
        setCapabilitiesError(null);
        setBackendWarmupProgress({ loadedProfiles: 1, totalProfiles: 1 });
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setCapabilitiesError(BACKEND_CAPABILITIES_REFRESH_ERROR);
        setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
      })
      .finally(() => {
        if (cancelled) {
          return;
        }
        setCapabilitiesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeProfileId, applyCapabilities, syncCapabilitiesFromCache]);

  const refreshCapabilities = useCallback(async () => {
    setCapabilitiesRefreshing(true);
    setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
    try {
      const data = await forceRefreshBackendCapabilities(activeProfileId ?? undefined);
      applyCapabilities(data.backends);
      setCapabilitiesError(null);
      setBackendWarmupProgress({ loadedProfiles: 1, totalProfiles: 1 });
    } catch {
      setCapabilitiesError(BACKEND_CAPABILITIES_REFRESH_ERROR);
      setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
    } finally {
      setCapabilitiesRefreshing(false);
    }
  }, [activeProfileId, applyCapabilities]);

  useEffect(() => {
    return subscribeToIbmCredentialProfilesChanged((detail) => {
      applyBackendCapabilityRefreshDetail(
        detail,
        syncCapabilitiesFromCache,
        setActiveProfileId,
        setCapabilitiesLoading,
        setCapabilitiesRefreshing,
        setCapabilitiesError,
        setBackendWarmupProgress,
      );
    });
  }, [syncCapabilitiesFromCache]);

  return {
    backendCapabilities,
    capabilitiesLoading,
    capabilitiesRefreshing,
    capabilitiesError,
    backendWarmupProgress,
    refreshCapabilities,
  };
}

function buildIncompatibleMoleculeIds(molecules: MoleculeResponse[]) {
  const map = new Map<string, string>();
  for (const molecule of molecules) {
    const result = isMoleculeCompatible(molecule);
    if (result.ok) {
      continue;
    }
    map.set(molecule.id, result.reason);
  }
  return map;
}

function getVisibleRunFormError(
  form: UseFormReturn<SimulationRunFormData, unknown, SimulationRunFormData>,
  submitAttempted: boolean,
  field: RunFormErrorField,
) {
  if (submitAttempted || isRunFormFieldTouched(form, field)) {
    return getRunFormError(form, field);
  }

  return undefined;
}

function getAlgorithmSectionTitle(isAdvanced: boolean) {
  return isAdvanced ? "Algorithm & Manual Controls" : "Algorithm & Guided Preset";
}

function getAlgorithmSectionDescription(isAdvanced: boolean) {
  return isAdvanced
    ? "Choose the algorithm and tune its primary + expert controls"
    : "Choose the algorithm and an accuracy/runtime target";
}

function hasRequiredRunSelections({
  selectedMolecule,
  incompatibleMoleculeIds,
  values,
}: {
  selectedMolecule: MoleculeResponse | null;
  incompatibleMoleculeIds: Map<string, string>;
  values: SimulationRunFormData;
}) {
  const hasManualIbmBackendName =
    values.backend_target !== "ibm_runtime" ||
    values.backend_options.selection_policy !== "manual" ||
    Boolean(values.backend_options.backend_name?.trim());

  return (
    selectedMolecule !== null &&
    !incompatibleMoleculeIds.has(selectedMolecule.id) &&
    values.mode !== null &&
    values.backend_target !== null &&
    values.algorithm !== null &&
    hasManualIbmBackendName
  );
}

function ChemicalAccuracyTargetPanel({
  submitting,
  values,
  form,
  submitAttempted,
  recommendedSummary,
  applyRecommendedSettings,
  chemicalAccuracyTargetOptions,
}: RunFormControlProps) {
  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4">
      <div className="space-y-4">
        <FormField
          label="Chemical Accuracy Target (Ha)"
          htmlFor="chemical-accuracy-target-input"
          error={getVisibleRunFormError(form, submitAttempted, "chemical_accuracy_target_ha")}
          help={{
            short: "Manual-mode helper used to map your target into a recommended preset family.",
            anchor: "chemical_accuracy_target_ha",
          }}
        >
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {chemicalAccuracyTargetOptions.map((option) => (
                <Button
                  key={option.goal}
                  type="button"
                  variant={
                    values.chemical_accuracy_target_ha === option.thresholdHa
                      ? "default"
                      : "outline"
                  }
                  size="sm"
                  disabled={submitting}
                  onClick={() =>
                    form.setValue("chemical_accuracy_target_ha", option.thresholdHa, {
                      shouldDirty: true,
                      shouldTouch: true,
                      shouldValidate: true,
                    })
                  }
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <Input
              id="chemical-accuracy-target-input"
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={values.chemical_accuracy_target_ha ?? ""}
              onChange={(event) =>
                form.setValue(
                  "chemical_accuracy_target_ha",
                  event.target.value === "" ? null : Number(event.target.value),
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              onBlur={() =>
                form.setValue("chemical_accuracy_target_ha", values.chemical_accuracy_target_ha, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              aria-invalid={!!getRunFormError(form, "chemical_accuracy_target_ha")}
              disabled={submitting}
            />
          </div>
        </FormField>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">{recommendedSummary}</p>
          <Button
            type="button"
            variant="outline"
            onClick={applyRecommendedSettings}
            disabled={submitting || values.algorithm == null}
          >
            Apply recommended settings
          </Button>
        </div>
      </div>
    </div>
  );
}

function ManualAlgorithmPanel({
  algorithm,
  submitting,
  configMetadata,
  onResetRecommended,
}: ManualAlgorithmPanelProps) {
  if (algorithm === null) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
        Pick an algorithm above to unlock its manual controls.
      </div>
    );
  }

  switch (algorithm) {
    case "vqe":
      return (
        <VQEPanel
          disabled={submitting}
          metadata={configMetadata}
          onResetRecommended={onResetRecommended}
        />
      );
    case "sqd":
      return <SQDPanel disabled={submitting} onResetRecommended={onResetRecommended} />;
    case "kqd":
      return <KQDPanel disabled={submitting} onResetRecommended={onResetRecommended} />;
    case "qfd":
      return <QFDPanel disabled={submitting} onResetRecommended={onResetRecommended} />;
    case "qse":
      return (
        <QSEPanel
          disabled={submitting}
          metadata={configMetadata}
          onResetRecommended={onResetRecommended}
        />
      );
    case "skqd":
      return <SKQDPanel disabled={submitting} onResetRecommended={onResetRecommended} />;
  }
}

function PresetControls({ submitting, form, submitAttempted }: PresetControlsProps) {
  return (
    <FormField
      label="Preset"
      htmlFor="easy-goal-slider"
      required
      error={getVisibleRunFormError(form, submitAttempted, "easy_options.goal")}
      help={{
        short: "Each preset maps to concrete values for the selected algorithm.",
        anchor: "goal",
      }}
    >
      <EasyGoalSlider id="easy-goal-slider" disabled={submitting} />
    </FormField>
  );
}

function AdvancedAlgorithmControls({
  submitting,
  values,
  form,
  submitAttempted,
  recommendedSummary,
  applyRecommendedSettings,
  chemicalAccuracyTargetOptions,
  configMetadata,
  onResetRecommended,
}: AdvancedAlgorithmControlsProps) {
  return (
    <>
      <ChemicalAccuracyTargetPanel
        submitting={submitting}
        values={values}
        form={form}
        submitAttempted={submitAttempted}
        recommendedSummary={recommendedSummary}
        applyRecommendedSettings={applyRecommendedSettings}
        chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
      />

      <AnimatePresence mode="wait">
        <motion.div
          key={values.algorithm}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <ManualAlgorithmPanel
            algorithm={values.algorithm}
            submitting={submitting}
            configMetadata={configMetadata}
            onResetRecommended={onResetRecommended}
          />
        </motion.div>
      </AnimatePresence>
    </>
  );
}

function AlgorithmControls({
  isAdvanced,
  submitting,
  values,
  form,
  submitAttempted,
  recommendedSummary,
  applyRecommendedSettings,
  chemicalAccuracyTargetOptions,
  configMetadata,
  onResetRecommended,
}: AlgorithmControlsProps) {
  if (isAdvanced) {
    return (
      <AdvancedAlgorithmControls
        submitting={submitting}
        values={values}
        form={form}
        submitAttempted={submitAttempted}
        recommendedSummary={recommendedSummary}
        applyRecommendedSettings={applyRecommendedSettings}
        chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
        configMetadata={configMetadata}
        onResetRecommended={onResetRecommended}
      />
    );
  }

  return <PresetControls submitting={submitting} form={form} submitAttempted={submitAttempted} />;
}

function RunSubmitButton({
  submitting,
  disabled,
}: Readonly<{ submitting: boolean; disabled: boolean }>) {
  return (
    <Button type="submit" disabled={disabled} className="w-full">
      {submitting ? (
        <>
          <Spinner className="mr-2" /> Creating run…
        </>
      ) : (
        "Create Run"
      )}
    </Button>
  );
}

export function RunForm({ initialMoleculeId = null }: RunFormProps) {
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const configMetadata = useRunFormConfigMetadata();
  const {
    backendCapabilities,
    capabilitiesLoading,
    capabilitiesRefreshing,
    capabilitiesError,
    backendWarmupProgress,
    refreshCapabilities,
  } = useBackendCapabilitiesState();
  const moleculesQuery = useAllMolecules();

  const defaultValues = useMemo(
    () => ({
      ...initialValues,
      molecule_id: initialMoleculeId,
    }),
    [initialMoleculeId],
  );

  const form = useForm<SimulationRunFormData, unknown, SimulationRunFormData>({
    defaultValues,
    mode: "onChange",
    resolver: zodResolver(runFormSchema) as Resolver<
      SimulationRunFormData,
      unknown,
      SimulationRunFormData
    >,
  });
  const values = form.watch();
  const errors = useMemo(() => flattenErrors(form.formState.errors), [form.formState.errors]);

  const { estimate, loading: validating } = useValidateRunDebounced(values, form.formState.isValid);
  const {
    handleSubmit,
    submitting,
    ibmConfirmationOpen,
    setIbmConfirmationOpen,
    confirmIbmSubmit,
    pendingIbmSubmit,
  } = useRunFormSubmit({ form, setSubmitAttempted });

  useEffect(() => {
    if (moleculesQuery.error == null) return;
    showErrorToast(moleculesQuery.error, {
      title: "Error",
      fallbackDescription: "Failed to load molecules",
    });
  }, [moleculesQuery.error]);

  const molecules = moleculesQuery.data ?? EMPTY_MOLECULES;
  const loadingMolecules = moleculesQuery.isLoading;

  const selectedMolecule = useMemo(
    () => molecules.find((m) => m.id === values.molecule_id) ?? null,
    [molecules, values.molecule_id],
  );
  const chemicalAccuracyTargetOptions = useMemo(
    () => getChemicalAccuracyTargetOptions(configMetadata?.easy_goal_presets),
    [configMetadata?.easy_goal_presets],
  );
  const recommendedGoal = goalForChemicalAccuracyTarget(
    values.chemical_accuracy_target_ha,
    chemicalAccuracyTargetOptions,
  );
  const recommendedGoalLabel =
    chemicalAccuracyTargetOptions.find((option) => option.goal === recommendedGoal)?.label ??
    "1.6 mHa";
  const recommendedSummary = `${recommendedGoalLabel} target maps to the ${recommendedGoal.replace("_", " ")} preset family.`;

  useEffect(() => {
    if (values.backend_target !== "ibm_runtime") {
      return;
    }

    const capability = backendCapabilities.find((item) => item.target === "ibm_runtime") ?? null;
    const selectableDevices = getSelectableDevices("ibm_runtime", capability);
    if (
      values.backend_options.selection_policy !== "manual" ||
      selectableDevices.length === 0 ||
      selectableDevices.some((device) => device.name === values.backend_options.backend_name)
    ) {
      return;
    }

    const nextOptions = backendDefaultsForTarget(
      "ibm_runtime",
      values.backend_options,
      capability ?? undefined,
    );
    form.setValue("backend_options", nextOptions, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    });

    if (values.noise_profile?.source === "backend_derived") {
      form.setValue(
        "noise_profile",
        {
          ...values.noise_profile,
          reference_backend: resolveNoiseReference(
            nextOptions,
            capability,
            "ibm_runtime",
            selectableDevices,
          ),
        },
        {
          shouldDirty: true,
          shouldTouch: true,
          shouldValidate: true,
        },
      );
    }
  }, [
    backendCapabilities,
    form,
    values.backend_options,
    values.backend_target,
    values.noise_profile,
  ]);

  const applyRecommendedSettings = useCallback(() => {
    if (values.algorithm == null) {
      return;
    }

    const patch = buildRecommendedAdvancedPatch(
      values.algorithm,
      recommendedGoal,
      selectedMolecule?.active_space,
      configMetadata,
    );
    form.setValue("easy_options.goal", recommendedGoal, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    });
    form.setValue(patch.field, patch.value, {
      shouldDirty: true,
      shouldTouch: true,
      shouldValidate: true,
    });
  }, [configMetadata, form, recommendedGoal, selectedMolecule?.active_space, values.algorithm]);

  const resetRecommendedForAlgorithm = useCallback(() => {
    applyRecommendedSettings();
  }, [applyRecommendedSettings]);

  const incompatibleMoleculeIds = useMemo(
    () => buildIncompatibleMoleculeIds(molecules),
    [molecules],
  );

  const isAdvanced = values.mode === "advanced";
  const sectionStatus = useFormSectionStatus({
    form,
    values,
    errors,
    submitAttempted,
    incompatibleMoleculeIds,
  });
  const hasRequiredSelections = hasRequiredRunSelections({
    selectedMolecule,
    incompatibleMoleculeIds,
    values,
  });

  return (
    <RunFormProvider form={form}>
      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <CardHeader>
            <CardTitle>Create Simulation Run</CardTitle>
            <CardDescription>Configure an algorithm-aware simulation run</CardDescription>
          </CardHeader>

          <CardContent className="flex flex-col gap-8">
            {submitAttempted && Object.keys(errors).length > 0 && <ErrorSummary errors={errors} />}

            <FormSection
              index={1}
              title="Molecule"
              description="Select the molecule to simulate"
              status={sectionStatus(1)}
            >
              <MoleculeSection
                molecules={molecules}
                loading={loadingMolecules}
                value={values.molecule_id}
                onChange={(val) => {
                  form.setValue("molecule_id", val, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  });
                }}
                basisSetOverride={values.basis_set_override}
                onBasisSetChange={(v) =>
                  form.setValue("basis_set_override", v, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
                disabled={submitting}
                incompatibleIds={incompatibleMoleculeIds}
                error={getVisibleRunFormError(form, submitAttempted, "molecule_id")}
              />
            </FormSection>

            <FormSection
              index={2}
              title="Mode"
              description="Choose guided presets or manual parameters"
              status={sectionStatus(2)}
            >
              <ModeSection disabled={submitting} />
            </FormSection>

            <FormSection
              index={3}
              title="Backend"
              description="Simulation backend target and execution options"
              status={sectionStatus(3)}
            >
              <BackendSection
                value={values.backend_target}
                mode={values.mode}
                onChange={(v) => {
                  form.setValue("backend_target", v, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  });
                }}
                backendOptions={values.backend_options}
                onBackendOptionsChange={(next) =>
                  form.setValue("backend_options", next, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  })
                }
                noiseProfile={values.noise_profile}
                onNoiseProfileChange={(next) =>
                  form.setValue("noise_profile", next, {
                    shouldDirty: true,
                    shouldTouch: true,
                    shouldValidate: true,
                  })
                }
                capabilities={backendCapabilities}
                capabilitiesLoading={capabilitiesLoading}
                capabilitiesError={capabilitiesError}
                capabilitiesRefreshing={capabilitiesRefreshing}
                capabilitiesWarmupProgress={backendWarmupProgress}
                onRefreshCapabilities={refreshCapabilities}
                disabled={submitting}
                error={getVisibleRunFormError(form, submitAttempted, "backend_target")}
              />
            </FormSection>

            <FormSection
              index={4}
              title={getAlgorithmSectionTitle(isAdvanced)}
              description={getAlgorithmSectionDescription(isAdvanced)}
              status={sectionStatus(4)}
            >
              <div className="flex flex-col gap-6">
                <AlgorithmSection disabled={submitting} />
                <AlgorithmControls
                  isAdvanced={isAdvanced}
                  submitting={submitting}
                  values={values}
                  form={form}
                  submitAttempted={submitAttempted}
                  recommendedSummary={recommendedSummary}
                  applyRecommendedSettings={applyRecommendedSettings}
                  chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
                  configMetadata={configMetadata}
                  onResetRecommended={resetRecommendedForAlgorithm}
                />
              </div>
            </FormSection>

            <EstimateSummary estimate={estimate} loading={validating} />
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <RunSubmitButton
              submitting={submitting}
              disabled={submitting || !hasRequiredSelections}
            />
          </CardFooter>
        </form>
      </Card>
      <ConfirmDialog
        open={ibmConfirmationOpen}
        onOpenChange={setIbmConfirmationOpen}
        title="Submit to IBM Quantum?"
        description={ibmConfirmationDescription(pendingIbmSubmit ?? values)}
        confirmText="Submit to IBM Runtime"
        cancelText="Review settings"
        onConfirm={confirmIbmSubmit}
        loading={submitting}
      />
    </RunFormProvider>
  );
}

function ibmConfirmationDescription(values: SimulationRunFormData): string {
  const options = values.backend_options;
  const backend = getIbmConfirmationBackend(options);
  const algorithm = values.algorithm?.toUpperCase() ?? "the selected algorithm";
  return `${algorithm} will be submitted to IBM Runtime on ${backend} with ${options.shots} shots. This can consume IBM Quantum quota and queue time.`;
}

function getIbmConfirmationBackend(options: SimulationRunFormData["backend_options"]): string {
  if (options.selection_policy === "manual") {
    return options.backend_name ?? "the selected IBM backend";
  }

  return options.selection_policy.replace("_", " ");
}
