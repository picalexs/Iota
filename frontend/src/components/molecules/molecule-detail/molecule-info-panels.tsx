import { useState } from "react";
import { Check, ChevronDown, ChevronUp, Copy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CardContent } from "@/components/ui/card";
import type { MoleculeResponse } from "@/types/run";
import { FullscreenPanel } from "./fullscreen-panel";
import { DetailRow, MoleculePropertiesPanel } from "./molecule-properties-panel";
import { PanelCard } from "./panel-card";

function CopyButton({ text }: { readonly text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard not available
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleCopy()}
      aria-label="Copy to clipboard"
      className="ml-1.5 inline-flex items-center text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
    </button>
  );
}

function MonoRow({
  label,
  value,
}: {
  readonly label: string;
  readonly value: string | null | undefined;
}) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
      <span className="text-xs font-mono break-all leading-relaxed">
        {value}
        <CopyButton text={value} />
      </span>
    </div>
  );
}

export function MoleculePropertiesFullscreen({
  molecule,
  formula,
  molecularWeight,
  bondCount,
  open,
  onClose,
}: {
  readonly molecule: MoleculeResponse;
  readonly formula: string;
  readonly molecularWeight: number;
  readonly bondCount: number;
  readonly open: boolean;
  readonly onClose: () => void;
}) {
  return (
    <FullscreenPanel open={open} onClose={onClose} title="Properties">
      <MoleculePropertiesPanel
        molecule={molecule}
        formula={formula}
        molecularWeight={molecularWeight}
        bondCount={bondCount}
      />
    </FullscreenPanel>
  );
}

export function MoleculePropertiesCard({
  molecule,
  formula,
  molecularWeight,
  bondCount,
  onExpand,
  editMode,
}: {
  readonly molecule: MoleculeResponse;
  readonly formula: string;
  readonly molecularWeight: number;
  readonly bondCount: number;
  readonly onExpand: () => void;
  readonly editMode: boolean;
}) {
  return (
    <PanelCard title="Properties" onExpand={onExpand} editMode={editMode}>
      <CardContent className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0 px-4 py-3">
        <MoleculePropertiesPanel
          molecule={molecule}
          formula={formula}
          molecularWeight={molecularWeight}
          bondCount={bondCount}
          className="contents"
        />
      </CardContent>
    </PanelCard>
  );
}

