import { useState } from "react";
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
import type { BackendDeviceSummary, BackendOptions, BackendTarget } from "@/types/run";

import {
  backendChoiceLabel,
  backendChoiceSearchValue,
  buildBackendChoices,
  filterSuggestedBackendDevices,
  formatBackendPickerSummary,
  processorTypeLabel,
  selectedBackendChoiceId,
  suggestedBackendSummary,
  type BackendPickerChoice,
} from "./backend-section-shared";

interface BackendPickerProps {
  target: BackendTarget;
  devices: BackendDeviceSummary[];
  backendOptions: BackendOptions;
  disabled?: boolean;
  onSelect: (choice: BackendPickerChoice) => void;
}

export function BackendPicker({
  target,
  devices,
  backendOptions,
  disabled,
  onSelect,
}: BackendPickerProps) {
  const [open, setOpen] = useState(false);
  const listboxId = "backend-device-picker-listbox";
  const choices = buildBackendChoices(target, devices);
  const suggestions = choices.filter(
    (choice): choice is Extract<BackendPickerChoice, { kind: "policy" }> =>
      choice.kind === "policy",
  );
  const deviceChoices = choices.filter(
    (choice): choice is Extract<BackendPickerChoice, { kind: "device" }> =>
      choice.kind === "device",
  );
  const visibleDeviceNames = new Set(
    filterSuggestedBackendDevices(devices).map((device) => device.name),
  );
  const visibleDeviceChoices = deviceChoices.filter((choice) =>
    visibleDeviceNames.has(choice.device.name),
  );
  const selectedChoiceId = selectedBackendChoiceId(target, backendOptions, devices);
  const selectedChoice = choices.find((choice) => choice.id === selectedChoiceId) ?? null;
  const selectedLabel =
    selectedChoice != null ? backendChoiceLabel(selectedChoice) : "Select backend or suggestion";
  const selectedDevice =
    selectedChoice?.kind === "policy" ? selectedChoice.suggestedDevice : selectedChoice?.device;

  if (choices.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/80 bg-card p-4 text-sm text-muted-foreground dark:bg-muted/20">
        No selectable backends were returned for this target.
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id="backend-device-picker"
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
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search backend name, queue, qubits..." />
          <CommandList id={listboxId} role="listbox">
            <CommandEmpty>No backends found.</CommandEmpty>
            <CommandGroup>
              {suggestions.map((choice) => {
                const device = choice.suggestedDevice;
                const selected = choice.id === selectedChoiceId;
                return (
                  <CommandItem
                    key={choice.id}
                    value={backendChoiceSearchValue(choice)}
                    onSelect={() => {
                      onSelect(choice);
                      setOpen(false);
                    }}
                    className="items-start gap-3 bg-muted/25 py-3"
                  >
                    <Check
                      className={cn("mt-1 size-4 shrink-0", selected ? "opacity-100" : "opacity-0")}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{backendChoiceLabel(choice)}</span>
                        {device != null && processorTypeLabel(device) != null ? (
                          <Badge variant="outline" className="rounded-sm text-[10px]">
                            {processorTypeLabel(device)}
                          </Badge>
                        ) : null}
                        <Badge variant="secondary" className="rounded-sm text-[10px]">
                          Suggestion
                        </Badge>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {suggestedBackendSummary(choice)}
                      </p>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
            {suggestions.length > 0 && visibleDeviceChoices.length > 0 ? (
              <div className="mx-3 border-t border-border/60" />
            ) : null}
            <CommandGroup>
              {visibleDeviceChoices.map((choice) => {
                const selected = choice.id === selectedChoiceId;
                return (
                  <CommandItem
                    key={choice.id}
                    value={backendChoiceSearchValue(choice)}
                    onSelect={() => {
                      onSelect(choice);
                      setOpen(false);
                    }}
                    className="items-start gap-3 py-3"
                  >
                    <Check
                      className={cn("mt-1 size-4 shrink-0", selected ? "opacity-100" : "opacity-0")}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{choice.device.name}</span>
                        {processorTypeLabel(choice.device) != null ? (
                          <Badge variant="outline" className="rounded-sm text-[10px]">
                            {processorTypeLabel(choice.device)}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {formatBackendPickerSummary(choice.device, { includeProcessor: false })}
                      </p>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
