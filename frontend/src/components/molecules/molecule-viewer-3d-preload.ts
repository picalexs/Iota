let viewerModulePromise: Promise<typeof import("3dmol")> | null = null;

function loadViewerModule() {
  viewerModulePromise ??= import("3dmol");
  return viewerModulePromise;
}

export function preloadMoleculeViewer3D() {
  void loadViewerModule();
}