export function MoleculeDescriptionFullscreen({
  molecule,
  open,
  onClose,
}: {
  readonly molecule: MoleculeResponse;
  readonly open: boolean;
  readonly onClose: () => void;
}) {
  return (
    <FullscreenPanel open={open} onClose={onClose} title="Description">
      <div className="space-y-4 text-sm">
        {molecule.iupac_name && (
          <div>
            <h3 className="font-semibold">IUPAC Name</h3>
            <p className="text-muted-foreground mt-1">{molecule.iupac_name}</p>
          </div>
        )}
        {molecule.description && (
          <div>
            <h3 className="font-semibold">Description</h3>
            <p className="text-muted-foreground mt-1 leading-relaxed">{molecule.description}</p>
          </div>
        )}
        {molecule.synonyms && molecule.synonyms.length > 0 && (
          <div>
            <h3 className="font-semibold">Other Names</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {molecule.synonyms.map((s) => (
                <Badge key={s} variant="outline" className="text-xs font-normal">
                  {s}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </FullscreenPanel>
  );
}

export function MoleculeDescriptionCard({
  molecule,
  showAllSynonyms,
  descExpanded,
  onShowAllSynonymsChange,
  onDescExpandedChange,
  onExpand,
  editMode,
}: {
  readonly molecule: MoleculeResponse;
  readonly showAllSynonyms: boolean;
  readonly descExpanded: boolean;
  readonly onShowAllSynonymsChange: (show: boolean) => void;
  readonly onDescExpandedChange: (expanded: boolean) => void;
  readonly onExpand: () => void;
  readonly editMode: boolean;
}) {
  const synonyms = molecule.synonyms ?? [];
  const visibleSynonyms = showAllSynonyms ? synonyms : synonyms.slice(0, 5);
  const hiddenCount = synonyms.length - 5;
  const truncateAt = 400;
  const description = molecule.description;
  const isLong = description != null && description.length > truncateAt;
  const shouldTruncateDescription = isLong && descExpanded === false;
  const displayText = shouldTruncateDescription
    ? `${description.slice(0, truncateAt).trimEnd()}…`
    : description;

  return (
    <PanelCard title="Description" onExpand={onExpand} editMode={editMode}>
      <CardContent className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0 px-4 py-3">
        {molecule.iupac_name && (
          <DetailRow
            label="IUPAC Name"
            value={<span className="font-medium">{molecule.iupac_name}</span>}
          />
        )}
        {molecule.description && (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Description
            </span>
            <p className="text-sm leading-relaxed">{displayText}</p>
            {isLong && (
              <button
                type="button"
                onClick={() => onDescExpandedChange(!descExpanded)}
                className="flex items-center gap-1 text-xs text-primary hover:underline self-start"
              >
                {descExpanded ? (
                  <>
                    <ChevronUp className="size-3" /> Show less
                  </>
                ) : (
                  <>
                    <ChevronDown className="size-3" /> Show more
                  </>
                )}
              </button>
            )}
          </div>
        )}
        {synonyms.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Synonyms
            </span>
            <div className="flex flex-wrap gap-1.5">
              {visibleSynonyms.map((s) => (
                <Badge key={s} variant="outline" className="text-xs font-normal">
                  {s}
                </Badge>
              ))}
              {!showAllSynonyms && hiddenCount > 0 && (
                <button
                  type="button"
                  onClick={() => onShowAllSynonymsChange(true)}
                  className="text-xs text-primary hover:underline"
                >
                  +{hiddenCount} more
                </button>
              )}
              {showAllSynonyms && hiddenCount > 0 && (
                <button
                  type="button"
                  onClick={() => onShowAllSynonymsChange(false)}
                  className="text-xs text-primary hover:underline"
                >
                  Show less
                </button>
              )}
            </div>
          </div>
        )}
        {!molecule.description && !molecule.iupac_name && synonyms.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No description available.</p>
        )}
      </CardContent>
    </PanelCard>
  );
}

export function MoleculeIdentifiersFullscreen({
  molecule,
  open,
  onClose,
}: {
  readonly molecule: MoleculeResponse;
  readonly open: boolean;
  readonly onClose: () => void;
}) {
  return (
    <FullscreenPanel open={open} onClose={onClose} title="Identifiers">
      <div className="flex flex-col gap-3">
        {molecule.pubchem_cid != null && (
          <DetailRow
            label="PubChem CID"
            value={<span className="font-mono">{molecule.pubchem_cid}</span>}
          />
        )}
        <MonoRow label="SMILES" value={molecule.smiles} />
        <MonoRow label="InChI" value={molecule.inchi} />
        <MonoRow label="InChIKey" value={molecule.inchi_key} />
      </div>
    </FullscreenPanel>
  );
}

export function MoleculeIdentifiersCard({
  molecule,
  onExpand,
  editMode,
}: {
  readonly molecule: MoleculeResponse;
  readonly onExpand: () => void;
  readonly editMode: boolean;
}) {
  const identifierRows =
    molecule.pubchem_cid == null ? null : (
      <>
        <DetailRow
          label="PubChem CID"
          value={<span className="font-mono">{molecule.pubchem_cid}</span>}
        />
        <MonoRow label="SMILES" value={molecule.smiles} />
        <MonoRow label="InChI" value={molecule.inchi} />
        <MonoRow label="InChIKey" value={molecule.inchi_key} />
      </>
    );

  return (
    <PanelCard title="Identifiers" onExpand={onExpand} editMode={editMode}>
      <CardContent className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0 px-4 py-3">
        {identifierRows ?? (
          <p className="text-sm text-muted-foreground italic">No identifiers available.</p>
        )}
      </CardContent>
    </PanelCard>
  );
}
