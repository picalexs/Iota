import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { GridLayout, verticalCompactor } from "react-grid-layout";
import { Edit2, ExternalLink, Lock, Plus, RotateCcw } from "lucide-react";
import { SkeletonCardGrid } from "@/components/ui/loading-skeleton-blocks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useGetMolecule } from "@/hooks";
import { ROW_HEIGHT, calculateResponsiveColumns } from "@/lib/responsive-columns";
import {
  MoleculeAtomsCard,
  MoleculeAtomsFullscreen,
} from "./molecule-detail/atom-coordinates-panel";
import {
  MoleculeDescriptionCard,
  MoleculeDescriptionFullscreen,
  MoleculeIdentifiersCard,
  MoleculeIdentifiersFullscreen,
  MoleculePropertiesCard,
  MoleculePropertiesFullscreen,
} from "./molecule-detail/molecule-info-panels";
import {
  MoleculeViewerFullscreen,
  MoleculeViewerPanel,
} from "./molecule-detail/molecule-viewer-panel";
import { useMoleculeGrid } from "./molecule-detail/use-molecule-grid";
import { useMoleculeViewer } from "./molecule-detail/use-molecule-viewer";
import { MoleculeDetailLoadingSkeleton } from "./molecule-detail-loading";

type FullscreenId = "viewer" | "properties" | "description" | "identifiers" | "atoms";

export interface MoleculeDetailProps {
  readonly moleculeId: string;
}

