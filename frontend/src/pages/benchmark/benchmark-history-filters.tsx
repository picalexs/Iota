import { useState } from "react";
import { FilterOptionItem, FilterTriggerButton } from "@/components/filters/filter-primitives";
import { Command, CommandGroup, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  BENCHMARK_HISTORY_BACKEND_LABELS,
  BENCHMARK_HISTORY_STATUS_LABELS,
  type BenchmarkRunHistoryStatus,
} from "@/features/benchmarks/state/history";

export type BenchmarkBackendFilter = keyof typeof BENCHMARK_HISTORY_BACKEND_LABELS | "all";
export type BenchmarkStatusFilter = BenchmarkRunHistoryStatus | "all";

const BENCHMARK_HISTORY_STATUSES: BenchmarkRunHistoryStatus[] = [
  "running",
  "paused",
  "finished",
  "failed",
  "cancelled",
  "planned",
  "excluded",
  "draft",
];

export function StatusFilter({
  selectedStatus,
  onSelectStatus,
}: Readonly<{
  selectedStatus: BenchmarkStatusFilter;
  onSelectStatus: (status: BenchmarkStatusFilter) => void;
}>) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Status"
          ariaLabel="Filter by status"
          activeCount={selectedStatus === "all" ? undefined : 1}
        />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {BENCHMARK_HISTORY_STATUSES.map((status) => (
                <FilterOptionItem
                  key={status}
                  selected={selectedStatus === status}
                  onSelect={() => {
                    onSelectStatus(selectedStatus === status ? "all" : status);
                    setOpen(false);
                  }}
                >
                  {BENCHMARK_HISTORY_STATUS_LABELS[status]}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function BackendFilter({
  selectedBackend,
  onSelectBackend,
}: Readonly<{
  selectedBackend: BenchmarkBackendFilter;
  onSelectBackend: (backend: BenchmarkBackendFilter) => void;
}>) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Backend"
          ariaLabel="Filter by backend"
          activeCount={selectedBackend === "all" ? undefined : 1}
        />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {(
                Object.keys(BENCHMARK_HISTORY_BACKEND_LABELS) as Array<
                  keyof typeof BENCHMARK_HISTORY_BACKEND_LABELS
                >
              ).map((backend) => (
                <FilterOptionItem
                  key={backend}
                  selected={selectedBackend === backend}
                  onSelect={() => {
                    onSelectBackend(selectedBackend === backend ? "all" : backend);
                    setOpen(false);
                  }}
                >
                  {BENCHMARK_HISTORY_BACKEND_LABELS[backend]}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
