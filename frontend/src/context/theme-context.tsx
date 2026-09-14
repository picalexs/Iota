import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/** The supported theme values. `'system'` defers to the OS preference. */
export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeProviderProps {
  readonly children: ReactNode;
  /** Initial theme to use when no value is stored in localStorage. */
  readonly defaultTheme?: Theme;
  /** The localStorage key used to persist the selected theme. */
  readonly storageKey?: string;
}

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const VALID_THEMES = new Set<string>(["light", "dark", "system"]);

function isTheme(value: string | null): value is Theme {
  return value !== null && VALID_THEMES.has(value);
}

function getSystemTheme(): ResolvedTheme {
  return globalThis.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Wraps the application and provides a `theme` value + `setTheme` setter via
 * context. The selected theme is persisted to `localStorage` and applied by
 * toggling the `dark` CSS class on `document.documentElement`.
 */
export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "theme",
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    const storedTheme = globalThis.localStorage.getItem(storageKey);
    return isTheme(storedTheme) ? storedTheme : defaultTheme;
  });
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    theme === "system" ? getSystemTheme() : theme,
  );

  useEffect(() => {
    const root = globalThis.document.documentElement;
    const mediaQuery = globalThis.matchMedia("(prefers-color-scheme: dark)");

    const applyTheme = (nextResolvedTheme: ResolvedTheme) => {
      root.classList.toggle("dark", nextResolvedTheme === "dark");
      root.style.colorScheme = nextResolvedTheme;
      setResolvedTheme(nextResolvedTheme);
    };

    if (theme === "system") {
      applyTheme(getSystemTheme());

      const handler = (event: MediaQueryListEvent) => {
        applyTheme(event.matches ? "dark" : "light");
      };
      mediaQuery.addEventListener("change", handler);
      return () => mediaQuery.removeEventListener("change", handler);
    }

    applyTheme(theme);
  }, [theme]);

  /** Persists the chosen theme to localStorage and updates the context state. */
  const setStoredTheme = useCallback(
    (newTheme: Theme) => {
      globalThis.localStorage.setItem(storageKey, newTheme);
      setTheme(newTheme);
    },
    [storageKey],
  );

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme: setStoredTheme }),
    [theme, resolvedTheme, setStoredTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * Returns the current `theme` value and the `setTheme` setter.
 *
 * @throws {Error} When called outside of a `ThemeProvider`.
 */
export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