export function MoleculeDetail({ moleculeId }: MoleculeDetailProps) {
  const [editMode, setEditMode] = useState(false);
  const [expandedPanel, setExpandedPanel] = useState<FullscreenId | null>(null);
  const [showAllSynonyms, setShowAllSynonyms] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const moleculeQuery = useGetMolecule(moleculeId);
  const molecule = moleculeQuery.data ?? null;
  const loading = moleculeQuery.isLoading;
  const loadError = moleculeQuery.error instanceof Error ? moleculeQuery.error : null;
  const {
    bondCount,
    formula,
    isDark,
    mw,
    preferences,
    setGridLayout,
    setShowBonds,
    setViewerStyle,
    setViewMode,
    viewer3DRef,
  } = useMoleculeViewer(molecule);
  const {
    buildLayout,
    containerRef,
    containerWidth,
    handleGridDrag,
    handleGridDragStart,
    handleGridDragStop,
    handleLayoutChange,
    mounted,
    resetLayout,
  } = useMoleculeGrid({
    molecule,
    savedLayout: preferences.gridLayout,
    savedBreakpoint: preferences.layoutBreakpoint,
    setGridLayout,
  });

  return (
    <div
      data-testid="molecule-detail"
      className="flex flex-col gap-4 w-full overflow-x-hidden px-2 min-w-0"
    >
      {/* Keep the probe mounted so container width is available before data loads. */}
      <div ref={containerRef} className="w-full" />

      {loading && <MoleculeDetailLoadingSkeleton />}

      {loadError && (
        <PageErrorState
          {...getErrorPresentation(loadError, "this molecule")}
          onRetry={() => void moleculeQuery.refetch()}
        />
      )}

      {!loading && !loadError && molecule && (
        <>
          <div className="flex items-end justify-between gap-4 flex-wrap shrink-0">
            <div className="flex flex-col gap-1.5 min-w-0 flex-1">
              <h1 className="text-3xl font-bold tracking-tight">{molecule.name}</h1>
              <div className="flex items-center gap-2.5 flex-wrap">
                {formula && (
                  <Badge variant="secondary" className="font-mono">
                    {formula}
                  </Badge>
                )}
                {molecule.pubchem_cid != null && (
                  <Badge variant="outline" className="font-mono text-xs">
                    CID {molecule.pubchem_cid}
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              {molecule.pubchem_cid != null && (
                <a
                  href={`https://pubchem.ncbi.nlm.nih.gov/compound/${molecule.pubchem_cid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid="pubchem-link"
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline shrink-0"
                >
                  <ExternalLink className="size-3.5" />
                  View on PubChem
                </a>
              )}
              <Button asChild size="sm" className="gap-1.5 shrink-0 h-8 text-xs">
                <Link to="/runs/new" search={{ molecule_id: molecule.id }}>
                  <Plus className="size-3.5" />
                  New run
                </Link>
              </Button>
              <Button
                variant={editMode ? "default" : "outline"}
                size="sm"
                className="gap-1.5 shrink-0 h-8 text-xs"
                onClick={() => setEditMode((v) => !v)}
                aria-label={editMode ? "Lock layout" : "Edit layout"}
              >
                {editMode ? <Lock className="size-3.5" /> : <Edit2 className="size-3.5" />}
                {editMode ? "Lock" : "Edit layout"}
              </Button>
              {editMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1.5 shrink-0 h-8 text-xs text-muted-foreground"
                  onClick={resetLayout}
                  aria-label="Reset layout to defaults"
                >
                  <RotateCcw className="size-3.5" />
                  Reset
                </Button>
              )}
            </div>
          </div>

          <MoleculeViewerFullscreen
            open={expandedPanel === "viewer"}
            onClose={() => setExpandedPanel(null)}
            molecule={molecule}
            preferences={preferences}
            isDark={isDark}
            viewer3DRef={viewer3DRef}
            onViewModeChange={setViewMode}
            onViewerStyleChange={setViewerStyle}
            onShowBondsChange={setShowBonds}
          />
          <MoleculePropertiesFullscreen
            open={expandedPanel === "properties"}
            onClose={() => setExpandedPanel(null)}
            molecule={molecule}
            formula={formula}
            molecularWeight={mw}
            bondCount={bondCount}
          />
          <MoleculeDescriptionFullscreen
            open={expandedPanel === "description"}
            onClose={() => setExpandedPanel(null)}
            molecule={molecule}
          />
          <MoleculeIdentifiersFullscreen
            open={expandedPanel === "identifiers"}
            onClose={() => setExpandedPanel(null)}
            molecule={molecule}
          />
          <MoleculeAtomsFullscreen
            open={expandedPanel === "atoms"}
            onClose={() => setExpandedPanel(null)}
            molecule={molecule}
          />

          <div className="relative w-full overflow-x-hidden">
            {mounted ? (
              <GridLayout
                width={containerWidth}
                layout={buildLayout(containerWidth)}
                gridConfig={{
                  cols: calculateResponsiveColumns(containerWidth),
                  rowHeight: ROW_HEIGHT,
                  margin: [8, 8] as const,
                  containerPadding: [0, 0] as const,
                }}
                dragConfig={
                  editMode
                    ? { handle: ".drag-handle", bounded: true }
                    : { enabled: false, bounded: false }
                }
                resizeConfig={
                  editMode ? { handles: ["se"] as const } : { enabled: false, handles: [] as const }
                }
                compactor={verticalCompactor}
                onLayoutChange={(l) => {
                  if (editMode) handleLayoutChange(l);
                }}
                onDragStart={handleGridDragStart}
                onDrag={handleGridDrag}
                onDragStop={handleGridDragStop}
                autoSize
              >
                <div key="viewer">
                  <MoleculeViewerPanel
                    molecule={molecule}
                    preferences={preferences}
                    isDark={isDark}
                    viewer3DRef={viewer3DRef}
                    onExpand={() => setExpandedPanel("viewer")}
                    editMode={editMode}
                    onViewModeChange={setViewMode}
                    onViewerStyleChange={setViewerStyle}
                    onShowBondsChange={setShowBonds}
                  />
                </div>

                <div key="properties">
                  <MoleculePropertiesCard
                    molecule={molecule}
                    formula={formula}
                    molecularWeight={mw}
                    bondCount={bondCount}
                    onExpand={() => setExpandedPanel("properties")}
                    editMode={editMode}
                  />
                </div>

                <div key="description">
                  <MoleculeDescriptionCard
                    molecule={molecule}
                    showAllSynonyms={showAllSynonyms}
                    descExpanded={descExpanded}
                    onShowAllSynonymsChange={setShowAllSynonyms}
                    onDescExpandedChange={setDescExpanded}
                    onExpand={() => setExpandedPanel("description")}
                    editMode={editMode}
                  />
                </div>

                <div key="identifiers">
                  <MoleculeIdentifiersCard
                    molecule={molecule}
                    onExpand={() => setExpandedPanel("identifiers")}
                    editMode={editMode}
                  />
                </div>

                <div key="atoms">
                  <MoleculeAtomsCard
                    molecule={molecule}
                    onExpand={() => setExpandedPanel("atoms")}
                    editMode={editMode}
                  />
                </div>
              </GridLayout>
            ) : (
              <div className="space-y-4">
                <Skeleton className="h-80" />
                <SkeletonCardGrid cardCount={3} />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default MoleculeDetail;
