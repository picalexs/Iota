import type { ReactNode } from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PubChemImportDialog } from "./pubchem-import-dialog";
import type { usePubChemImport } from "./use-pubchem-import";

type PubChemImportState = ReturnType<typeof usePubChemImport>;

interface MoleculesToolbarProps {
  readonly searchQuery: string;
  readonly onSearchQueryChange: (value: string) => void;
  readonly importState: PubChemImportState;
  readonly actionSlot?: ReactNode;
}

export function MoleculesToolbar({
  searchQuery,
  onSearchQueryChange,
  importState,
  actionSlot,
}: MoleculesToolbarProps) {
  return (
    <>
      <PubChemImportDialog importState={importState} />

      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base font-semibold">Molecule Library</CardTitle>
        <div className="flex items-center gap-2">
          {actionSlot}
          <Button
            variant="outline"
            size="sm"
            onClick={() => importState.open()}
            aria-label="Import molecule from PubChem or XYZ"
          >
            <Download className="size-3.5" />
            Import Molecule
          </Button>
        </div>
      </CardHeader>

      <div className="px-4 pt-4 pb-3 flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            placeholder="Search molecules..."
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            className="sm:max-w-md"
            aria-label="Search molecules"
          />
        </div>
      </div>
    </>
  );
}
