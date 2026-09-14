import { Link } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { DashboardTile } from "@/components/results/dashboard-tile";
import type { MoleculeResponse } from "@/types/run";

interface MoleculeTileProps {
  readonly molecule: MoleculeResponse | null;
  readonly moleculeId: string | null;
  readonly editMode?: boolean;
}

interface StatRowProps {
  readonly label: string;
  readonly value: React.ReactNode;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/40 py-1.5 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium">{value}</span>
    </div>
  );
}

function buildFormula(molecule: MoleculeResponse): string {
  const counts: Record<string, number> = {};
  for (const atom of molecule.atoms) {
    counts[atom.symbol] = (counts[atom.symbol] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([sym, n]) => (n === 1 ? sym : `${sym}${n}`))
    .join("");
}

function activeSpaceSummary(activeSpace: MoleculeResponse["active_space"]): string | null {
  if (activeSpace == null) {
    return null;
  }
  return `(${activeSpace.n_electrons}e, ${activeSpace.n_orbitals}o)`;
}

export function MoleculeTile({ molecule, moleculeId, editMode }: MoleculeTileProps) {
  const formula = molecule ? buildFormula(molecule) : null;
  const activeSpaceLabel = activeSpaceSummary(molecule?.active_space ?? null);

  return (
    <DashboardTile
      title="Molecule"
      helpText="Molecule used in this simulation run."
      editMode={editMode}
    >
      <div className="flex flex-col">
        <MoleculeTileBody
          molecule={molecule}
          moleculeId={moleculeId}
          formula={formula}
          activeSpaceLabel={activeSpaceLabel}
        />
      </div>
    </DashboardTile>
  );
}

function MoleculeTileBody({
  molecule,
  moleculeId,
  formula,
  activeSpaceLabel,
}: {
  readonly molecule: MoleculeResponse | null;
  readonly moleculeId: string | null;
  readonly formula: string | null;
  readonly activeSpaceLabel: string | null;
}) {
  if (!molecule || !moleculeId) {
    if (moleculeId) {
      return <p className="text-xs text-muted-foreground">Loading molecule…</p>;
    }
    return <p className="text-xs text-muted-foreground italic">No molecule linked to this run.</p>;
  }

  return (
    <>
      <div className="mb-2 flex items-center gap-2">
        <FlaskConical className="size-4 shrink-0 text-primary" />
        <Link
          to="/molecules/$moleculeId"
          params={{ moleculeId }}
          className="truncate text-sm font-semibold text-primary underline-offset-2 hover:underline"
        >
          {molecule.name}
        </Link>
      </div>
      {formula != null && (
        <StatRow label="Formula" value={<code className="font-mono">{formula}</code>} />
      )}
      {molecule.basis_set && <StatRow label="Basis set" value={molecule.basis_set} />}
      {molecule.charge !== 0 && <StatRow label="Charge" value={molecule.charge} />}
      {molecule.multiplicity !== 1 && (
        <StatRow label="Multiplicity" value={molecule.multiplicity} />
      )}
      {activeSpaceLabel && <StatRow label="Active space" value={activeSpaceLabel} />}
    </>
  );
}
