/**
 * 3D Molecule Viewer Component
 * Renders a 3D molecular structure using 3Dmol.js
 */

import {
  useRef,
  useEffect,
  useCallback,
  forwardRef,
  useImperativeHandle,
  type RefObject,
} from "react";
import { logAppError } from "@/lib/app-logger";
import { atomsToXyz } from "@/lib/chemistry-utils";
import type { AtomSchema } from "@/types/run";

export interface MoleculeViewer3DProps {
  /** Array of atoms with symbol and coordinates */
  readonly atoms: AtomSchema[];
  /** Visual style for rendering (default: "ball-and-stick") */
  readonly style?: "ball-and-stick" | "space-filling" | "wireframe";
  /** Whether to show bonds (default: true) */
  readonly showBonds?: boolean;
  /** Whether to use dark mode background (default: false) */
  readonly isDark?: boolean;
  /** Optional CSS class name for the container */
  readonly className?: string;
}

export interface MoleculeViewer3DRef {
  readonly resetCamera: () => void;
}

type ViewState = [number, number, number, number, number, number, number, number];
type ViewerStyle = "ball-and-stick" | "space-filling" | "wireframe";
type ViewerInstance = {
  addModel?: (...args: unknown[]) => unknown;
  clear?: (...args: unknown[]) => unknown;
  getView?: () => unknown;
  render?: (...args: unknown[]) => unknown;
  resize?: (...args: unknown[]) => unknown;
  setBackgroundColor?: (...args: unknown[]) => unknown;
  setStyle?: (...args: unknown[]) => unknown;
  setView?: (...args: unknown[]) => unknown;
  spin?: (...args: unknown[]) => unknown;
  zoom?: (...args: unknown[]) => unknown;
  zoomTo?: (...args: unknown[]) => unknown;
};

const RESET_ANIMATION_MS = 420;
const DEFAULT_ZOOM_FACTOR = 1.18;
const AUTO_ROTATE_AXIS = "vy";
const AUTO_ROTATE_TARGET_SPEED = 0.2;
const AUTO_ROTATE_MIN_SPEED = 0.035;
const AUTO_ROTATE_RAMP_MS = 900;
const AUTO_ROTATE_RESUME_DELAY_MS = 1800;
const AUTO_ROTATE_TICK_MS = 50;
let viewerModulePromise: Promise<typeof import("3dmol")> | null = null;

function getViewerBackgroundColor(): string {
  if (globalThis.document === undefined || typeof globalThis.getComputedStyle !== "function") {
    return "#ffffff";
  }

  const cardColor = globalThis
    .getComputedStyle(globalThis.document.documentElement)
    .getPropertyValue("--card")
    .trim();
  return cardColor || "#ffffff";
}

function loadViewerModule() {
  viewerModulePromise ??= import("3dmol");
  return viewerModulePromise;
}

function runViewerAction(action: () => void) {
  try {
    action();
  } catch {
    // ignore
  }
}

function clearTimeoutRef(timeoutRef: RefObject<ReturnType<typeof setTimeout> | null>) {
  if (timeoutRef.current !== null) {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
  }
}

function getViewerNamespace(mol: typeof import("3dmol")) {
  return (mol as typeof import("3dmol") & { default?: typeof import("3dmol") }).default ?? mol;
}

function ensureViewerInstance(
  mol: typeof import("3dmol"),
  container: HTMLDivElement,
  viewerRef: RefObject<ViewerInstance | null>,
): ViewerInstance {
  if (viewerRef.current) {
    return viewerRef.current;
  }

  container.innerHTML = "";
  const viewer = getViewerNamespace(mol).createViewer(container, {
    backgroundColor: getViewerBackgroundColor(),
  }) as unknown as ViewerInstance;
  viewerRef.current = viewer;
  return viewer;
}

function normalizeQuaternion(
  x: number,
  y: number,
  z: number,
  w: number,
): [number, number, number, number] {
  const len = Math.hypot(x, y, z, w);
  if (len === 0) return [0, 0, 0, 1];
  return [x / len, y / len, z / len, w / len];
}

function asViewState(view: unknown): ViewState | null {
  if (!Array.isArray(view) || view.length < 8) return null;
  const firstEight = view.slice(0, 8);
  if (!firstEight.every((n) => typeof n === "number" && Number.isFinite(n))) return null;
  return firstEight as ViewState;
}

