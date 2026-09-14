import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { RunsListPage } from "./runs-list-page";

// Mock RunsList so we don't need full API setup
vi.mock("@/features/runs/RunsList", () => ({
  RunsList: () => <div data-testid="runs-list">RunsList</div>,
}));

// Mock matchMedia
beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

function buildTestRouter() {
  const rootRoute = createRootRoute();
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs",
    component: RunsListPage,
  });
  const newRunRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/new",
    component: () => <div>New Run</div>,
  });
  const routeTree = rootRoute.addChildren([listRoute, newRunRoute]);
  const history = createMemoryHistory({ initialEntries: ["/runs"] });
  return createRouter({ routeTree, history });
}

describe("RunsListPage", () => {
  it("renders the page heading", async () => {
    render(<RouterProvider router={buildTestRouter()} />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /quantum runs/i })).toBeInTheDocument();
    });
  });

  it("renders the RunsList component", async () => {
    render(<RouterProvider router={buildTestRouter()} />);
    await waitFor(() => {
      expect(screen.getByTestId("runs-list")).toBeInTheDocument();
    });
  });
});
