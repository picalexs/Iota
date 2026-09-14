import { Box, Eye, EyeOff, LayoutGrid, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type ViewMode = "2d" | "3d";
export type ViewerStyle = "ball-and-stick" | "space-filling" | "wireframe";

const STYLE_LABELS: Record<ViewerStyle, string> = {
  "ball-and-stick": "Ball & Stick",
  "space-filling": "Space Filling",
  wireframe: "Wireframe",
};
const VIEWER_STYLES: readonly ViewerStyle[] = ["ball-and-stick", "space-filling", "wireframe"];

function parseViewerStyle(value: string): ViewerStyle | null {
  switch (value) {
    case "ball-and-stick":
    case "space-filling":
    case "wireframe":
      return value;
    default:
      return null;
  }
}

interface ViewerToolbarProps {
  readonly viewMode: ViewMode;
  readonly onViewModeChange: (mode: ViewMode) => void;
  readonly viewerStyle: ViewerStyle;
  readonly onViewerStyleChange: (style: ViewerStyle) => void;
  readonly showBonds: boolean;
  readonly onShowBondsChange: (show: boolean) => void;
  readonly onResetCamera?: () => void;
}

export function ViewerToolbar({
  viewMode,
  onViewModeChange,
  viewerStyle,
  onViewerStyleChange,
  showBonds,
  onShowBondsChange,
  onResetCamera,
}: ViewerToolbarProps) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <div className="flex items-center rounded-md border overflow-hidden shrink-0">
        <Button
          variant={viewMode === "2d" ? "default" : "ghost"}
          size="sm"
          className="rounded-none border-0 h-8 px-3 gap-1.5"
          onClick={() => onViewModeChange("2d")}
          aria-pressed={viewMode === "2d"}
        >
          <LayoutGrid className="size-3.5" />
          2D
        </Button>
        <Button
          variant={viewMode === "3d" ? "default" : "ghost"}
          size="sm"
          className="rounded-none border-0 h-8 px-3 gap-1.5"
          onClick={() => onViewModeChange("3d")}
          aria-pressed={viewMode === "3d"}
        >
          <Box className="size-3.5" />
          3D
        </Button>
      </div>

      <Button
        variant="outline"
        size="sm"
        className="gap-1.5 shrink-0"
        onClick={() => onShowBondsChange(!showBonds)}
        aria-pressed={showBonds}
        aria-label={showBonds ? "Hide bonds" : "Show bonds"}
      >
        {showBonds ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5" />}
        <span>{showBonds ? "Bonds" : "No Bonds"}</span>
      </Button>

      {viewMode === "3d" && (
        <Select
          value={viewerStyle}
          onValueChange={(val) => {
            const nextStyle = parseViewerStyle(val);
            if (nextStyle != null) onViewerStyleChange(nextStyle);
          }}
        >
          <SelectTrigger size="sm" aria-label="Viewer style" className="w-32 shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VIEWER_STYLES.map((s) => (
              <SelectItem key={s} value={s}>
                {STYLE_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {viewMode === "3d" && onResetCamera && (
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 shrink-0"
          onClick={onResetCamera}
          aria-label="Reset camera view"
        >
          <RotateCcw className="size-3.5" />
          <span>Reset</span>
        </Button>
      )}
    </div>
  );
}
