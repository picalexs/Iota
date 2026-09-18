import { useId, useState } from "react";
import { Check, ChevronsUpDown, HelpCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type {
  BackendDeviceSummary,
  BackendTarget,
  CustomNoisePreset,
  NoiseProfile,
  RunMode,
} from "@/types/run";

import {
  buildNoiseReferenceOptions,
  filterSuggestedBackendDevices,
  formatBackendPickerSummary,
  leastBusyDevice,
  leastErrorDevice,
  processorTypeLabel,
} from "./backend-section-shared";
import { BackendRefreshButton } from "./backend-refresh-button";

interface NoiseModelPanelProps {
  target: BackendTarget;
  disabled?: boolean;
  mode: RunMode;
  noiseProfile: NoiseProfile | null;
  onNoiseProfileChange: (next: NoiseProfile | null) => void;
  defaultNoiseProfile: () => NoiseProfile;
  referenceDevices: BackendDeviceSummary[];
  onRefresh?: () => void;
  refreshing?: boolean;
}

interface NoiseReferenceCommandItemProps {
  device: BackendDeviceSummary;
  selected: boolean;
  onSelect: () => void;
  value: string;
  badgeLabel?: string;
  className?: string;
  label?: string;
}

function NoiseReferenceCommandItem({
  device,
  selected,
  onSelect,
  value,
  badgeLabel,
  className,
  label,
}: NoiseReferenceCommandItemProps) {
  const processorLabel = processorTypeLabel(device);

  return (
    <CommandItem value={value} onSelect={onSelect} className={className}>
      <Check className={cn("mt-1 size-4 shrink-0", selected ? "opacity-100" : "opacity-0")} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{label ?? device.name}</span>
          {processorLabel != null ? (
            <Badge variant="outline" className="rounded-sm text-[10px]">
              {processorLabel}
            </Badge>
          ) : null}
          {badgeLabel != null ? (
            <Badge variant="secondary" className="rounded-sm text-[10px]">
              {badgeLabel}
            </Badge>
          ) : null}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {formatBackendPickerSummary(device, { includeProcessor: false })}
        </p>
      </div>
    </CommandItem>
  );
}

function NoiseReferenceSuggestions({
  selectedBackend,
  leastErrorRef,
  leastBusyRef,
  onSelect,
}: {
  selectedBackend: string;
  leastErrorRef: BackendDeviceSummary | null;
  leastBusyRef: BackendDeviceSummary | null;
  onSelect: (backendName: string) => void;
}) {
  const suggestions = [
    { key: "least_error", label: "Least error", device: leastErrorRef },
    { key: "least_busy", label: "Least busy", device: leastBusyRef },
  ];

  return (
    <CommandGroup heading="Suggestions">
      {suggestions.map(({ key, label, device }) =>
        device == null ? (
          <CommandItem
            key={`suggestion:${key}`}
            value={`${label} suggestion`}
            disabled
            className="items-start gap-3 bg-muted/25 py-3"
          >
            <Check className="mt-1 size-4 shrink-0 opacity-0" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{label}</span>
                <Badge variant="secondary" className="rounded-sm text-[10px]">
                  Suggestion
                </Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                No calibrated backends available
              </p>
            </div>
          </CommandItem>
        ) : (
          <NoiseReferenceCommandItem
            key={`suggestion:${key}`}
            device={device}
            selected={selectedBackend === device.name}
            onSelect={() => onSelect(device.name)}
            value={`${label} suggestion ${device.name} ${processorTypeLabel(device) ?? ""}`}
            className="items-start gap-3 bg-muted/25 py-3"
            label={`${label}: ${device.name}`}
            badgeLabel="Suggestion"
          />
        ),
      )}
    </CommandGroup>
  );
}

export function NoiseModelPanel({
  target,
  disabled,
  mode,
  noiseProfile,
  onNoiseProfileChange,
  defaultNoiseProfile,
  referenceDevices,
  onRefresh,
  refreshing,
}: NoiseModelPanelProps) {
  const referenceOptions = buildNoiseReferenceOptions(referenceDevices, noiseProfile);
  const visibleReferenceOptions = filterSuggestedBackendDevices(referenceOptions);
  const leastErrorRef = leastErrorDevice(referenceDevices);
  const leastBusyRef = leastBusyDevice(referenceDevices);
  const hasSuggestions = referenceDevices.length > 0;
  const [open, setOpen] = useState(false);
  const listboxId = useId();

  const selectedDevice =
    noiseProfile?.source === "backend_derived"
      ? (referenceOptions.find((d) => d.name === noiseProfile.reference_backend) ?? null)
      : null;
  const selectedLabel = selectedDevice?.name ?? "Select noise reference backend";
  const selectedNoiseInfoHref =
    noiseProfile?.source === "custom_preset" ? `/info/noise-models/${noiseProfile.preset}` : null;
  const selectedBackendName =
    noiseProfile?.source === "backend_derived" ? noiseProfile.reference_backend : "";

  return (
    <div className="rounded-lg border border-border/70 bg-card p-3 dark:bg-muted/20">
      <div className="flex items-center gap-2">
        <Checkbox
          id="noise-profile-enabled"
          checked={noiseProfile !== null}
          disabled={disabled}
          onCheckedChange={(checked) =>
            onNoiseProfileChange(checked ? defaultNoiseProfile() : null)
          }
        />
        <label htmlFor="noise-profile-enabled" className="text-sm font-medium">
          Noise model
        </label>
        <InfoPageHelp
          href="/info/noise-models"
          label="noise models"
          short="Open the reference guide for the available noise-model families."
        />
      </div>

      {noiseProfile !== null && (
        <div className="mt-3 grid gap-3">
          {mode === "advanced" && (
            <div className="grid gap-2">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Noise source
                </p>
                <InfoPageHelp
                  href="/info/noise-models"
                  label="noise source"
                  short="Choose between a preset local model or an IBM-backend-derived calibration snapshot."
                />
              </div>
              <Select
                value={noiseProfile.source}
                onValueChange={(next) =>
                  onNoiseProfileChange(
                    next === "backend_derived"
                      ? defaultNoiseProfile()
                      : {
                          source: "custom_preset",
                          preset: "depolarizing_cx",
                          strength: 0.01,
                        },
                  )
                }
              >
                <SelectTrigger aria-label="Noise source" disabled={disabled}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="backend_derived">Backend derived</SelectItem>
                  <SelectItem value="custom_preset">Custom preset</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {noiseProfile.source === "backend_derived" ? (
            <div className="grid gap-2">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Reference backend
                </p>
                <InfoPageHelp
                  href="/info/noise-models/backend_derived"
                  label="backend-derived noise"
                  short="Learn how backend-derived noise mirrors a selected IBM backend's calibration snapshot."
                />
              </div>
              {referenceOptions.length > 0 ? (
                <div className="flex gap-2">
                  <div className="min-w-0 flex-1">
                    <Popover open={open} onOpenChange={setOpen}>
                      <PopoverTrigger asChild>
                        <Button
                          type="button"
                          variant="outline"
                          role="combobox"
                          aria-controls={listboxId}
                          aria-expanded={open}
                          disabled={disabled}
                          className="h-auto min-h-11 w-full justify-between whitespace-normal text-left font-normal data-[state=open]:border-interactive-hover-border data-[state=open]:bg-surface-raised-hover"
                        >
                          <span className="flex min-w-0 flex-col">
                            <span className="truncate text-sm font-medium">{selectedLabel}</span>
                            {selectedDevice != null ? (
                              <span className="text-xs text-muted-foreground">
                                {formatBackendPickerSummary(selectedDevice)}
                              </span>
                            ) : null}
                          </span>
                          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent
                        className="w-[--radix-popover-trigger-width] p-0"
                        align="start"
                      >
                        <Command>
                          <CommandInput placeholder="Search backend name, queue, qubits..." />
                          <CommandList id={listboxId} role="listbox">
                            <CommandEmpty>No backends found.</CommandEmpty>
                            {hasSuggestions && (
                              <NoiseReferenceSuggestions
                                selectedBackend={selectedBackendName}
                                leastErrorRef={leastErrorRef}
                                leastBusyRef={leastBusyRef}
                                onSelect={(backendName) => {
                                  onNoiseProfileChange({
                                    ...noiseProfile,
                                    reference_backend: backendName,
                                  });
                                  setOpen(false);
                                }}
                              />
                            )}
                            <CommandGroup>
                              {visibleReferenceOptions.map((device) => {
                                return (
                                  <NoiseReferenceCommandItem
                                    key={device.name}
                                    device={device}
                                    selected={device.name === selectedBackendName}
                                    value={`${device.name} ${processorTypeLabel(device) ?? ""} ${formatBackendPickerSummary(device)}`}
                                    onSelect={() => {
                                      onNoiseProfileChange({
                                        ...noiseProfile,
                                        reference_backend: device.name,
                                      });
                                      setOpen(false);
                                    }}
                                    className="items-start gap-3 py-3"
                                  />
                                );
                              })}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                  </div>
                  {onRefresh && (
                    <BackendRefreshButton
                      onClick={onRefresh}
                      disabled={disabled}
                      refreshing={refreshing}
                      aria-label="Refresh noise reference backends"
                    />
                  )}
                </div>
              ) : (
                <Input
                  aria-label="IBM noise reference"
                  value={noiseProfile.reference_backend}
                  onChange={(event) =>
                    onNoiseProfileChange({
                      ...noiseProfile,
                      reference_backend: event.target.value,
                    })
                  }
                  disabled={disabled || mode !== "advanced"}
                />
              )}
              <div className="rounded-md border border-border/70 bg-background px-3 py-2 text-xs text-muted-foreground">
                {target === "aer_simulator"
                  ? "The run stays local on Aer while the noise model mirrors the selected IBM backend calibration or fake-provider snapshot."
                  : "Backend-derived noise follows the selected backend calibration metadata."}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-2">
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Noise preset
                  </p>
                  <InfoPageHelp
                    href={selectedNoiseInfoHref ?? "/info/noise-models"}
                    label="noise preset"
                    short="Open the detail page for the currently selected preset."
                  />
                </div>
                <Select
                  value={noiseProfile.preset}
                  onValueChange={(next) =>
                    onNoiseProfileChange({
                      ...noiseProfile,
                      preset: next as CustomNoisePreset,
                    })
                  }
                >
                  <SelectTrigger
                    aria-label="Noise preset"
                    disabled={disabled || mode !== "advanced"}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="depolarizing_cx">Depolarizing CX</SelectItem>
                    <SelectItem value="thermal_relaxation">Thermal relaxation</SelectItem>
                    <SelectItem value="readout_bias">Readout bias</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Strength
                  </p>
                  <InfoPageHelp
                    href={selectedNoiseInfoHref ?? "/info/noise-models"}
                    label="noise strength"
                    short="The preset detail page explains what increasing the strength knob means for this noise family."
                  />
                </div>
                <Input
                  aria-label="Noise strength"
                  type="number"
                  min={0}
                  max={1}
                  step={0.001}
                  value={noiseProfile.strength}
                  onChange={(event) =>
                    onNoiseProfileChange({
                      ...noiseProfile,
                      strength: Number(event.target.value),
                    })
                  }
                  disabled={disabled || mode !== "advanced"}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InfoPageHelp({ href, label, short }: { href: string; label: string; short: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Learn more about ${label}`}
          className="inline-flex rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <HelpCircle className="size-3.5" />
        </a>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-56 text-xs">
        {short}
      </TooltipContent>
    </Tooltip>
  );
}
