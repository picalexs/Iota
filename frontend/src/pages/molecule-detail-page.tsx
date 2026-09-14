import { useEffect } from "react";
import { useLocation, useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { MoleculeDetail } from "@/components/molecules/molecule-detail";
import { preloadMoleculeViewer3D } from "@/components/molecules/molecule-viewer-3d-preload";
import { useSmartBack } from "@/hooks/use-smart-back";

export function MoleculeDetailPage() {
  const { moleculeId } = useParams({ from: "/molecules/$moleculeId" });
  const shouldGoToList = useLocation({
    select: (location) => {
      const state = location.state;
      if (!state || typeof state !== "object") {
        return false;
      }
      return (
        "__source" in state &&
        (state as Record<string, unknown>).__source === "run-create-molecule-info"
      );
    },
  });
  const goBack = useSmartBack({ to: "/molecules" }, { forceFallback: shouldGoToList });

  useEffect(() => {
    if (!moleculeId) return;
    preloadMoleculeViewer3D();
  }, [moleculeId]);

  if (!moleculeId) {
    return (
      <div className="w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-6">
        <div className="flex flex-col gap-6">
          <p role="alert" className="text-destructive text-sm">
            No molecule ID provided.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 overflow-x-hidden">
      <div className="flex flex-col gap-6">
        <button
          type="button"
          onClick={goBack}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
          aria-label="Go back"
        >
          <ChevronLeft className="size-4" />
          Back
        </button>
        <MoleculeDetail moleculeId={moleculeId} />
      </div>
    </div>
  );
}

export default MoleculeDetailPage;
