import { useId, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { BackendDeviceSummary } from "@/types/run";
import {
  filterSuggestedBackendDevices,
  formatBackendPickerSummary,
  leastBusyDevice,
  leastErrorDevice,
  processorTypeLabel,
} from "@/components/forms/run-form/backend-section-shared";

interface BenchmarkBackendPickerProps {
  devices: readonly BackendDeviceSummary[];
  selectedBackendName: string | null;
  placeholder: string;
  ariaLabelledBy?: string;
  disabled?: boolean;
  onOpen?: () => void;
  onSelect: (backendName: string) => void;
}

interface BenchmarkBackendCommandItemProps {
  device: BackendDeviceSummary;
  selected: boolean;
  onSelect: () => void;
  value: string;
  label?: string;
  badgeLabel?: string;
  className?: string;
}

function BenchmarkBackendCommandItem({
  device,
  selected,
  onSelect,
  value,
  label,
  badgeLabel,
  className,
}: BenchmarkBackendCommandItemProps) {
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

export function BenchmarkBackendPicker({
  devices,
  selectedBackendName,
  placeholder,
  ariaLabelledBy,
  disabled,
  onOpen,
  onSelect,
}: BenchmarkBackendPickerProps) {
  const [open, setOpen] = useState(false);
  const listboxId = useId();
  const leastErrorRef = leastErrorDevice([...devices]);
  const leastBusyRef = leastBusyDevice([...devices]);
  const visibleDevices = filterSuggestedBackendDevices([...devices]);
  const selectedDevice = devices.find((device) => device.name === selectedBackendName) ?? null;
  const selectedLabel = selectedDevice?.name ?? placeholder;
  const suggestions = [
    { key: "least_error", label: "Least error", device: leastErrorRef },
    { key: "least_busy", label: "Least busy", device: leastBusyRef },
  ];

  if (devices.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card p-4 text-sm text-muted-foreground dark:bg-muted/20">
        No IBM backends are available right now.
      </div>
    );
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen) {
          onOpen?.();
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-labelledby={ariaLabelledBy}
          aria-controls={listboxId}
          aria-expanded={open}
          disabled={disabled}
          className="h-10 min-h-10 w-full justify-between whitespace-normal px-3 py-2 text-left font-normal data-[state=open]:border-interactive-hover-border data-[state=open]:bg-surface-raised-hover"
        >
          <span className="flex min-w-0 flex-col justify-center">
            <span className="truncate text-sm font-medium">{selectedLabel}</span>
            {selectedDevice != null ? (
              <span className="truncate text-[11px] leading-tight text-muted-foreground">
                {formatBackendPickerSummary(selectedDevice)}
              </span>
            ) : null}
          </span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search backend name, queue, qubits..." />
          <CommandList id={listboxId} role="listbox">
            <CommandEmpty>No backends found.</CommandEmpty>
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
                  <BenchmarkBackendCommandItem
                    key={`suggestion:${key}`}
                    device={device}
                    selected={selectedBackendName === device.name}
                    onSelect={() => {
                      onSelect(device.name);
                      setOpen(false);
                    }}
                    value={`${label} suggestion ${device.name} ${processorTypeLabel(device) ?? ""}`}
                    className="items-start gap-3 bg-muted/25 py-3"
                    label={`${label}: ${device.name}`}
                    badgeLabel="Suggestion"
                  />
                ),
              )}
            </CommandGroup>
            {visibleDevices.length > 0 ? (
              <>
                <div className="mx-3 border-t border-border/60" />
                <CommandGroup>
                  {visibleDevices.map((device) => (
                    <BenchmarkBackendCommandItem
                      key={device.name}
                      device={device}
                      selected={selectedBackendName === device.name}
                      value={`${device.name} ${processorTypeLabel(device) ?? ""} ${formatBackendPickerSummary(device)}`}
                      onSelect={() => {
                        onSelect(device.name);
                        setOpen(false);
                      }}
                      className="items-start gap-3 py-3"
                    />
                  ))}
                </CommandGroup>
              </>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
