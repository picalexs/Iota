import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { ThemeProvider } from "@/context/theme-context";
import { MOBILE_BREAKPOINT } from "@/lib/layout-constants";
import { AppLayout } from "./app-layout";

const mockStartBackendCapabilitiesAutoRefresh = vi.hoisted(() => vi.fn());
const mockWarmAllBackendCapabilitiesCache = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    activeProfileId: null,
  }),
);

vi.mock("@/api/backends", () => ({
  startBackendCapabilitiesAutoRefresh: mockStartBackendCapabilitiesAutoRefresh,
}));

vi.mock("@/api/profiles", () => ({
  warmAllBackendCapabilitiesCache: mockWarmAllBackendCapabilitiesCache,
}));

// jsdom does not implement matchMedia or ResizeObserver — stub them before rendering
beforeEach(() => {
  Object.defineProperty(globalThis, "innerWidth", {
    configurable: true,
    writable: true,
    value: MOBILE_BREAKPOINT,
  });
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    },
  );
  localStorage.clear();
});

function buildTestRouter(initialEntries: string[] = ["/"]) {
  const rootRoute = createRootRoute({ component: AppLayout });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: () => null,
  });
  const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs",
    component: () => null,
  });
  const newRunRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/new",
    component: () => null,
  });
  const routeTree = rootRoute.addChildren([indexRoute, runsRoute, newRunRoute]);
  const history = createMemoryHistory({ initialEntries });
  return createRouter({ routeTree, history });
}

function renderLayout(viewportWidth = MOBILE_BREAKPOINT) {
  globalThis.innerWidth = viewportWidth;
  const testRouter = buildTestRouter();
  return render(
    <ThemeProvider>
      <RouterProvider router={testRouter} />
    </ThemeProvider>,
  );
}

describe("AppLayout", () => {
  it("warms backend capabilities once when the app shell mounts", async () => {
    renderLayout();

    await waitFor(() => {
      expect(mockStartBackendCapabilitiesAutoRefresh).toHaveBeenCalledOnce();
      expect(mockWarmAllBackendCapabilitiesCache).toHaveBeenCalledOnce();
    });
  });

  it("does not render a top header landmark", async () => {
    renderLayout();
    await waitFor(() => expect(screen.queryByRole("banner")).not.toBeInTheDocument());
  });

  it("renders the main landmark", async () => {
    renderLayout();
    // SidebarInset renders as <main>; our content div is nested inside
    await waitFor(() => expect(screen.getByRole("main")).toBeInTheDocument());
  });

  it("does not render the sidebar toggle button on desktop widths", async () => {
    renderLayout();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /toggle sidebar/i })).not.toBeInTheDocument(),
    );
  });

  it("renders a sidebar toggle button on mobile widths", async () => {
    renderLayout(MOBILE_BREAKPOINT - 1);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /toggle sidebar/i })).toBeInTheDocument(),
    );
  });

  it("renders the footer landmark", async () => {
    renderLayout();
    await waitFor(() => expect(screen.getByRole("contentinfo")).toBeInTheDocument());
  });

  it("renders sidebar navigation links", async () => {
    renderLayout();
    // shadcn Sidebar uses divs/ul, not <nav> — verify nav items are present instead
    await waitFor(() => expect(screen.getByText("Home")).toBeInTheDocument());
  });

  it("keeps the sidebar footer overflow visible for the IBM profile switcher", async () => {
    renderLayout();

    const footer = await screen.findByTestId("sidebar-footer-shell");
    expect(footer.className).not.toContain("overflow-hidden");
  });

  it("highlights only New Run on the new run page", async () => {
    const testRouter = buildTestRouter(["/runs/new"]);
    render(
      <ThemeProvider>
        <RouterProvider router={testRouter} />
      </ThemeProvider>,
    );

    const newRunLink = await screen.findByRole("link", { name: "New Run" });
    const runsLink = screen.getByRole("link", { name: "Runs" });

    expect(newRunLink).toHaveAttribute("data-status", "active");
    expect(newRunLink).toHaveAttribute("aria-current", "page");
    expect(newRunLink.className).toContain("hover:bg-sidebar-hover");
    expect(newRunLink.className).toContain("data-[status=active]:bg-sidebar-selected");
    expect(newRunLink.className).toContain("shadow-[var(--shadow-sidebar-selected)]");
    expect(runsLink).not.toHaveAttribute("data-status", "active");
    expect(runsLink).not.toHaveAttribute("aria-current", "page");
  });

  it("keeps the logo link visually neutral on the home route", async () => {
    renderLayout();

    const logoLink = await screen.findByRole("link", { name: "Go to home page" });

    expect(logoLink).toHaveAttribute("data-status", "active");
    expect(logoLink.className).toContain("data-[status=active]:!bg-transparent");
    expect(logoLink.className).toContain("hover:bg-transparent");
  });
});
