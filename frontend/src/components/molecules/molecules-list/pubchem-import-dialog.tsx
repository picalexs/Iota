import { ArrowLeft, FileText, Search, Upload, X } from "lucide-react";

import { MoleculeViewer2D } from "@/components/molecules/molecule-viewer-2d";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { shouldUseSpinner } from "@/utils/loading-policy";
import type { MoleculeImportPreviewResponse } from "@/types/run";
import type { usePubChemImport } from "./use-pubchem-import";

type PubChemImportState = ReturnType<typeof usePubChemImport>;

export function PubChemImportDialog({ importState }: { readonly importState: PubChemImportState }) {
  return (
    <Dialog
      open={importState.dialogOpen}
      onOpenChange={(open) => {
        importState.setDialogOpen(open);
        if (open) return;
        importState.reset();
      }}
    >
      <DialogContent
        showCloseButton={false}
        className={cn(
          "fixed left-1/2 top-1/2 z-50 max-h-[92vh] w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg p-6 duration-200",
          "data-[state=open]:animate-in data-[state=closed]:animate-out",
          "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          "data-[state=closed]:slide-out-to-top-[52%]",
          "data-[state=open]:slide-in-from-top-[52%]",
        )}
      >
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-2">
            <DialogTitle className="text-lg font-semibold leading-none">
              Import Molecule
            </DialogTitle>
            <DialogDescription className="sr-only">
              Search PubChem or paste XYZ coordinates to preview and import a molecule.
            </DialogDescription>
            <button
              onClick={importState.close}
              className="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none"
              disabled={importState.importing}
              type="button"
              aria-label="Close dialog"
            >
              <X className="size-4" />
              <span className="sr-only">Close</span>
            </button>
          </div>

          <ImportModeTabs importState={importState} />

          {importState.mode === "pubchem" && importState.step === "search" && (
            <ImportSearchStep importState={importState} />
          )}
          {importState.mode === "pubchem" &&
            importState.step === "configure" &&
            importState.selectedCandidate && <ImportConfigureStep importState={importState} />}
          {importState.mode === "xyz" && <XyzImportStep importState={importState} />}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ImportModeTabs({ importState }: { readonly importState: PubChemImportState }) {
  return (
    <div className="grid grid-cols-2 gap-2 rounded-md bg-muted p-1">
      <button
        type="button"
        onClick={() => importState.setMode("pubchem")}
        className={cn(
          "inline-flex h-8 items-center justify-center gap-2 rounded-sm text-xs font-medium transition-colors",
          importState.mode === "pubchem"
            ? "border border-border/80 bg-surface-overlay text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
        aria-pressed={importState.mode === "pubchem"}
      >
        <Search className="size-3.5" />
        PubChem
      </button>
      <button
        type="button"
        onClick={() => importState.setMode("xyz")}
        className={cn(
          "inline-flex h-8 items-center justify-center gap-2 rounded-sm text-xs font-medium transition-colors",
          importState.mode === "xyz"
            ? "border border-border/80 bg-surface-overlay text-foreground"
            : "text-muted-foreground hover:text-foreground",
        )}
        aria-pressed={importState.mode === "xyz"}
      >
        <FileText className="size-3.5" />
        XYZ
      </button>
    </div>
  );
}

function ImportSearchStep({ importState }: { readonly importState: PubChemImportState }) {
  return (
    <>
      <div className="flex gap-2">
        <Input
          placeholder="Type to search"
          value={importState.query}
          onChange={(event) => {
            importState.setQuery(event.target.value);
            importState.setSearchError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !importState.searching) void importState.search();
          }}
          disabled={importState.searching}
          aria-label="Compound name to search"
        />
        <Button
          onClick={() => void importState.search()}
          disabled={importState.searching || importState.query.trim().length === 0}
        >
          {importState.searching ? (
            <SearchSpinner />
          ) : (
            <>
              <Search className="size-4" />
              Search
            </>
          )}
        </Button>
      </div>

      {importState.searchError && (
        <p role="alert" className="text-destructive text-xs">
          {importState.searchError}
        </p>
      )}

      {importState.searching && importState.searchResults.length === 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {shouldUseSpinner("search") && (
            <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          )}
          Searching…
        </div>
      )}

      {importState.searchResults.length > 0 && <SearchResults importState={importState} />}
    </>
  );
}

function SearchSpinner() {
  return (
    <>
      {shouldUseSpinner("search") && (
        <span className="mr-2 size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      Searching…
    </>
  );
}

function SearchResults({ importState }: { readonly importState: PubChemImportState }) {
  return (
    <>
      {importState.searchResultsUpdating && (
        <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
          {shouldUseSpinner("search") && (
            <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
          )}
          <span>Updating results…</span>
        </div>
      )}
      <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded-md border">
        {importState.searchResults.map((result) => (
          <button
            key={result.name}
            type="button"
            onClick={() => importState.selectCandidate(result)}
            className="flex flex-col items-start border-b px-3 py-2 text-left transition-colors last:border-0 hover:bg-accent/60"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{result.name}</span>
              {result.cid != null && (
                <Badge variant="outline" className="h-4 px-1 font-mono text-xs">
                  CID {result.cid}
                </Badge>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {result.iupac_name}
              {result.formula ? ` · ${result.formula}` : ""}
            </span>
          </button>
        ))}
      </div>
    </>
  );
}

function ImportConfigureStep({ importState }: { readonly importState: PubChemImportState }) {
  const actionLabel =
    importState.preview?.commit_action === "reuse" ? "Open Molecule" : "Import Molecule";

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="import-display-name" className="text-sm font-medium">
          Save as name
        </label>
        <Input
          id="import-display-name"
          value={importState.displayName}
          onChange={(event) => importState.setDisplayName(event.target.value)}
          disabled={importState.importing}
          aria-label="Display name for imported molecule"
        />
      </div>

      <ImportPreviewCard preview={importState.preview} previewing={importState.previewing} />

      {importState.importError && (
        <p role="alert" className="text-destructive text-xs">
          {importState.importError}
        </p>
      )}

      <div className="flex justify-between gap-2 pt-1">
        <Button
          variant="outline"
          onClick={() => {
            importState.setStep("search");
            importState.setImportError(null);
          }}
          disabled={importState.importing}
        >
          <ArrowLeft className="mr-1 size-3.5" />
          Back
        </Button>
        <Button
          onClick={() => void importState.importSelected()}
          disabled={
            importState.importing ||
            importState.previewing ||
            importState.displayName.trim().length === 0
          }
        >
          {importState.importing ? (
            <MutationSpinner label="Importing…" />
          ) : (
            <>
              <Upload className="size-4" />
              {actionLabel}
            </>
          )}
        </Button>
      </div>
    </>
  );
}

function XyzImportStep({ importState }: { readonly importState: PubChemImportState }) {
  const canImport =
    importState.xyzName.trim().length > 0 &&
    importState.xyzText.trim().length > 0 &&
    importState.preview?.commit_action !== "name_conflict";

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_5rem_5rem]">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="xyz-import-name" className="text-sm font-medium">
            Save as name
          </label>
          <Input
            id="xyz-import-name"
            value={importState.xyzName}
            onChange={(event) => {
              importState.setXyzName(event.target.value);
              importState.setImportError(null);
            }}
            disabled={importState.importing}
            aria-label="XYZ molecule name"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="xyz-import-charge" className="text-sm font-medium">
            Charge
          </label>
          <Input
            id="xyz-import-charge"
            type="number"
            inputMode="numeric"
            value={importState.xyzCharge}
            onChange={(event) => importState.setXyzCharge(event.target.value)}
            disabled={importState.importing}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="xyz-import-multiplicity" className="text-sm font-medium">
            Mult.
          </label>
          <Input
            id="xyz-import-multiplicity"
            type="number"
            inputMode="numeric"
            min={1}
            value={importState.xyzMultiplicity}
            onChange={(event) => importState.setXyzMultiplicity(event.target.value)}
            disabled={importState.importing}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="xyz-import-text" className="text-sm font-medium">
          XYZ coordinates
        </label>
        <Textarea
          id="xyz-import-text"
          value={importState.xyzText}
          onChange={(event) => {
            importState.setXyzText(event.target.value);
            importState.setImportError(null);
          }}
          className="min-h-40 font-mono text-xs"
          placeholder={"3\nwater\nO 0.000 0.000 0.000\nH 0.757 0.586 0.000\nH -0.757 0.586 0.000"}
          disabled={importState.importing}
          aria-label="XYZ coordinates"
        />
      </div>

      <ImportPreviewCard preview={importState.preview} previewing={importState.previewing} />

      {importState.importError && (
        <p role="alert" className="text-destructive text-xs">
          {importState.importError}
        </p>
      )}

      <div className="flex justify-end gap-2 pt-1">
        <Button
          variant="outline"
          onClick={() => void importState.previewXyz()}
          disabled={importState.previewing || importState.importing || !importState.xyzText.trim()}
        >
          {importState.previewing ? (
            <MutationSpinner label="Previewing…" />
          ) : (
            <>
              <Search className="size-4" />
              Preview
            </>
          )}
        </Button>
        <Button
          onClick={() => void importState.importXyz()}
          disabled={importState.importing || importState.previewing || !canImport}
        >
          {importState.importing ? (
            <MutationSpinner label="Importing…" />
          ) : (
            <>
              <Upload className="size-4" />
              Import Molecule
            </>
          )}
        </Button>
      </div>
    </>
  );
}

function ImportPreviewCard({
  preview,
  previewing,
}: {
  readonly preview: MoleculeImportPreviewResponse | null;
  readonly previewing: boolean;
}) {
  const systemPrefersDark =
    typeof globalThis.matchMedia === "function" &&
    globalThis.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark =
    globalThis.document?.documentElement.classList.contains("dark") === true || systemPrefersDark;

  if (previewing && !preview) {
    return (
      <div className="flex min-h-28 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        {shouldUseSpinner("search") && (
          <span className="mr-2 size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        )}
        Building preview…
      </div>
    );
  }

  if (!preview) return null;

  const activeSpace = preview.active_space
    ? `${preview.active_space.n_electrons}e / ${preview.active_space.n_orbitals}o`
    : "active space unset";
  let actionText = "Ready to create a new library molecule.";
  if (preview.commit_action === "reuse") {
    actionText = `Will open existing molecule "${preview.existing_molecule_name ?? preview.name}".`;
  } else if (preview.commit_action === "name_conflict") {
    const existingName = preview.existing_molecule_name
      ? ` as "${preview.existing_molecule_name}"`
      : "";
    actionText = `Name already exists${existingName}.`;
  }

  return (
    <div className="grid gap-3 rounded-md border bg-card p-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
      <MoleculeViewer2D
        atoms={preview.atoms}
        showBonds
        isDark={isDark}
        className="h-32 rounded-md border border-border/70"
      />
      <div className="min-w-0 space-y-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold" title={preview.name}>
            {preview.name}
          </p>
          <p className="text-xs text-muted-foreground">{actionText}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className="font-mono text-xs">
            {preview.formula}
          </Badge>
          <Badge variant="outline" className="font-mono text-xs">
            {preview.atom_count} atoms
          </Badge>
          <Badge variant="outline" className="font-mono text-xs">
            q={preview.charge}
          </Badge>
          <Badge variant="outline" className="font-mono text-xs">
            m={preview.multiplicity}
          </Badge>
          <Badge variant="outline" className="font-mono text-xs">
            {activeSpace}
          </Badge>
          <Badge
            variant={preview.eligibility.selectable ? "secondary" : "destructive"}
            className="text-xs"
          >
            {preview.eligibility.label}
          </Badge>
          {preview.eligibility.capability_labels.map((label) => (
            <Badge key={label} variant="outline" className="text-xs">
              {label}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

function MutationSpinner({ label }: { readonly label: string }) {
  return (
    <>
      {shouldUseSpinner("mutation") && (
        <span className="mr-2 size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {label}
    </>
  );
}
