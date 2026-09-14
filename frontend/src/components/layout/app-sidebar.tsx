import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Link } from "@tanstack/react-router";
import { BookOpen, FlaskConical, House, Play, Plus, Settings, TestTube2 } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";
import { ProfileQuickSwitch } from "./profile-quick-switch";
import { useRef } from "react";
import { LogoAtom } from "@/components/motion/molecule-loader";
import { SITE_SHORT_NAME } from "@/lib/site-metadata";
import { preloadPageModule } from "@/routes/lazy-pages";

const navItems = [
  { title: "Home", icon: House, to: "/" },
  { title: "Molecules", icon: FlaskConical, to: "/molecules" },
  { title: "New Run", icon: Plus, to: "/runs/new" },
  { title: "Runs", icon: Play, to: "/runs" },
  { title: "Benchmarks", icon: TestTube2, to: "/benchmarks" },
  { title: "Info", icon: BookOpen, to: "/info" },
] as const;

const bottomNavItems = [{ title: "Settings", icon: Settings, to: "/settings" }] as const;

/**
 * Application sidebar with smooth hover-to-expand behavior.
 * Expands on hover when collapsed, smooth fade for text and icon transitions.
 * Logo stays fixed left-aligned and intentionally does not entangle in the sidebar.
 */
export function AppSidebar() {
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { state, setOpen } = useSidebar();

  const handleMouseEnter = () => {
    if (closeTimerRef.current !== null) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    if (state === "collapsed") {
      setOpen(true);
    }
  };

  const handleMouseLeave = () => {
    closeTimerRef.current = setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, 100);
  };

  return (
    <Sidebar
      collapsible="icon"
      className="transition-[width] duration-200 ease-in-out"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              size="lg"
              activeStyle="none"
              className="hover:border-transparent hover:bg-transparent hover:text-sidebar-foreground active:bg-transparent active:text-sidebar-foreground"
            >
              <Link to="/" aria-label="Go to home page">
                <LogoAtom isEntangled={false} size={32} className="shrink-0" />
                <span className="font-semibold truncate">{SITE_SHORT_NAME}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent className="overflow-hidden">
        <SidebarGroup>
          <SidebarGroupLabel className="transition-opacity duration-200 group-data-[collapsible=icon]:opacity-0">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <Link
                      to={item.to}
                      onFocus={() => preloadPageModule(item.to)}
                      onPointerEnter={() => preloadPageModule(item.to)}
                      activeOptions={item.title === "Runs" ? { exact: true } : undefined}
                    >
                      <item.icon />
                      <span className="transition-opacity duration-200 group-data-[collapsible=icon]:opacity-0">
                        {item.title}
                      </span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter data-testid="sidebar-footer-shell">
        <SidebarMenu>
          <SidebarMenuItem>
            <ThemeToggle />
          </SidebarMenuItem>
          <ProfileQuickSwitch />
          {bottomNavItems.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton asChild>
                <Link
                  to={item.to}
                  onFocus={() => preloadPageModule(item.to)}
                  onPointerEnter={() => preloadPageModule(item.to)}
                >
                  <item.icon />
                  <span className="transition-opacity duration-200 group-data-[collapsible=icon]:opacity-0">
                    {item.title}
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