function slerpQuaternion(
  from: number[],
  to: number[],
  t: number,
): [number, number, number, number] {
  const [fx, fy, fz, fw] = normalizeQuaternion(
    from[0] ?? 0,
    from[1] ?? 0,
    from[2] ?? 0,
    from[3] ?? 1,
  );
  let [tx, ty, tz, tw] = normalizeQuaternion(to[0] ?? 0, to[1] ?? 0, to[2] ?? 0, to[3] ?? 1);

  let dot = fx * tx + fy * ty + fz * tz + fw * tw;
  if (dot < 0) {
    tx = -tx;
    ty = -ty;
    tz = -tz;
    tw = -tw;
    dot = -dot;
  }

  if (dot > 0.9995) {
    return normalizeQuaternion(
      fx + (tx - fx) * t,
      fy + (ty - fy) * t,
      fz + (tz - fz) * t,
      fw + (tw - fw) * t,
    );
  }

  const theta0 = Math.acos(Math.max(-1, Math.min(1, dot)));
  const sinTheta0 = Math.sin(theta0);
  if (sinTheta0 < 1e-6) return [fx, fy, fz, fw];

  const theta = theta0 * t;
  const sinTheta = Math.sin(theta);
  const s0 = Math.cos(theta) - (dot * sinTheta) / sinTheta0;
  const s1 = sinTheta / sinTheta0;

  return normalizeQuaternion(
    fx * s0 + tx * s1,
    fy * s0 + ty * s1,
    fz * s0 + tz * s1,
    fw * s0 + tw * s1,
  );
}

function interpolateView(from: ViewState, to: ViewState, t: number): ViewState {
  const q = slerpQuaternion([from[4], from[5], from[6], from[7]], [to[4], to[5], to[6], to[7]], t);

  return [
    from[0] + (to[0] - from[0]) * t,
    from[1] + (to[1] - from[1]) * t,
    from[2] + (to[2] - from[2]) * t,
    from[3] + (to[3] - from[3]) * t,
    q[0],
    q[1],
    q[2],
    q[3],
  ];
}

function resetViewerZoom(viewer: ViewerInstance) {
  runViewerAction(() => {
    viewer.zoomTo?.({}, RESET_ANIMATION_MS, true);
    viewer.zoom?.(DEFAULT_ZOOM_FACTOR);
    viewer.render?.();
  });
}

function animateResetToView(
  viewer: ViewerInstance,
  startView: ViewState,
  targetView: ViewState,
  resetAnimationRef: RefObject<number | null>,
  onComplete: () => void,
) {
  const startAt = performance.now();
  const step = (now: number) => {
    const progress = Math.min(1, (now - startAt) / RESET_ANIMATION_MS);
    const eased = 1 - Math.pow(1 - progress, 3);
    const nextView = interpolateView(startView, targetView, eased);

    runViewerAction(() => {
      viewer.setView?.(nextView, true);
    });

    if (progress < 1) {
      resetAnimationRef.current = requestAnimationFrame(step);
      return;
    }

    resetAnimationRef.current = null;
    runViewerAction(() => {
      viewer.render?.();
    });
    onComplete();
  };

  resetAnimationRef.current = requestAnimationFrame(step);
}

function applyViewerAtoms(
  viewer: ViewerInstance,
  atoms: AtomSchema[],
  style: ViewerStyle,
  showBonds: boolean,
): ViewState | null {
  const xyzData = atomsToXyz(atoms);
  viewer.addModel?.(xyzData, "xyz");
  viewer.setStyle?.({}, getStyleConfig(style, showBonds));
  viewer.zoomTo?.();
  viewer.zoom?.(DEFAULT_ZOOM_FACTOR);
  viewer.render?.();
  return asViewState(viewer.getView?.());
}

function syncAutoRotateWithHoverState(
  container: HTMLDivElement,
  isHoveringRef: RefObject<boolean>,
  startAutoRotate: () => void,
  stopAutoRotate: () => void,
) {
  isHoveringRef.current = container.matches(":hover");
  if (isHoveringRef.current) {
    stopAutoRotate();
    return;
  }
  startAutoRotate();
}

