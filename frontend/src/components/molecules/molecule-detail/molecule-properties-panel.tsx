import type { ReactNode } from "react";
import type { MoleculeResponse } from "@/types/run";

export interface DetailRowProps {
  readonly label: string;
  readonly value: ReactNode;
}

export function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

interface MoleculePropertiesPanelProps {
  readonly molecule: MoleculeResponse;
  readonly formula: string;
  readonly molecularWeight: number;
  readonly bondCount: number;
  readonly className?: string;
}

export function MoleculePropertiesPanel({
  molecule,
  formula,
  molecularWeight,
  bondCount,
  className = "flex flex-col gap-3",
}: MoleculePropertiesPanelProps) {
  const frozenCore = molecule.active_space?.n_frozen_core;
  const frozenCoreLabel =
    typeof frozenCore === "string" ||
    typeof frozenCore === "number" ||
    typeof frozenCore === "boolean"
      ? `${frozenCore}`
      : null;
  let chargeLabel = String(molecule.charge);
  if (molecule.charge === 0) {
    chargeLabel = "Neutral (0)";
  } else if (molecule.charge > 0) {
    chargeLabel = `+${molecule.charge}`;
  }

  return (
    <div className={className}>
      <DetailRow label="Formula" value={<span className="font-mono">{formula || "—"}</span>} />
      <DetailRow label="Molecular Weight" value={`${molecularWeight.toFixed(3)} Da`} />
      <DetailRow label="Charge" value={chargeLabel} />
      <DetailRow label="Multiplicity" value={molecule.multiplicity} />
      <DetailRow label="Atoms" value={molecule.atoms.length} />
      <DetailRow label="Bonds (est.)" value={bondCount} />
      {molecule.active_space && (
        <div className="border-t pt-2 mt-1 flex flex-col gap-2">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Active Space
          </span>
          <DetailRow label="Electrons" value={molecule.active_space.n_electrons} />
          <DetailRow label="Orbitals" value={molecule.active_space.n_orbitals} />
          {frozenCoreLabel != null && <DetailRow label="Frozen Core" value={frozenCoreLabel} />}
        </div>
      )}
      <div className="border-t pt-2 mt-1 flex flex-col gap-2">
        <DetailRow label="Added" value={new Date(molecule.created_at).toLocaleString()} />
        <DetailRow label="Updated" value={new Date(molecule.updated_at).toLocaleString()} />
      </div>
    </div>
  );
}
