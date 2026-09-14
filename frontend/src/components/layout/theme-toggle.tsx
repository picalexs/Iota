import { Monitor, Moon, Sun } from "lucide-react";

import { SidebarMenuButton } from "@/components/ui/sidebar";
import { useTheme, type Theme } from "@/hooks/use-theme";

type ThemeOption = {
  value: Theme;
  label: string;
  icon: typeof Sun;
};

const THEME_OPTIONS = [
  {
    value: "light",
    label: "Light",
    icon: Sun,
  },
  {
    value: "dark",
    label: "Dark",
    icon: Moon,
  },
  {
    value: "system",
    label: "System",
    icon: Monitor,
  },
] satisfies readonly [ThemeOption, ...ThemeOption[]];

const DEFAULT_THEME_OPTION = THEME_OPTIONS[0];

/**
 * Sidebar-mounted theme toggle that cycles through light, dark, and system
 * modes on each click without opening a secondary menu.
 */
export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const selectedTheme =
    THEME_OPTIONS.find((option) => option.value === theme) ?? DEFAULT_THEME_OPTION;
  const SelectedIcon = selectedTheme.icon;
  const selectedIndex = THEME_OPTIONS.findIndex((option) => option.value === selectedTheme.value);
  const nextTheme =
    THEME_OPTIONS[(selectedIndex + 1) % THEME_OPTIONS.length] ?? DEFAULT_THEME_OPTION;
  const resolvedThemeLabel = resolvedTheme === "dark" ? "Dark" : "Light";
  const resolvedSuffix = theme === "system" ? `. Following system (${resolvedThemeLabel})` : "";

  return (
    <SidebarMenuButton
      tooltip="Theme"
      aria-label={`Theme: ${selectedTheme.label}. Click to switch to ${nextTheme.label}${resolvedSuffix}`}
      className="cursor-pointer"
      onClick={() => setTheme(nextTheme.value)}
    >
      <SelectedIcon className="size-4" />
      <span className="transition-opacity duration-200 group-data-[collapsible=icon]:opacity-0">
        {selectedTheme.label}
      </span>
    </SidebarMenuButton>
  );
}
