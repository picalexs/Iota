import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";

/**
 * Mobile-only app-shell toolbar that exposes the drawer toggle on small viewports.
 */
export function Header() {
  const { isMobile } = useSidebar();

  if (!isMobile) {
    return null;
  }

  return (
    <div className="sticky top-0 z-20 flex h-14 shrink-0 items-center border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <SidebarTrigger className="size-9" />
    </div>
  );
}

export default Header;
