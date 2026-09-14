import { useId, useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "./button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "./command";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { cn } from "@/lib/utils";
import type { MoleculeResponse } from "@/types/run";

type MoleculeComboboxProps = Readonly<{
  molecules: readonly MoleculeResponse[];
  value: string; // selected molecule UUID
  onChange: (value: string) => void;
  disabled?: boolean;
  loading?: boolean;
  placeholder?: string;
  id?: string;
  incompatibleIds?: Map<string, string>; // molecule id -> reason string
}>;

function buildFormula(atoms: MoleculeResponse["atoms"] | null | undefined): string {
  if (!Array.isArray(atoms) || atoms.length === 0) {
    return "";
  }

  const counts: Record<string, number> = {};
  for (const atom of atoms) {
    counts[atom.symbol] = (counts[atom.symbol] ?? 0) + 1;
  }
  const parts: string[] = [];
  for (const sym of [
    "C",
    "H",
    ...Object.keys(counts)
      .filter((s) => s !== "C" && s !== "H")
      .sort((left, right) => left.localeCompare(right)),
  ]) {
    if (counts[sym]) parts.push(counts[sym] === 1 ? sym : `${sym}${counts[sym]}`);
  }
  return parts.join("");
}

function tokenizeSearchValue(value: string): string[] {
  return value
    .split(/[^a-z0-9]+/i)
    .map((part) => part.trim().toLowerCase())
    .filter((part) => part.length > 0);
}

function rankTextMatch(value: string, query: string): number | null {
  const normalized = value.trim().toLowerCase();
  if (normalized.length === 0) {
    return null;
  }

  if (normalized === query) {
    return 0;
  }
  if (normalized.startsWith(query)) {
    return 1;
  }

  const tokens = tokenizeSearchValue(normalized);
  if (tokens.some((token) => token.startsWith(query))) {
    return 2;
  }

  const index = normalized.indexOf(query);
  if (index >= 0) {
    return 10 + index;
  }

  return null;
}

type RankedMoleculeMatch = {
  molecule: MoleculeResponse;
  score: number;
  index: number;
};

function rankMoleculeMatch(molecule: MoleculeResponse, query: string): number | null {
  const fields = [
    { weight: 0, value: molecule.name },
    { weight: 100, value: molecule.iupac_name ?? "" },
    { weight: 200, value: buildFormula(molecule.atoms) },
    ...((molecule.synonyms ?? []).map((synonym) => ({ weight: 300, value: synonym })) ?? []),
  ];
  let bestScore: number | null = null;
  for (const field of fields) {
    const matchRank = rankTextMatch(field.value, query);
    if (matchRank == null) continue;
    const nextScore = field.weight + matchRank;
    if (bestScore == null || nextScore < bestScore) bestScore = nextScore;
  }
  return bestScore;
}

export function filterAndSortMolecules(
  molecules: readonly MoleculeResponse[],
  search: string,
): MoleculeResponse[] {
  const query = search.trim().toLowerCase();
  if (query.length === 0) {
    return [...molecules];
  }

  const ranked: RankedMoleculeMatch[] = [];
  molecules.forEach((molecule, index) => {
    const bestScore = rankMoleculeMatch(molecule, query);
    if (bestScore == null) {
      return;
    }

    ranked.push({ molecule, score: bestScore, index });
  });

  ranked.sort((left, right) => {
    if (left.score !== right.score) {
      return left.score - right.score;
    }

    const nameCompare = left.molecule.name.localeCompare(right.molecule.name, undefined, {
      sensitivity: "base",
    });
    if (nameCompare !== 0) {
      return nameCompare;
    }

    return left.index - right.index;
  });

  return ranked.map((entry) => entry.molecule);
}

export function MoleculeCombobox({
  molecules,
  value,
  onChange,
  disabled = false,
  loading = false,
  placeholder = "Select a molecule",
  id,
  incompatibleIds,
}: MoleculeComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const generatedId = useId();
  const comboboxId = id ?? `molecule-combobox-${generatedId}`;
  const listboxId = `${comboboxId}-listbox`;

  const selectedMolecule = molecules.find((mol) => mol.id === value);
  let selectedLabel = placeholder;
  if (loading) {
    selectedLabel = "Loading molecules...";
  } else if (selectedMolecule) {
    selectedLabel = selectedMolecule.name;
  }

  const filteredMolecules = useMemo(
    () => filterAndSortMolecules(molecules, search),
    [molecules, search],
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={comboboxId}
          variant="outline"
          role="combobox"
          aria-controls={listboxId}
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between font-normal data-[state=open]:border-interactive-hover-border data-[state=open]:bg-surface-raised-hover"
        >
          <span className="flex min-w-0 items-center gap-2">
            {loading ? <Spinner className="opacity-70" /> : null}
            <span className="truncate">{selectedLabel}</span>
          </span>
          {loading ? null : <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[min(var(--radix-popover-trigger-width),42rem)] p-0"
      >
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search by name or formula..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList
            id={listboxId}
            role="listbox"
            className="[scrollbar-gutter:stable] h-[320px]"
          >
            <CommandEmpty>No molecules found.</CommandEmpty>
            <CommandGroup>
              {filteredMolecules.map((mol) => {
                const formula = buildFormula(mol.atoms);
                const basisSet = mol.basis_set ?? "sto-3g";
                const incompatReason = incompatibleIds?.get(mol.id);
                const isIncompat = !!incompatReason;
                return (
                  <CommandItem
                    key={mol.id}
                    value={mol.id}
                    disabled={isIncompat}
                    className={cn(isIncompat && "opacity-60")}
                    onSelect={() => {
                      if (!isIncompat) {
                        onChange(mol.id);
                        setSearch("");
                        setOpen(false);
                      }
                    }}
                  >
                    <Check
                      className={cn("mr-2 h-4 w-4", value === mol.id ? "opacity-100" : "opacity-0")}
                    />
                    <span className={cn(isIncompat && "text-muted-foreground")}>{mol.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {formula} · {basisSet}
                      {isIncompat && (
                        <span className="ml-1 text-destructive/70">· {incompatReason}</span>
                      )}
                    </span>
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
