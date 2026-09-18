import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";

import { forceRefreshBackendCapabilities, setActiveBackendCapabilitiesProfile } from "@/api/backends";
import { activateIbmCredentialProfile, listIbmCredentialProfiles } from "@/api/profiles";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import { notifyIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";
import type { IbmCredentialProfileListResponse } from "@/types/profile";
import { ProfileQuickSwitch, SIDEBAR_RECENT_PROFILE_STORAGE_KEY } from "./profile-quick-switch";

vi.mock("@/api/backends", () => ({
  forceRefreshBackendCapabilities: vi.fn(),
  setActiveBackendCapabilitiesProfile: vi.fn(),
}));

vi.mock("@/api/profiles", () => ({
  activateIbmCredentialProfile: vi.fn(),
  listIbmCredentialProfiles: vi.fn(),
}));

const baseProfiles: IbmCredentialProfileListResponse = {
  active_profile_id: "profile-1",
  encryption_key_source: "local_key_file",
  encryption_warning: null,
  profiles: [
    {
      id: "profile-1",
      name: "Main IBM",
      channel: "ibm_quantum_platform",
      active: true,
      created_at: "2026-06-01T08:00:00Z",
      updated_at: "2026-06-01T08:00:00Z",
    },
    {
      id: "profile-2",
      name: "EU-West",
      channel: "ibm_cloud",
      active: false,
      created_at: "2026-06-01T09:00:00Z",
      updated_at: "2026-06-01T09:00:00Z",
    },
    {
      id: "profile-3",
      name: "Research",
      channel: "ibm_quantum_platform",
      active: false,
      created_at: "2026-06-01T10:00:00Z",
      updated_at: "2026-06-01T10:00:00Z",
    },
    {
      id: "profile-4",
      name: "Backup",
      channel: "ibm_cloud",
      active: false,
      created_at: "2026-06-01T11:00:00Z",
      updated_at: "2026-06-01T11:00:00Z",
    },
  ],
};

const secondaryProfile = baseProfiles.profiles[1];
if (!secondaryProfile) {
  throw new Error("Expected a secondary IBM profile fixture");
}

function renderSwitch() {
  return render(
    <SidebarProvider>
      <ProfileQuickSwitch />
    </SidebarProvider>,
  );
}

function buildTestRouter() {
  const rootRoute = createRootRoute({
    component: () => (
      <SidebarProvider>
        <ProfileQuickSwitch />
      </SidebarProvider>
    ),
  });
  const settingsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/settings",
    component: () => null,
  });
  const routeTree = rootRoute.addChildren([settingsRoute]);
  const history = createMemoryHistory({ initialEntries: ["/settings"] });
  return createRouter({ routeTree, history });
}

function renderSwitchWithRouter() {
  const router = buildTestRouter();
  return render(<RouterProvider router={router} />);
}

function neverSettles<T>() {
  return new Promise<T>(() => {
    // Intentionally pending for background-validation assertions.
  });
}

function CollapseHarness() {
  const { setOpen } = useSidebar();

  return (
    <>
      <button type="button" onClick={() => setOpen(false)}>
        Collapse sidebar
      </button>
      <ProfileQuickSwitch />
    </>
  );
}