function ensureViewerResizeObserver({
  container,
  resizeObserverRef,
  debounceRef,
  viewerRef,
  isCancelled,
}: {
  container: HTMLDivElement;
  resizeObserverRef: RefObject<ResizeObserver | null>;
  debounceRef: RefObject<ReturnType<typeof setTimeout> | null>;
  viewerRef: RefObject<ViewerInstance | null>;
  isCancelled: () => boolean;
}) {
  if (resizeObserverRef.current) return;

  const observer = new ResizeObserver(() => {
    clearTimeoutRef(debounceRef);
    debounceRef.current = setTimeout(() => {
      debounceRef.current = null;
      if (isCancelled() || !viewerRef.current) return;

      runViewerAction(() => {
        viewerRef.current?.resize?.();
        viewerRef.current?.render?.();
      });
    }, 150);
  });

  resizeObserverRef.current = observer;
  observer.observe(container);
}

/**
 * 3D molecule viewer component using 3Dmol.js
 * Renders atoms as a 3D structure with optional bonds
 */
export const MoleculeViewer3D = forwardRef<MoleculeViewer3DRef, MoleculeViewer3DProps>(
  function MoleculeViewer3D(
    { atoms, style = "ball-and-stick", showBonds = true, isDark = false, className = "" },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const viewerRef = useRef<ViewerInstance | null>(null);
    const resizeObserverRef = useRef<ResizeObserver | null>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const resetAnimationRef = useRef<number | null>(null);
    const autoRotateRampRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const autoRotateResumeRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const defaultViewRef = useRef<ViewState | null>(null);
    const styleRef = useRef(style);
    const showBondsRef = useRef(showBonds);
    const isHoveringRef = useRef(false);

    const cancelResetAnimation = useCallback(() => {
      if (resetAnimationRef.current !== null) {
        cancelAnimationFrame(resetAnimationRef.current);
        resetAnimationRef.current = null;
      }
    }, []);

    const clearAutoRotateRamp = useCallback(() => {
      if (autoRotateRampRef.current !== null) {
        clearInterval(autoRotateRampRef.current);
        autoRotateRampRef.current = null;
      }
    }, []);

    const clearAutoRotateResume = useCallback(() => {
      clearTimeoutRef(autoRotateResumeRef);
    }, []);

    const stopAutoRotate = useCallback(() => {
      clearAutoRotateResume();
      clearAutoRotateRamp();
      try {
        viewerRef.current?.spin?.(false);
      } catch {
        // ignore
      }
    }, [clearAutoRotateRamp, clearAutoRotateResume]);

    const startAutoRotate = useCallback(() => {
      if (atoms.length === 0 || isHoveringRef.current || !viewerRef.current) return;

      clearAutoRotateResume();
      clearAutoRotateRamp();

      const viewer = viewerRef.current;
      const startAt = performance.now();
      const updateSpin = () => {
        if (!viewerRef.current || isHoveringRef.current) {
          stopAutoRotate();
          return;
        }

        const elapsed = performance.now() - startAt;
        const progress = Math.min(1, elapsed / AUTO_ROTATE_RAMP_MS);
        const eased = progress * progress * (3 - 2 * progress);
        const speed = Math.max(AUTO_ROTATE_MIN_SPEED, AUTO_ROTATE_TARGET_SPEED * eased);

        try {
          viewer.spin?.(AUTO_ROTATE_AXIS, speed, true);
        } catch {
          // ignore
        }

        if (progress >= 1) {
          clearAutoRotateRamp();
        }
      };

      updateSpin();
      autoRotateRampRef.current = setInterval(updateSpin, AUTO_ROTATE_TICK_MS);
    }, [atoms.length, clearAutoRotateRamp, clearAutoRotateResume, stopAutoRotate]);

    const scheduleAutoRotateResume = useCallback(
      (delayMs = AUTO_ROTATE_RESUME_DELAY_MS) => {
        clearAutoRotateResume();
        if (atoms.length === 0 || isHoveringRef.current) return;
        autoRotateResumeRef.current = setTimeout(() => {
          autoRotateResumeRef.current = null;
          startAutoRotate();
        }, delayMs);
      },
      [atoms.length, clearAutoRotateResume, startAutoRotate],
    );

    const resumeAutoRotateIfIdle = useCallback(() => {
      if (!isHoveringRef.current) {
        scheduleAutoRotateResume();
      }
    }, [scheduleAutoRotateResume]);

    const resetCamera = useCallback(() => {
      const viewer = viewerRef.current;
      if (!viewer) return;

      cancelResetAnimation();
      stopAutoRotate();

      const targetView = defaultViewRef.current;
      const startView = asViewState(viewer.getView?.());
      if (!targetView || !startView) {
        resetViewerZoom(viewer);
        resumeAutoRotateIfIdle();
        return;
      }

      animateResetToView(viewer, startView, targetView, resetAnimationRef, resumeAutoRotateIfIdle);
    }, [cancelResetAnimation, resumeAutoRotateIfIdle, stopAutoRotate]);

    useImperativeHandle(
      ref,
      () => ({
        resetCamera,
      }),
      [resetCamera],
    );

    useEffect(() => {
      styleRef.current = style;
    }, [style]);

    useEffect(() => {
      showBondsRef.current = showBonds;
    }, [showBonds]);

    useEffect(() => {
      if (!containerRef.current) return;

      let cancelled = false;
      const isCancelled = () => cancelled;

      loadViewerModule().then((mol) => {
        if (cancelled || !containerRef.current) return;

        try {
          const container = containerRef.current;
          const viewer = ensureViewerInstance(mol, container, viewerRef);

          cancelResetAnimation();
          runViewerAction(() => {
            viewer.clear?.();
          });

          if (atoms.length > 0) {
            defaultViewRef.current = applyViewerAtoms(
              viewer,
              atoms,
              styleRef.current,
              showBondsRef.current,
            );
            syncAutoRotateWithHoverState(container, isHoveringRef, startAutoRotate, stopAutoRotate);
          } else {
            defaultViewRef.current = null;
            stopAutoRotate();
            viewer.render?.();
          }

          ensureViewerResizeObserver({
            container,
            resizeObserverRef,
            debounceRef,
            viewerRef,
            isCancelled,
          });
        } catch (error) {
          logAppError("molecule.viewer-3d", "Failed to initialize 3Dmol viewer.", error);
        }
      });

      return () => {
        cancelled = true;
        clearTimeoutRef(debounceRef);
      };
    }, [atoms, cancelResetAnimation, startAutoRotate, stopAutoRotate]);

    useEffect(() => {
      const viewer = viewerRef.current;
      if (!viewer || atoms.length === 0) return;
      runViewerAction(() => {
        viewer.setStyle?.({}, getStyleConfig(style, showBonds));
        viewer.render?.();
      });
    }, [atoms.length, style, showBonds]);

    useEffect(() => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      runViewerAction(() => {
        viewer.setBackgroundColor?.(getViewerBackgroundColor());
        viewer.render?.();
      });
    }, [isDark]);

    useEffect(
      () => () => {
        cancelResetAnimation();
        clearTimeoutRef(debounceRef);
        clearAutoRotateResume();
        clearAutoRotateRamp();
        if (resizeObserverRef.current) {
          resizeObserverRef.current.disconnect();
          resizeObserverRef.current = null;
        }
        const viewer = viewerRef.current;
        if (viewer) {
          runViewerAction(() => {
            viewer.spin?.(false);
            viewer.clear?.();
          });
          viewerRef.current = null;
        }
      },
      [cancelResetAnimation, clearAutoRotateRamp, clearAutoRotateResume],
    );

    return (
      <div
        ref={containerRef}
        data-testid="molecule-viewer-3d"
        className={className}
        onPointerEnter={() => {
          isHoveringRef.current = true;
          stopAutoRotate();
        }}
        onPointerLeave={() => {
          isHoveringRef.current = false;
          scheduleAutoRotateResume();
        }}
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          backgroundColor: "var(--card)",
        }}
      />
    );
  },
);

// Reuse stable style object references for hot render paths.
const STYLE_CONFIG_CACHE: Record<string, Readonly<Record<string, unknown>>> = {
  "ball-and-stick:true": { stick: { radius: 0.15 }, sphere: { scale: 0.25 } },
  "ball-and-stick:false": { sphere: { scale: 0.35 } },
  "space-filling:true": { sphere: { scale: 1 } },
  "space-filling:false": { sphere: { scale: 1 } },
  "wireframe:true": { line: { linewidth: 2 } },
  "wireframe:false": { sphere: { scale: 0.15 } },
};

function getStyleConfig(style: ViewerStyle, showBonds: boolean): Readonly<Record<string, unknown>> {
  return STYLE_CONFIG_CACHE[`${style}:${showBonds}`] ?? {};
}
