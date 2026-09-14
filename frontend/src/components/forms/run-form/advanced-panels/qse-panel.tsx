import { Minus, Plus } from "lucide-react";

import { FormField } from "@/components/forms/form-field";
import { useRunFormContext } from "@/components/forms/run-form/run-form-context";
import {
  getRunFormError,
  isRunFormFieldTouched,
  type RunFormMethods,
} from "@/components/forms/run-form/run-form-context-helpers";
import { ExpertDisclosure } from "./expert-disclosure";
import { VqeSelectorFields } from "./vqe-selector-fields";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumberSlider } from "@/components/ui/number-slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { RUN_CONSTRAINTS } from "@/lib/run-form-constraints";
import type { RunConfigMetadataResponse } from "@/types/run";

interface QSEPanelProps {
  disabled?: boolean;
  metadata: RunConfigMetadataResponse | null;
  onResetRecommended?: () => void;
}

type QSEReferenceMethod = "hf" | "vqe" | "provided_state" | "provided_sector";
type RunFormFieldPath = Parameters<typeof getRunFormError>[1];

function getTouchedRunFormError(form: RunFormMethods, path: RunFormFieldPath): string | undefined {
  return isRunFormFieldTouched(form, path) ? getRunFormError(form, path) : undefined;
}

export function QSEPanel({ disabled = false, metadata, onResetRecommended }: QSEPanelProps) {
  const form = useRunFormContext();
  const values = form.watch("advanced_qse");
  const providedSectorRowsPath = "advanced_qse.provided_sector_rows" as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-card px-4 py-3 dark:bg-muted/20">
        <div>
          <p className="text-sm font-semibold">Primary controls</p>
          <p className="text-xs text-muted-foreground">
            Choose the QSE reference flow and tune the projected-subspace solve.
          </p>
        </div>
        {onResetRecommended ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onResetRecommended}
            disabled={disabled}
          >
            Reset to recommended
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FormField
          label="Reference Method"
          htmlFor="advanced-qse-reference-method-select"
          required
          error={getTouchedRunFormError(form, "advanced_qse.reference_method")}
          help={{
            short: "Select the reference state construction that seeds the QSE expansion.",
            anchor: "reference_method",
            href: "/info/components/reference-states",
          }}
        >
          <Select
            value={values.reference_method}
            onValueChange={(value) =>
              form.setValue("advanced_qse.reference_method", value as QSEReferenceMethod, {
                shouldDirty: true,
                shouldTouch: true,
                shouldValidate: true,
              })
            }
          >
            <SelectTrigger
              id="advanced-qse-reference-method-select"
              disabled={disabled}
              aria-invalid={!!getRunFormError(form, "advanced_qse.reference_method")}
            >
              <SelectValue placeholder="Select reference method" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hf">HF reference</SelectItem>
              <SelectItem value="vqe">VQE reference</SelectItem>
              <SelectItem value="provided_state">Provided dense state</SelectItem>
              <SelectItem value="provided_sector">Provided determinant sector</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField
          label="Excitation Level"
          htmlFor="advanced-qse-excitation-level-select"
          required
          error={getTouchedRunFormError(form, "advanced_qse.excitation_level")}
          help={{
            short: "Control how many excitations are included in the QSE operator pool.",
            anchor: "excitation_level",
          }}
        >
          <Select
            value={values.excitation_level}
            onValueChange={(value) =>
              form.setValue(
                "advanced_qse.excitation_level",
                value as "singles" | "singles_doubles",
                {
                  shouldDirty: true,
                  shouldTouch: true,
                  shouldValidate: true,
                },
              )
            }
          >
            <SelectTrigger
              id="advanced-qse-excitation-level-select"
              disabled={disabled}
              aria-invalid={!!getRunFormError(form, "advanced_qse.excitation_level")}
            >
              <SelectValue placeholder="Select excitation level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="singles">Singles</SelectItem>
              <SelectItem value="singles_doubles">Singles + doubles</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <FormField
          label="Max Subspace Dimension"
          htmlFor="advanced-qse-max-subspace-dim-input"
          required
          error={getTouchedRunFormError(form, "advanced_qse.max_subspace_dim")}
          help={{
            short: "Cap the projected QSE basis size.",
            anchor: "max_subspace_dim",
          }}
        >
          <NumberSlider
            id="advanced-qse-max-subspace-dim-input"
            value={values.max_subspace_dim}
            min={RUN_CONSTRAINTS.qse.max_subspace_dim.min}
            max={RUN_CONSTRAINTS.qse.max_subspace_dim.max}
            step={1}
            onChange={(next) =>
              form.setValue("advanced_qse.max_subspace_dim", next, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue("advanced_qse.max_subspace_dim", values.max_subspace_dim, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>

        <FormField
          label="Residual Tolerance"
          htmlFor="advanced-qse-residual-tolerance-input"
          required
          error={getTouchedRunFormError(form, "advanced_qse.residual_tolerance")}
          help={{
            short: "Stopping threshold for the projected solve.",
            anchor: "residual_tolerance",
          }}
        >
          <Input
            id="advanced-qse-residual-tolerance-input"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            value={values.residual_tolerance ?? ""}
            onChange={(event) =>
              form.setValue(
                "advanced_qse.residual_tolerance",
                event.target.value === "" ? null : Number(event.target.value),
                {
                  shouldDirty: true,
                  shouldValidate: true,
                },
              )
            }
            onBlur={() =>
              form.setValue("advanced_qse.residual_tolerance", values.residual_tolerance, {
                shouldTouch: true,
                shouldValidate: true,
              })
            }
            disabled={disabled}
          />
        </FormField>
      </div>

      {values.reference_method === "vqe" ? (
        <div className="grid grid-cols-1 gap-4 rounded-xl border border-border/70 p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <p className="text-sm font-semibold">Reference VQE</p>
            <p className="text-xs text-muted-foreground">
              Configure the VQE solve used to prepare the QSE reference state.
            </p>
          </div>
          <VqeSelectorFields
            ansatzPath="advanced_qse.vqe_reference_ansatz_name"
            optimizerPath="advanced_qse.vqe_reference_optimizer_name"
            ansatzValue={values.vqe_reference_ansatz_name}
            optimizerValue={values.vqe_reference_optimizer_name}
            metadata={metadata}
            disabled={disabled}
            ansatzLabel="Reference Ansatz"
            optimizerLabel="Reference Optimizer"
            ansatzHelpAnchor="vqe_reference_ansatz_name"
            optimizerHelpAnchor="vqe_reference_optimizer_name"
          />
          <FormField
            label="Reference VQE Iterations"
            htmlFor="advanced-qse-vqe-reference-max-iterations-input"
            required
            error={getTouchedRunFormError(form, "advanced_qse.vqe_reference_max_iterations")}
            help={{
              short: "Optimization budget used to build the QSE reference state.",
              anchor: "vqe_reference_max_iterations",
            }}
          >
            <NumberSlider
              id="advanced-qse-vqe-reference-max-iterations-input"
              value={values.vqe_reference_max_iterations}
              min={RUN_CONSTRAINTS.qse.vqe_reference_max_iterations.min}
              max={RUN_CONSTRAINTS.qse.vqe_reference_max_iterations.max}
              step={1}
              onChange={(next) =>
                form.setValue("advanced_qse.vqe_reference_max_iterations", next, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue(
                  "advanced_qse.vqe_reference_max_iterations",
                  values.vqe_reference_max_iterations,
                  {
                    shouldTouch: true,
                    shouldValidate: true,
                  },
                )
              }
              disabled={disabled}
            />
          </FormField>
          <FormField
            label="Reference VQE Depth"
            htmlFor="advanced-qse-vqe-reference-reps-input"
            required
            error={getTouchedRunFormError(form, "advanced_qse.vqe_reference_reps")}
            help={{
              short: "Ansatz depth for the reference VQE solve.",
              anchor: "vqe_reference_reps",
            }}
          >
            <NumberSlider
              id="advanced-qse-vqe-reference-reps-input"
              value={values.vqe_reference_reps}
              min={RUN_CONSTRAINTS.qse.vqe_reference_reps.min}
              max={RUN_CONSTRAINTS.qse.vqe_reference_reps.max}
              step={1}
              onChange={(next) =>
                form.setValue("advanced_qse.vqe_reference_reps", next, {
                  shouldDirty: true,
                  shouldValidate: true,
                })
              }
              onBlur={() =>
                form.setValue("advanced_qse.vqe_reference_reps", values.vqe_reference_reps, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>
        </div>
      ) : null}

      {values.reference_method === "provided_state" ? (
        <FormField
          label="Provided State Vector"
          htmlFor="advanced-qse-provided-state-text"
          required
          error={getTouchedRunFormError(form, "advanced_qse.provided_state_vector_text")}
          help={{
            short: "Enter a JSON array of numbers or { real, imag } amplitudes.",
            anchor: "provided_state_vector",
            href: "/info/components/reference-states",
          }}
        >
          <Textarea
            id="advanced-qse-provided-state-text"
            value={values.provided_state_vector_text}
            onChange={(event) =>
              form.setValue("advanced_qse.provided_state_vector_text", event.target.value, {
                shouldDirty: true,
                shouldValidate: true,
              })
            }
            onBlur={() =>
              form.setValue(
                "advanced_qse.provided_state_vector_text",
                values.provided_state_vector_text,
                {
                  shouldTouch: true,
                  shouldValidate: true,
                },
              )
            }
            placeholder='[1, {"real": 0, "imag": 0}]'
            disabled={disabled}
          />
        </FormField>
      ) : null}

      {values.reference_method === "provided_sector" ? (
        <div className="space-y-3 rounded-xl border border-border/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">Provided determinant amplitudes</p>
              <p className="text-xs text-muted-foreground">
                Supply a sparse fixed-particle-sector reference as bitstrings plus complex
                amplitudes.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                form.setValue(
                  "advanced_qse.provided_sector_rows",
                  [...values.provided_sector_rows, { bitstring: "", real: "0", imag: "0" }],
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              disabled={disabled}
            >
              <Plus className="size-4" />
              Add row
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bitstring</TableHead>
                <TableHead>Real</TableHead>
                <TableHead>Imag</TableHead>
                <TableHead className="w-16">Row</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {values.provided_sector_rows.map((row, index) => (
                <TableRow key={`${row.bitstring || "sector-row"}-${row.real}-${row.imag}`}>
                  <TableCell>
                    <Input
                      value={row.bitstring}
                      onChange={(event) => {
                        const next = [...values.provided_sector_rows];
                        next[index] = { ...row, bitstring: event.target.value };
                        form.setValue("advanced_qse.provided_sector_rows", next, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }}
                      disabled={disabled}
                      placeholder="0101"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={row.real}
                      onChange={(event) => {
                        const next = [...values.provided_sector_rows];
                        next[index] = { ...row, real: event.target.value };
                        form.setValue("advanced_qse.provided_sector_rows", next, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }}
                      disabled={disabled}
                      placeholder="1.0"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={row.imag}
                      onChange={(event) => {
                        const next = [...values.provided_sector_rows];
                        next[index] = { ...row, imag: event.target.value };
                        form.setValue("advanced_qse.provided_sector_rows", next, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }}
                      disabled={disabled}
                      placeholder="0.0"
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => {
                        const next =
                          values.provided_sector_rows.length > 1
                            ? values.provided_sector_rows.filter(
                                (_, rowIndex) => rowIndex !== index,
                              )
                            : [{ bitstring: "", real: "0", imag: "0" }];
                        form.setValue("advanced_qse.provided_sector_rows", next, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }}
                      disabled={disabled}
                      aria-label={`Remove determinant row ${index + 1}`}
                    >
                      <Minus className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {getRunFormError(form, providedSectorRowsPath) ? (
            <p className="text-sm text-destructive">
              {getRunFormError(form, providedSectorRowsPath)}
            </p>
          ) : null}
        </div>
      ) : null}

      <ExpertDisclosure description="Control the stability filters used when the projected basis is assembled and diagonalized.">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <FormField
            label="Regularization"
            htmlFor="advanced-qse-regularization-input"
            error={getTouchedRunFormError(form, "advanced_qse.regularization")}
            help={{
              short: "Optional diagonal regularization applied to the overlap solve.",
              anchor: "regularization",
            }}
          >
            <Input
              id="advanced-qse-regularization-input"
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={values.regularization ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_qse.regularization",
                  event.target.value === "" ? null : Number(event.target.value),
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              onBlur={() =>
                form.setValue("advanced_qse.regularization", values.regularization, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>
          <FormField
            label="Overlap Threshold"
            htmlFor="advanced-qse-overlap-threshold-input"
            error={getTouchedRunFormError(form, "advanced_qse.overlap_threshold")}
            help={{
              short: "Minimum overlap used to keep newly generated QSE basis states.",
              anchor: "overlap_threshold",
            }}
          >
            <Input
              id="advanced-qse-overlap-threshold-input"
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={values.overlap_threshold ?? ""}
              onChange={(event) =>
                form.setValue(
                  "advanced_qse.overlap_threshold",
                  event.target.value === "" ? null : Number(event.target.value),
                  {
                    shouldDirty: true,
                    shouldValidate: true,
                  },
                )
              }
              onBlur={() =>
                form.setValue("advanced_qse.overlap_threshold", values.overlap_threshold, {
                  shouldTouch: true,
                  shouldValidate: true,
                })
              }
              disabled={disabled}
            />
          </FormField>
        </div>
      </ExpertDisclosure>
    </div>
  );
}
