import { Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent } from "@/components/ui/card";
import type { MoleculeResponse } from "@/types/run";
import { FullscreenPanel } from "./fullscreen-panel";
import { PanelCard } from "./panel-card";
import { downloadXyz } from "./use-molecule-viewer";

function AtomCoordinatesTable({
  molecule,
  compact,
}: {
  readonly molecule: MoleculeResponse;
  readonly compact?: boolean;
}) {
  const rowClassName = compact
    ? "grid grid-cols-[1.5rem_3rem_1fr_1fr_1fr] gap-3 items-center px-3 py-1.5 border-b last:border-0 hover:bg-muted/40 transition-colors"
    : "grid grid-cols-[2rem_3rem_1fr_1fr_1fr] gap-3 items-center px-4 py-2 border-b hover:bg-muted/30 transition-colors";
  const headerClassName = compact
    ? "grid grid-cols-[1.5rem_3rem_1fr_1fr_1fr] gap-3 items-center px-3 py-2 border-b bg-muted/40 sticky top-0 z-10"
    : "grid grid-cols-[2rem_3rem_1fr_1fr_1fr] gap-3 items-center px-4 py-2 border-b bg-muted/40 sticky top-0 z-10";

  return (
    <table aria-label={compact ? "Atom coordinates" : "Full atom coordinates"} className="w-full">
      <thead>
        <tr className={headerClassName}>
          {["#", "Sym", "X (Å)", "Y (Å)", "Z (Å)"].map((h) => (
            <th
              key={h}
              className="text-xs font-medium text-muted-foreground uppercase tracking-wide"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {molecule.atoms.map((atom, idx) => (
          <tr key={`${atom.symbol}-${atom.x}-${atom.y}-${atom.z}`} className={rowClassName}>
            <td
              className={
                compact ? "text-xs text-muted-foreground tabular-nums" : "text-xs font-mono"
              }
            >
              {idx + 1}
            </td>
            <td className={compact ? "text-sm font-medium" : "font-semibold"}>{atom.symbol}</td>
            <td className="text-xs font-mono tabular-nums">
              {compact ? atom.x.toFixed(3) : atom.x.toFixed(6)}
            </td>
            <td className="text-xs font-mono tabular-nums">
              {compact ? atom.y.toFixed(3) : atom.y.toFixed(6)}
            </td>
            <td className="text-xs font-mono tabular-nums">
              {compact ? atom.z.toFixed(3) : atom.z.toFixed(6)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MoleculeAtomsFullscreen({
  molecule,
  open,
  onClose,
}: {
  readonly molecule: MoleculeResponse;
  readonly open: boolean;
  readonly onClose: () => void;
}) {
  return (
    <FullscreenPanel
      open={open}
      onClose={onClose}
      title="Atom Coordinates"
      headerActions={<DownloadXyzButton molecule={molecule} />}
    >
      <div className="border rounded-md">
        <AtomCoordinatesTable molecule={molecule} />
      </div>
    </FullscreenPanel>
  );
}

export function MoleculeAtomsCard({
  molecule,
  onExpand,
  editMode,
}: {
  readonly molecule: MoleculeResponse;
  readonly onExpand: () => void;
  readonly editMode: boolean;
}) {
  return (
    <PanelCard
      title="Atom Coordinates"
      onExpand={onExpand}
      editMode={editMode}
      badge={
        <Badge variant="secondary" className="font-mono tabular-nums">
          {molecule.atoms.length}
        </Badge>
      }
      headerRight={<DownloadXyzButton molecule={molecule} />}
    >
      <CardContent className="p-0 flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="border-t h-full overflow-y-auto flex-1">
          <AtomCoordinatesTable molecule={molecule} compact />
        </div>
      </CardContent>
    </PanelCard>
  );
}

function DownloadXyzButton({ molecule }: { readonly molecule: MoleculeResponse }) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="size-8"
      onClick={() => downloadXyz(molecule.name, molecule.atoms)}
      aria-label="Download XYZ coordinates"
      title="Download XYZ coordinates"
    >
      <Download className="size-3.5" />
    </Button>
  );
}
