import { useRef, type RefObject } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardContent } from "@/components/ui/card";
import type { MoleculeResponse } from "@/types/run";
import { MoleculeViewer2D } from "@/components/molecules/molecule-viewer-2d";
import { MoleculeViewer3D } from "@/components/molecules/molecule-viewer-3d";
import type { MoleculeViewer3DRef } from "@/components/molecules/molecule-viewer-3d";
import { FullscreenPanel } from "./fullscreen-panel";
import { PanelCard } from "./panel-card";
import { downloadViewerImage } from "./use-molecule-viewer";
import { ViewerToolbar } from "./viewer-toolbar";
import type { ViewMode, ViewerStyle } from "./viewer-toolbar";

interface ViewerPreferencesForPanel {
  readonly viewMode: ViewMode;
  readonly viewerStyle: ViewerStyle;
  readonly showBonds: boolean;
}

interface MoleculeViewerPanelProps {
  readonly molecule: MoleculeResponse;
  readonly preferences: ViewerPreferencesForPanel;
  readonly isDark: boolean;
  readonly viewer3DRef: RefObject<MoleculeViewer3DRef | null>;
  readonly onExpand: () => void;
  readonly editMode: boolean;
  readonly onViewModeChange: (mode: ViewMode) => void;
  readonly onViewerStyleChange: (style: ViewerStyle) => void;
  readonly onShowBondsChange: (show: boolean) => void;
}

interface ViewerActionsProps extends Omit<
  MoleculeViewerPanelProps,
  "isDark" | "onExpand" | "editMode"
> {
  readonly viewerContainerRef: RefObject<HTMLDivElement | null>;
}

function ViewerActions({
  molecule,
  preferences,
  viewer3DRef,
  viewerContainerRef,
  onViewModeChange,
  onViewerStyleChange,
  onShowBondsChange,
}: ViewerActionsProps) {
  const exportLabel =
    preferences.viewMode === "3d" ? "Download 3D structure image" : "Download 2D structure image";

  return (
    <div className="flex items-center gap-2 shrink-0">
      <Button
        variant="outline"
        size="icon"
        className="size-8"
        onClick={() =>
          downloadViewerImage(molecule.name, preferences.viewMode, viewerContainerRef.current)
        }
        aria-label={exportLabel}
        title={exportLabel}
      >
        <Download className="size-3.5" />
      </Button>
      <ViewerToolbar
        viewMode={preferences.viewMode}
        onViewModeChange={onViewModeChange}
        viewerStyle={preferences.viewerStyle}
        onViewerStyleChange={onViewerStyleChange}
        showBonds={preferences.showBonds}
        onShowBondsChange={onShowBondsChange}
        onResetCamera={() => viewer3DRef.current?.resetCamera()}
      />
    </div>
  );
}

function ViewerCanvas({
  molecule,
  preferences,
  isDark,
  viewer3DRef,
  className,
  containerRef,
}: Pick<MoleculeViewerPanelProps, "molecule" | "preferences" | "isDark" | "viewer3DRef"> & {
  readonly className: string;
  readonly containerRef: RefObject<HTMLDivElement | null>;
}) {
  const viewer =
    preferences.viewMode === "3d" ? (
      <MoleculeViewer3D
        ref={viewer3DRef}
        atoms={molecule.atoms}
        style={preferences.viewerStyle}
        showBonds={preferences.showBonds}
        isDark={isDark}
        className={className}
      />
    ) : (
      <MoleculeViewer2D
        atoms={molecule.atoms}
        showBonds={preferences.showBonds}
        isDark={isDark}
        className={className}
      />
    );

  return (
    <div ref={containerRef} className="h-full min-h-0">
      {viewer}
    </div>
  );
}

export function MoleculeViewerFullscreen(
  props: Omit<MoleculeViewerPanelProps, "onExpand" | "editMode"> & {
    readonly open: boolean;
    readonly onClose: () => void;
  },
) {
  const { molecule, preferences, isDark, viewer3DRef, open, onClose, ...actionsProps } = props;
  const viewerContainerRef = useRef<HTMLDivElement>(null);
  const panelProps = { ...actionsProps, molecule, preferences, viewer3DRef, viewerContainerRef };

  return (
    <FullscreenPanel
      open={open}
      onClose={onClose}
      title={`${molecule.name} — ${preferences.viewMode === "3d" ? "3D" : "2D"} Structure`}
      headerActions={<ViewerActions {...panelProps} />}
    >
      <div className="h-full">
        <ViewerCanvas
          molecule={molecule}
          preferences={preferences}
          isDark={isDark}
          viewer3DRef={viewer3DRef}
          containerRef={viewerContainerRef}
          className="h-full"
        />
      </div>
    </FullscreenPanel>
  );
}

export function MoleculeViewerPanel(props: MoleculeViewerPanelProps) {
  const { preferences, isDark, molecule, viewer3DRef, onExpand, editMode, ...actionsProps } = props;
  const viewerContainerRef = useRef<HTMLDivElement>(null);
  const panelProps = { ...actionsProps, molecule, preferences, viewer3DRef, viewerContainerRef };

  return (
    <PanelCard
      title={preferences.viewMode === "3d" ? "3D Structure" : "2D Structure"}
      onExpand={onExpand}
      editMode={editMode}
      headerRight={<ViewerActions {...panelProps} />}
    >
      <CardContent className="p-0 flex-1 min-h-0">
        <ViewerCanvas
          molecule={molecule}
          preferences={preferences}
          isDark={isDark}
          viewer3DRef={viewer3DRef}
          containerRef={viewerContainerRef}
          className="rounded-b-lg overflow-hidden h-full"
        />
      </CardContent>
    </PanelCard>
  );
}