describe("ProfileQuickSwitch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    vi.mocked(activateIbmCredentialProfile).mockReset();
    vi.mocked(forceRefreshBackendCapabilities).mockReset();
    vi.mocked(listIbmCredentialProfiles).mockReset();
    vi.mocked(setActiveBackendCapabilitiesProfile).mockReset();
    vi.mocked(listIbmCredentialProfiles).mockResolvedValue(baseProfiles);
    vi.mocked(forceRefreshBackendCapabilities).mockResolvedValue({ backends: [] });
  });

  it("shows only the latest three recent profiles in the toggle list", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      SIDEBAR_RECENT_PROFILE_STORAGE_KEY,
      JSON.stringify(["profile-4", "profile-2", "profile-3"]),
    );

    renderSwitch();

    await user.click(await screen.findByRole("button", { name: /IBM profile: Main IBM/i }));

    expect(screen.getByRole("button", { name: "Main IBM active" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch to Backup" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Switch to EU-West" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Switch to Research" })).not.toBeInTheDocument();
  });

  it("highlights the active profile row with success styling", async () => {
    const user = userEvent.setup();

    renderSwitch();

    await user.click(await screen.findByRole("button", { name: /IBM profile: Main IBM/i }));

    const activeButton = screen.getByRole("button", { name: "Main IBM active" });
    expect(activeButton).toHaveClass("data-[active=true]:!bg-success/10");
    expect(activeButton).toHaveClass("data-[active=true]:!text-success");
  });

  it("shows an add profile link when no saved profiles exist", async () => {
    const user = userEvent.setup();
    vi.mocked(listIbmCredentialProfiles).mockResolvedValueOnce({
      active_profile_id: null,
      encryption_key_source: "local_key_file",
      encryption_warning: null,
      profiles: [],
    });

    renderSwitchWithRouter();

    await user.click(await screen.findByRole("button", { name: /IBM profiles/i }));

    expect(screen.getByRole("link", { name: "Add IBM profile in settings" })).toHaveAttribute(
      "href",
      "/settings",
    );
  });

  it("activates a selected profile and refreshes backend capabilities", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      SIDEBAR_RECENT_PROFILE_STORAGE_KEY,
      JSON.stringify(["profile-2", "profile-4", "profile-3"]),
    );
    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce(baseProfiles)
      .mockResolvedValueOnce({
        ...baseProfiles,
        active_profile_id: "profile-2",
        profiles: baseProfiles.profiles.map((profile) => ({
          ...profile,
          active: profile.id === "profile-2",
        })),
      });
    vi.mocked(activateIbmCredentialProfile).mockResolvedValue({
      ...secondaryProfile,
      active: true,
    });

    renderSwitch();

    await user.click(await screen.findByRole("button", { name: /IBM profile: Main IBM/i }));
    await user.click(screen.getByRole("button", { name: "Switch to EU-West" }));

    await waitFor(() => {
      expect(activateIbmCredentialProfile).toHaveBeenCalledWith("profile-2");
    });
    await waitFor(() => {
      expect(setActiveBackendCapabilitiesProfile).toHaveBeenCalledWith("profile-2");
    });
    await waitFor(() => {
      expect(forceRefreshBackendCapabilities).toHaveBeenCalledWith("profile-2");
    });
    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem(SIDEBAR_RECENT_PROFILE_STORAGE_KEY) ?? "[]")).toEqual([
        "profile-2",
        "profile-1",
        "profile-4",
      ]);
    });
  });

  it("closes the profile list when the sidebar collapses", async () => {
    const user = userEvent.setup();

    render(
      <SidebarProvider defaultOpen>
        <CollapseHarness />
      </SidebarProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /IBM profile: Main IBM/i }));
    expect(screen.getByRole("button", { name: "Switch to Backup" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Switch to Backup" })).not.toBeInTheDocument();
    });
  });

  it("does not wait for backend refresh before finishing the visible switch", async () => {
    const user = userEvent.setup();
    localStorage.setItem(
      SIDEBAR_RECENT_PROFILE_STORAGE_KEY,
      JSON.stringify(["profile-2", "profile-4", "profile-3"]),
    );
    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce(baseProfiles)
      .mockResolvedValueOnce({
        ...baseProfiles,
        active_profile_id: "profile-2",
        profiles: baseProfiles.profiles.map((profile) => ({
          ...profile,
          active: profile.id === "profile-2",
        })),
      });
    vi.mocked(activateIbmCredentialProfile).mockResolvedValue({
      ...secondaryProfile,
      active: true,
    });
    vi.mocked(forceRefreshBackendCapabilities).mockImplementation(() =>
      neverSettles<Awaited<ReturnType<typeof forceRefreshBackendCapabilities>>>(),
    );

    renderSwitch();

    await user.click(await screen.findByRole("button", { name: /IBM profile: Main IBM/i }));
    await user.click(screen.getByRole("button", { name: "Switch to EU-West" }));

    await waitFor(() => {
      expect(activateIbmCredentialProfile).toHaveBeenCalledWith("profile-2");
    });
    await waitFor(() => {
      expect(forceRefreshBackendCapabilities).toHaveBeenCalledWith("profile-2");
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: /IBM profile: EU-West\. Click to show recent profiles/i,
        }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Switch to Backup" })).not.toBeInTheDocument();
  });

  it("refreshes the visible sidebar profile when profiles change elsewhere", async () => {
    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce(baseProfiles)
      .mockResolvedValueOnce({
        ...baseProfiles,
        active_profile_id: "profile-2",
        profiles: baseProfiles.profiles.map((profile) => ({
          ...profile,
          active: profile.id === "profile-2",
        })),
      });

    renderSwitch();

    expect(
      await screen.findByRole("button", { name: /IBM profile: Main IBM/i }),
    ).toBeInTheDocument();

    act(() => {
      notifyIbmCredentialProfilesChanged();
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: /IBM profile: EU-West\. Click to show recent profiles/i,
        }),
      ).toBeInTheDocument();
    });

    await act(async () => {
      await Promise.resolve();
    });
  });
});
