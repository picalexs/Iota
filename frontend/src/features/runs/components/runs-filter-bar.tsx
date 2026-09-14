import { useState, type ReactNode } from "react";
import { X } from "lucide-react";
import {
  ActiveFilterChip,
  ClearFiltersButton,
  FilterOptionItem,
  FilterTriggerButton,
} from "@/components/filters/filter-primitives";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { BackendTarget, RunAlgorithm, RunStatus, UUID } from "@/types/run";
import { ALL_BACKENDS, ALL_METHODS, ALL_STATUSES } from "../state/filters";

const BACKEND_LABELS = {
  statevector: "Statevector",
  aer_simulator: "Aer Simulator",
  ibm_runtime: "IBM Runtime",
} as const;

const CHEMICAL_ACCURACY_FILTERS = [
  { label: "Yes", value: true },
  { label: "No", value: false },
] as const;

interface StatusFilterProps {
  readonly selectedStatuses: RunStatus[];
  readonly onToggleStatus: (status: RunStatus) => void;
}

function StatusFilter({ selectedStatuses, onToggleStatus }: StatusFilterProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Status"
          ariaLabel="Filter by status"
          activeCount={selectedStatuses.length}
        />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {ALL_STATUSES.map((status) => (
                <FilterOptionItem
                  key={status}
                  selected={selectedStatuses.includes(status)}
                  onSelect={() => onToggleStatus(status)}
                >
                  {status}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

interface BackendFilterProps {
  readonly selectedBackend?: BackendTarget;
  readonly onToggleBackend: (backend: BackendTarget) => void;
}

function BackendFilter({ selectedBackend, onToggleBackend }: BackendFilterProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Backend"
          ariaLabel="Filter by backend"
          activeCount={selectedBackend ? 1 : undefined}
        />
      </PopoverTrigger>
      <PopoverContent className="w-48 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {ALL_BACKENDS.map((backend) => (
                <FilterOptionItem
                  key={backend}
                  selected={selectedBackend === backend}
                  onSelect={() => onToggleBackend(backend)}
                >
                  {BACKEND_LABELS[backend]}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

interface MethodFilterProps {
  readonly selectedMethods: RunAlgorithm[];
  readonly onToggleMethod: (method: RunAlgorithm) => void;
}

function MethodFilter({ selectedMethods, onToggleMethod }: MethodFilterProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Method"
          ariaLabel="Filter by method"
          activeCount={selectedMethods.length}
        />
      </PopoverTrigger>
      <PopoverContent className="w-44 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {ALL_METHODS.map((method) => (
                <FilterOptionItem
                  key={method}
                  selected={selectedMethods.includes(method)}
                  onSelect={() => onToggleMethod(method)}
                >
                  {method.toUpperCase()}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

interface ChemicalAccuracyFilterProps {
  readonly selectedChemicalAccurate?: boolean;
  readonly onToggleChemicalAccurate: (chemicalAccurate: boolean) => void;
}

function ChemicalAccuracyFilter({
  selectedChemicalAccurate,
  onToggleChemicalAccurate,
}: ChemicalAccuracyFilterProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Chemical accurate"
          ariaLabel="Filter by chemical accuracy"
          activeCount={selectedChemicalAccurate === undefined ? undefined : 1}
        />
      </PopoverTrigger>
      <PopoverContent className="w-44 p-0" align="start">
        <Command>
          <CommandList>
            <CommandGroup>
              {CHEMICAL_ACCURACY_FILTERS.map((option) => (
                <FilterOptionItem
                  key={String(option.value)}
                  selected={selectedChemicalAccurate === option.value}
                  onSelect={() => onToggleChemicalAccurate(option.value)}
                >
                  {option.label}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

interface MoleculeFilterItem {
  readonly id: UUID;
  readonly name: string;
}

interface MoleculeFilterProps {
  readonly molecules: MoleculeFilterItem[];
  readonly selectedMoleculeIds: string[];
  readonly isLoading: boolean;
  readonly onToggleMolecule: (id: string) => void;
}

function MoleculeFilter({
  molecules,
  selectedMoleculeIds,
  isLoading,
  onToggleMolecule,
}: MoleculeFilterProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label="Molecule"
          ariaLabel="Filter by molecule"
          activeCount={selectedMoleculeIds.length}
        />
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search molecules…" className="text-xs" />
          <CommandList>
            <CommandEmpty className="text-xs py-4 text-center text-muted-foreground">
              {isLoading ? "Loading molecules..." : "No molecules found."}
            </CommandEmpty>
            <CommandGroup>
              {molecules.map((molecule) => (
                <FilterOptionItem
                  key={molecule.id}
                  value={molecule.name}
                  selected={selectedMoleculeIds.includes(molecule.id)}
                  onSelect={() => onToggleMolecule(molecule.id)}
                >
                  {molecule.name}
                </FilterOptionItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export interface RunsFilterBarProps {
  readonly filterStatuses: RunStatus[];
  readonly filterMoleculeIds: string[];
  readonly filterMethods: RunAlgorithm[];
  readonly filterBackendTarget?: BackendTarget;
  readonly filterChemicalAccurate?: boolean;
  readonly molecules: MoleculeFilterItem[];
  readonly moleculeMap: Map<UUID, string>;
  readonly isMoleculeLookupLoading: boolean;
  readonly hasActiveFilters: boolean;
  readonly toggleStatus: (status: RunStatus) => void;
  readonly toggleMolecule: (id: string) => void;
  readonly toggleMethod: (method: RunAlgorithm) => void;
  readonly toggleBackendTarget: (backendTarget: BackendTarget) => void;
  readonly toggleChemicalAccurate: (chemicalAccurate: boolean) => void;
  readonly clearFilters: () => void;
  readonly actionSlot?: ReactNode;
}

export function RunsFilterBar({
  filterStatuses,
  filterMoleculeIds,
  filterMethods,
  filterBackendTarget,
  filterChemicalAccurate,
  molecules,
  moleculeMap,
  isMoleculeLookupLoading,
  hasActiveFilters,
  toggleStatus,
  toggleMolecule,
  toggleMethod,
  toggleBackendTarget,
  toggleChemicalAccurate,
  clearFilters,
  actionSlot,
}: RunsFilterBarProps) {
  return (
    <div className="flex flex-col gap-2 border-b px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <StatusFilter selectedStatuses={filterStatuses} onToggleStatus={toggleStatus} />
        <BackendFilter
          selectedBackend={filterBackendTarget}
          onToggleBackend={toggleBackendTarget}
        />
        <MethodFilter selectedMethods={filterMethods} onToggleMethod={toggleMethod} />
        <ChemicalAccuracyFilter
          selectedChemicalAccurate={filterChemicalAccurate}
          onToggleChemicalAccurate={toggleChemicalAccurate}
        />
        <MoleculeFilter
          molecules={molecules}
          selectedMoleculeIds={filterMoleculeIds}
          isLoading={isMoleculeLookupLoading}
          onToggleMolecule={toggleMolecule}
        />
        <ActiveFilterChips
          filterStatuses={filterStatuses}
          filterMoleculeIds={filterMoleculeIds}
          filterMethods={filterMethods}
          filterBackendTarget={filterBackendTarget}
          filterChemicalAccurate={filterChemicalAccurate}
          moleculeMap={moleculeMap}
          toggleStatus={toggleStatus}
          toggleMolecule={toggleMolecule}
          toggleMethod={toggleMethod}
          toggleBackendTarget={toggleBackendTarget}
          toggleChemicalAccurate={toggleChemicalAccurate}
        />
        {hasActiveFilters && (
          <ClearFiltersButton
            label="Clear"
            ariaLabel="Clear run filters"
            className="h-7 px-2"
            icon={<X className="ml-1 size-3" />}
            onClear={clearFilters}
          />
        )}
      </div>
      {actionSlot ? <div className="flex shrink-0 items-center">{actionSlot}</div> : null}
    </div>
  );
}

type ActiveFilterChipsProps = Pick<
  RunsFilterBarProps,
  | "filterStatuses"
  | "filterMoleculeIds"
  | "filterMethods"
  | "filterBackendTarget"
  | "filterChemicalAccurate"
  | "moleculeMap"
  | "toggleStatus"
  | "toggleMolecule"
  | "toggleMethod"
  | "toggleBackendTarget"
  | "toggleChemicalAccurate"
>;

function ActiveFilterChips({
  filterStatuses,
  filterMoleculeIds,
  filterMethods,
  filterBackendTarget,
  filterChemicalAccurate,
  moleculeMap,
  toggleStatus,
  toggleMolecule,
  toggleMethod,
  toggleBackendTarget,
  toggleChemicalAccurate,
}: ActiveFilterChipsProps) {
  return (
    <>
      {filterStatuses.map((status) => (
        <ActiveFilterChip
          key={status}
          label={status}
          onRemove={() => toggleStatus(status)}
          ariaLabel={`Remove ${status} filter`}
        />
      ))}
      {filterMoleculeIds.map((id) => (
        <ActiveFilterChip
          key={id}
          label={moleculeMap.get(id) ?? id.slice(0, 8)}
          onRemove={() => toggleMolecule(id)}
          ariaLabel="Remove molecule filter"
        />
      ))}
      {filterMethods.map((method) => {
        const label = method.toUpperCase();
        return (
          <ActiveFilterChip
            key={method}
            label={label}
            onRemove={() => toggleMethod(method)}
            ariaLabel={`Remove ${label} method filter`}
          />
        );
      })}
      {filterBackendTarget && (
        <ActiveFilterChip
          label={BACKEND_LABELS[filterBackendTarget]}
          onRemove={() => toggleBackendTarget(filterBackendTarget)}
          ariaLabel={`Remove ${BACKEND_LABELS[filterBackendTarget]} backend filter`}
        />
      )}
      {filterChemicalAccurate !== undefined && (
        <ActiveFilterChip
          label={filterChemicalAccurate ? "Chemical accurate: Yes" : "Chemical accurate: No"}
          onRemove={() => toggleChemicalAccurate(filterChemicalAccurate)}
          ariaLabel={`Remove chemical accurate ${filterChemicalAccurate ? "yes" : "no"} filter`}
        />
      )}
    </>
  );
}
