import {
  createContext,
  useContext,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { useLocalStorage } from "@/hooks/use-local-storage";

type ViewMode = "2d" | "3d";
type ViewerStyle = "ball-and-stick" | "space-filling" | "wireframe";
type PanelId = "viewer" | "properties" | "description" | "identifiers" | "active_space" | "atoms";
type LayoutBreakpoint = "mobile" | "small-tablet" | "tablet" | "desktop";

// Minimal grid layout item — mirrors react-grid-layout's Layout interface
export type GridLayoutItem = {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
};

interface ViewerPreferences {
  viewMode: ViewMode;
  viewerStyle: ViewerStyle;
  showBonds: boolean;
  panelOrder: PanelId[];
  gridLayout?: GridLayoutItem[];
  layoutBreakpoint?: LayoutBreakpoint; // Breakpoint where current layout was saved
}

interface ViewerPreferencesContextType {
  preferences: ViewerPreferences;
  setViewMode: (mode: ViewMode) => void;
  setViewerStyle: (style: ViewerStyle) => void;
  setShowBonds: (show: boolean) => void;
  setPanelOrder: (order: PanelId[]) => void;
  setGridLayout: (layout: GridLayoutItem[], breakpoint: LayoutBreakpoint) => void;
}

const ViewerPreferencesContext = createContext<ViewerPreferencesContextType | undefined>(undefined);

const DEFAULT_PREFERENCES: ViewerPreferences = {
  viewMode: "3d",
  viewerStyle: "ball-and-stick",
  showBonds: true,
  panelOrder: ["description", "identifiers", "atoms"],
};

// v2: bumped to discard old saves with over-tall default heights
const STORAGE_KEY = "qvs-viewer-preferences-v2";

export interface ViewerPreferencesProviderProps {
  readonly children: ReactNode;
}

export function ViewerPreferencesProvider({ children }: ViewerPreferencesProviderProps) {
  const [preferences, setPreferences] = useLocalStorage<ViewerPreferences>(
    STORAGE_KEY,
    DEFAULT_PREFERENCES,
  );

  const layoutTimeoutRef = useRef<ReturnType<typeof globalThis.setTimeout> | null>(null);
  const pendingLayoutRef = useRef<{
    layout: GridLayoutItem[];
    breakpoint: LayoutBreakpoint;
  } | null>(null);
  const preferencesRef = useRef<ViewerPreferences>(preferences);

  useEffect(() => {
    preferencesRef.current = preferences;
  }, [preferences]);

  useEffect(() => {
    return () => {
      if (layoutTimeoutRef.current) {
        globalThis.clearTimeout(layoutTimeoutRef.current);
      }
    };
  }, []);

  const setViewMode = useCallback(
    (mode: ViewMode) => {
      setPreferences((prev) => ({ ...prev, viewMode: mode }));
    },
    [setPreferences],
  );

  const setViewerStyle = useCallback(
    (style: ViewerStyle) => {
      setPreferences((prev) => ({ ...prev, viewerStyle: style }));
    },
    [setPreferences],
  );

  const setShowBonds = useCallback(
    (show: boolean) => {
      setPreferences((prev) => ({ ...prev, showBonds: show }));
    },
    [setPreferences],
  );

  const setPanelOrder = useCallback(
    (order: PanelId[]) => {
      setPreferences((prev) => ({ ...prev, panelOrder: order }));
    },
    [setPreferences],
  );

  // Debounce layout writes during drag/resize to avoid localStorage jank.
  const setGridLayout = useCallback(
    (layout: GridLayoutItem[], breakpoint: LayoutBreakpoint) => {
      pendingLayoutRef.current = { layout, breakpoint };

      if (layoutTimeoutRef.current) {
        globalThis.clearTimeout(layoutTimeoutRef.current);
      }

      layoutTimeoutRef.current = globalThis.setTimeout(() => {
        const pending = pendingLayoutRef.current;
        if (pending) {
          setPreferences({
            ...preferencesRef.current,
            gridLayout: pending.layout,
            layoutBreakpoint: pending.breakpoint,
          });
          pendingLayoutRef.current = null;
        }
        layoutTimeoutRef.current = null;
      }, 300);
    },
    [setPreferences],
  );

  const value: ViewerPreferencesContextType = useMemo(
    () => ({
      preferences,
      setViewMode,
      setViewerStyle,
      setShowBonds,
      setPanelOrder,
      setGridLayout,
    }),
    [preferences, setGridLayout, setPanelOrder, setShowBonds, setViewerStyle, setViewMode],
  );

  return (
    <ViewerPreferencesContext.Provider value={value}>{children}</ViewerPreferencesContext.Provider>
  );
}

export function useViewerPreferences(): ViewerPreferencesContextType {
  const context = useContext(ViewerPreferencesContext);
  if (!context) {
    throw new Error("useViewerPreferences must be used within ViewerPreferencesProvider");
  }
  return context;
}

export type { ViewerPreferences, PanelId, LayoutBreakpoint };
