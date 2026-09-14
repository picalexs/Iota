import { useState } from "react";
import {
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

export interface ScatterFilterOption {
  value: string;
  label: string;
}

function ScatterFilterPopover({
  label,
  ariaLabel,
  options,
  hiddenValues,
  emptyLabel,
  allLabel,
  onToggleValue,
  onSelectAll,
  onHideAll,
}: Readonly<{
  label: string;
  ariaLabel: string;
  options: readonly ScatterFilterOption[];
  hiddenValues: ReadonlySet<string>;
  emptyLabel: string;
  allLabel: string;
  onToggleValue: (value: string) => void;
  onSelectAll: () => void;
  onHideAll: () => void;
}>) {
  const [open, setOpen] = useState(false);
  const visibleCount = options.filter((option) => !hiddenValues.has(option.value)).length;
  const activeCount = hiddenValues.size > 0 ? visibleCount : undefined;
  const allSelected = hiddenValues.size === 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          label={label}
          ariaLabel={ariaLabel}
          activeCount={activeCount}
          badgeClassName="text-[10px]"
        />
      </PopoverTrigger>
      <PopoverContent className="w-56 p-0" align="start">
        <Command>
          {options.length > 6 ? (
            <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
          ) : null}
          <CommandList>
            <CommandEmpty>{emptyLabel}</CommandEmpty>
            <CommandGroup>
              <FilterOptionItem
                selected={allSelected}
                value={`${allLabel} all`}
                onSelect={allSelected ? onHideAll : onSelectAll}
              >
                {allLabel}
              </FilterOptionItem>
              {options.map((option) => {
                const selected = !hiddenValues.has(option.value);
                return (
                  <FilterOptionItem
                    key={option.value}
                    selected={selected}
                    value={`${option.label} ${option.value}`}
                    onSelect={() => onToggleValue(option.value)}
                    selectedIndicatorClassName="border-border bg-accent text-accent-foreground shadow-none"
                  >
                    <span className="truncate" title={option.label}>
                      {option.label}
                    </span>
                  </FilterOptionItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export function RuntimeScatterFilters({
  familyOptions,
  algorithmOptions,
  moleculeOptions,
  hiddenFamilies,
  hiddenAlgorithms,
  hiddenMolecules,
  hasActiveFilters,
  pointsCount,
  totalPoints,
  onToggleFamily,
  onShowAllFamilies,
  onHideAllFamilies,
  onToggleAlgorithm,
  onToggleMolecule,
  onShowAllAlgorithms,
  onHideAllAlgorithms,
  onShowAllMolecules,
  onHideAllMolecules,
  onResetFilters,
}: Readonly<{
  familyOptions: readonly ScatterFilterOption[];
  algorithmOptions: readonly ScatterFilterOption[];
  moleculeOptions: readonly ScatterFilterOption[];
  hiddenFamilies: ReadonlySet<string>;
  hiddenAlgorithms: ReadonlySet<string>;
  hiddenMolecules: ReadonlySet<string>;
  hasActiveFilters: boolean;
  pointsCount: number;
  totalPoints: number;
  onToggleFamily: (value: string) => void;
  onShowAllFamilies: () => void;
  onHideAllFamilies: () => void;
  onToggleAlgorithm: (value: string) => void;
  onToggleMolecule: (value: string) => void;
  onShowAllAlgorithms: () => void;
  onHideAllAlgorithms: () => void;
  onShowAllMolecules: () => void;
  onHideAllMolecules: () => void;
  onResetFilters: () => void;
}>) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {familyOptions.length > 1 ? (
          <ScatterFilterPopover
            label="Families"
            ariaLabel="Filter accuracy-vs-runtime chart by family"
            options={familyOptions}
            hiddenValues={hiddenFamilies}
            emptyLabel="No families match."
            allLabel="All families"
            onToggleValue={onToggleFamily}
            onSelectAll={onShowAllFamilies}
            onHideAll={onHideAllFamilies}
          />
        ) : null}
        {algorithmOptions.length > 1 ? (
          <ScatterFilterPopover
            label="Algorithms"
            ariaLabel="Filter accuracy-vs-runtime chart by algorithm"
            options={algorithmOptions}
            hiddenValues={hiddenAlgorithms}
            emptyLabel="No algorithms match."
            allLabel="All algorithms"
            onToggleValue={onToggleAlgorithm}
            onSelectAll={onShowAllAlgorithms}
            onHideAll={onHideAllAlgorithms}
          />
        ) : null}
        {moleculeOptions.length > 1 ? (
          <ScatterFilterPopover
            label="Molecules"
            ariaLabel="Filter accuracy-vs-runtime chart by molecule"
            options={moleculeOptions}
            hiddenValues={hiddenMolecules}
            emptyLabel="No molecules match."
            allLabel="All molecules"
            onToggleValue={onToggleMolecule}
            onSelectAll={onShowAllMolecules}
            onHideAll={onHideAllMolecules}
          />
        ) : null}
        {hasActiveFilters ? (
          <ClearFiltersButton
            label="Show all"
            ariaLabel="Show all points"
            className="px-2"
            onClear={onResetFilters}
          />
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        Showing {pointsCount} of {totalPoints} point{totalPoints === 1 ? "" : "s"}
      </p>
    </div>
  );
}

export function RuntimeScatterEmptyState({
  totalPoints,
  hasActiveFilters,
  onResetFilters,
}: Readonly<{
  totalPoints: number;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
}>) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-3 rounded-md border border-dashed px-4 text-center text-sm text-muted-foreground">
      <p>
        {totalPoints === 0
          ? "No completed scored rows yet"
          : "No completed scored rows match the current chart filters."}
      </p>
      {hasActiveFilters && totalPoints > 0 ? (
        <ClearFiltersButton
          label="Show all points"
          ariaLabel="Show all points"
          variant="outline"
          onClear={onResetFilters}
        />
      ) : null}
    </div>
  );
}
