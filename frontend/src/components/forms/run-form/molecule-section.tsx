import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { fetchBasisSets } from "@/api/molecules";
import { MoleculeViewer2D } from "@/components/molecules/molecule-viewer-2d";
import { MoleculeCombobox } from "@/components/ui/molecule-combobox";
import { Badge } from "@/components/ui/badge";
import { FormField } from "@/components/forms/form-field";
import { useTheme } from "@/hooks/use-theme";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { BasisSetMetadata, MoleculeResponse } from "@/types/run";

const DEFAULT_BASIS_SET_VALUE = "__default__";
const FALLBACK_BASIS_SET = "sto-3g";
const FALLBACK_BASIS_OPTIONS: BasisSetMetadata[] = [
  {
    id: "sto-3g",
    label: "STO-3G",
    description: "Minimal basis",
    family: "minimal",
    recommended: true,
    supported_elements: [],
  },
];

interface MoleculeSectionProps {
  molecules: MoleculeResponse[];
  loading?: boolean;
  value: string | null;
  onChange: (val: string) => void;
  basisSetOverride: string;
  onBasisSetChange: (val: string) => void;
  disabled?: boolean;
  incompatibleIds: Map<string, string>;
  error?: string;
}

export function MoleculeSection({
  molecules,
  loading = false,
  value,
  onChange,
  basisSetOverride,
  onBasisSetChange,
  disabled,
  incompatibleIds,
  error,
}: MoleculeSectionProps) {
  const [basisOptions, setBasisOptions] = useState<BasisSetMetadata[]>(FALLBACK_BASIS_OPTIONS);
  const [basisDefault, setBasisDefault] = useState(FALLBACK_BASIS_SET);
  const selected = useMemo(() => molecules.find((m) => m.id === value), [molecules, value]);
  const defaultBasisSet = selected?.basis_set?.trim() || basisDefault;
  const basisIds = useMemo(() => new Set(basisOptions.map((option) => option.id)), [basisOptions]);
  const selectedPreset = basisIds.has(basisSetOverride) ? basisSetOverride : "";
  const basisSetValue = selectedPreset.length > 0 ? selectedPreset : DEFAULT_BASIS_SET_VALUE;
  const presetOptions = basisOptions.filter((option) => option.id !== defaultBasisSet);

  useEffect(() => {
    let cancelled = false;
    void fetchBasisSets()
      .then((response) => {
        if (cancelled) return;
        setBasisOptions(response.basis_sets);
        setBasisDefault(response.default_basis_set || FALLBACK_BASIS_SET);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(12rem,18rem)]">
      <div className="flex flex-col gap-4">
        <FormField
          label="Molecule"
          htmlFor="molecule-combobox"
          required
          error={error}
          help={{
            short: "Choose the molecular geometry and default basis set to start from.",
            anchor: "molecule",
          }}
        >
          <MoleculeCombobox
            id="molecule-combobox"
            molecules={molecules}
            value={value ?? ""}
            onChange={onChange}
            loading={loading}
            disabled={disabled || loading}
            incompatibleIds={incompatibleIds}
          />
        </FormField>

        <div className="flex min-h-[2rem] flex-wrap items-center gap-2">
          {selected && (
            <>
              <Badge variant="outline" className="font-mono text-xs">
                {selected.atoms.length} atoms
              </Badge>
              {selected.active_space && (
                <Badge variant="outline" className="font-mono text-xs">
                  {selected.active_space.n_electrons}e / {selected.active_space.n_orbitals}o
                </Badge>
              )}
              <Badge variant="outline" className="text-xs">
                {selected.multiplicity === 1 ? "singlet" : `multiplicity ${selected.multiplicity}`}
              </Badge>
              <Badge variant="outline" className="font-mono text-xs">
                {defaultBasisSet}
              </Badge>
              {selected.eligibility && (
                <Badge
                  variant={selected.eligibility.selectable ? "secondary" : "destructive"}
                  className="text-xs"
                  title={selected.eligibility.reason ?? selected.eligibility.label}
                >
                  {selected.eligibility.label}
                </Badge>
              )}
              {selected.eligibility?.capability_labels.slice(0, 2).map((label) => (
                <Badge key={label} variant="outline" className="text-xs">
                  {label}
                </Badge>
              ))}
              <Link
                to="/molecules/$moleculeId"
                params={{ moleculeId: selected.id }}
                state={(prev) => ({ ...prev, __source: "run-create-molecule-info" })}
                className="text-sm font-medium text-primary transition-colors hover:text-primary/80 hover:underline"
              >
                View molecule info
              </Link>
            </>
          )}
        </div>

        <FormField
          label="Basis Set"
          htmlFor="basis-set-select"
          help={{
            short:
              "Basis sets define the orbital functions used to approximate the molecule's wavefunction.",
            anchor: "basis_set",
            href: "/info/components/basis-sets",
          }}
        >
          <Select
            value={basisSetValue}
            onValueChange={(nextValue) => {
              if (nextValue === DEFAULT_BASIS_SET_VALUE) {
                onBasisSetChange("");
                return;
              }

              onBasisSetChange(nextValue);
            }}
          >
            <SelectTrigger id="basis-set-select" className="w-full" disabled={disabled}>
              <SelectValue placeholder={defaultBasisSet} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DEFAULT_BASIS_SET_VALUE}>{defaultBasisSet}</SelectItem>
              {presetOptions.map((preset) => (
                <SelectItem key={preset.id} value={preset.id}>
                  {preset.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      </div>

      <MoleculePreviewCard molecule={selected} loading={loading} />
    </div>
  );
}

function MoleculePreviewCard({
  molecule,
  loading,
}: {
  molecule: MoleculeResponse | undefined;
  loading: boolean;
}) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  let content = (
    <div className="flex h-36 w-full items-center justify-center rounded-lg border border-dashed border-border/80 bg-surface-raised/70 px-4 text-center text-sm text-muted-foreground dark:bg-card/40">
      Select a molecule to preview its 2D structure.
    </div>
  );

  if (loading) {
    content = (
      <div className="flex h-36 w-full items-center justify-center rounded-lg border border-dashed border-border/80 bg-surface-raised/70 px-4 text-center text-sm text-muted-foreground dark:bg-card/40">
        Loading molecule library...
      </div>
    );
  } else if (molecule) {
    content = (
      <MoleculeViewer2D
        atoms={molecule.atoms}
        showBonds
        isDark={isDark}
        className="h-36 rounded-lg border border-border/60"
      />
    );
  }

  return (
    <aside
      className={cn(
        "flex min-h-[10rem] items-center justify-center overflow-hidden rounded-xl border p-2",
        "border-border/85 bg-card shadow-[var(--shadow-elevation-raised)]",
      )}
    >
      {content}
    </aside>
  );
}
