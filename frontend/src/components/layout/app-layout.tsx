import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Outlet, useRouter } from "@tanstack/react-router";
import { AnimatePresence } from "framer-motion";
import { AppSidebar } from "./app-sidebar";
import { Footer } from "./footer";
import { Header } from "./header";
import { PageTransition } from "@/components/motion";
import { useEffect, useRef } from "react";
import { markRoute, getRouteMarkName } from "@/utils/web-vitals";
import { getRouteMetadata } from "@/lib/site-metadata";
import { startBackendCapabilitiesAutoRefresh } from "@/api/backends";
import { warmAllBackendCapabilitiesCache } from "@/api/profiles";
import { notifyIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";

export function AppLayout() {
  const router = useRouter();
  const currentPathname = router.state.location.pathname;
  const warmedCapabilitiesRef = useRef(false);

  useEffect(() => {
    const metadata = getRouteMetadata(currentPathname);
    document.title = metadata.title;

    let description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (description === null) {
      description = document.createElement("meta");
      description.name = "description";
      document.head.appendChild(description);
    }
    description.content = metadata.description;

    let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (canonical === null) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    canonical.href = `${globalThis.location.origin}${currentPathname}`;

    const routeName = getRouteMarkName(currentPathname);
    // Mark after paint so route timing includes the first rendered frame.
    const rafId = requestAnimationFrame(() => {
      markRoute(routeName, "end");
    });
    return () => cancelAnimationFrame(rafId);
  }, [currentPathname]);

  useEffect(() => {
    if (warmedCapabilitiesRef.current) {
      return;
    }
    warmedCapabilitiesRef.current = true;

    startBackendCapabilitiesAutoRefresh();
    void warmAllBackendCapabilitiesCache({
      onProgress: (progress) => {
        notifyIbmCredentialProfilesChanged({
          backendCapabilitiesRefresh: progress.loadedProfiles === 0 ? "started" : "progress",
          backendWarmupProgress: progress,
        });
      },
    })
      .then(({ activeProfileId }) => {
        notifyIbmCredentialProfilesChanged({
          activeProfileId,
          backendCapabilitiesRefresh: "completed",
          backendWarmupProgress: null,
        });
      })
      .catch(() => {
        notifyIbmCredentialProfilesChanged({
          backendCapabilitiesRefresh: "failed",
          backendWarmupProgress: null,
        });
      });
  }, []);

  return (
    <TooltipProvider>
      <SidebarProvider defaultOpen={false}>
        <AppSidebar />
        <SidebarInset>
          <Header />
          <div className="flex flex-1 flex-col gap-4 px-6 pb-6 pt-6 min-w-0 overflow-x-hidden">
            <AnimatePresence mode="popLayout">
              <PageTransition key={currentPathname}>
                <Outlet />
              </PageTransition>
            </AnimatePresence>
          </div>
          <Footer />
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
