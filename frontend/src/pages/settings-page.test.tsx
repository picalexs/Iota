import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { forceRefreshBackendCapabilities, setActiveBackendCapabilitiesProfile } from "@/api/backends";
import {
  activateIbmCredentialProfile,
  createIbmCredentialProfile,
  deleteIbmCredentialProfile,
  listIbmCredentialProfiles,
  updateIbmCredentialProfile,
} from "@/api/profiles";
import type { IbmCredentialProfileListResponse } from "@/types/profile";
import { SettingsPage } from "./settings-page";

vi.mock("@/api/backends", () => ({
  forceRefreshBackendCapabilities: vi.fn(),
  setActiveBackendCapabilitiesProfile: vi.fn(),
}));

vi.mock("@/api/profiles", () => ({
  activateIbmCredentialProfile: vi.fn(),
  createIbmCredentialProfile: vi.fn(),
  deleteIbmCredentialProfile: vi.fn(),
  listIbmCredentialProfiles: vi.fn(),
  updateIbmCredentialProfile: vi.fn(),
}));

const profileList: IbmCredentialProfileListResponse = {
  active_profile_id: "profile-1",
  encryption_key_source: "local_key_file",
  encryption_warning: null,
  profiles: [
    {
      id: "profile-1",
      name: "Main IBM",
      channel: "ibm_quantum_platform",
      active: true,
      created_at: "2026-05-31T08:00:00Z",
      updated_at: "2026-05-31T08:30:00Z",
    },
  ],
};

function getMainProfile() {
  const profile = profileList.profiles[0];
  if (!profile) {
    throw new Error("Expected a main IBM profile");
  }
  return profile;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(activateIbmCredentialProfile).mockReset();
  vi.mocked(createIbmCredentialProfile).mockReset();
  vi.mocked(deleteIbmCredentialProfile).mockReset();
  vi.mocked(forceRefreshBackendCapabilities).mockReset();
  vi.mocked(listIbmCredentialProfiles).mockReset();
  vi.mocked(setActiveBackendCapabilitiesProfile).mockReset();
  vi.mocked(updateIbmCredentialProfile).mockReset();
  vi.mocked(listIbmCredentialProfiles).mockResolvedValue(profileList);
  vi.mocked(forceRefreshBackendCapabilities).mockResolvedValue({ backends: [] });
});

describe("SettingsPage", () => {
  it("shows a page skeleton while the initial settings request is loading", () => {
    vi.mocked(listIbmCredentialProfiles).mockImplementationOnce(
      () => new Promise<IbmCredentialProfileListResponse>(() => {}),
    );

    render(<SettingsPage />);

    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading settings");
    expect(screen.queryByText("IBM Runtime account profiles")).not.toBeInTheDocument();
  });

  it("loads IBM profiles without exposing credential hints", async () => {
    render(<SettingsPage />);

    expect(await screen.findByText("Main IBM")).toBeInTheDocument();
    expect(screen.getByText("local_key_file")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Token" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "CRN" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activate Main IBM" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test Main IBM" })).not.toBeInTheDocument();
    expect(screen.getByText("Active: Main IBM")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete Main IBM" })).toBeVisible();
    expect(listIbmCredentialProfiles).toHaveBeenCalledOnce();
  });

  it("wraps long encryption key source values inside the card", async () => {
    vi.mocked(listIbmCredentialProfiles).mockResolvedValueOnce({
      ...profileList,
      encryption_key_source:
        "/app/local-state/credential-fernet-key-file-that-keeps-going-and-going",
    });

    render(<SettingsPage />);

    const keySource = await screen.findByText(
      "/app/local-state/credential-fernet-key-file-that-keeps-going-and-going",
    );
    expect(keySource).toHaveClass("w-full", "whitespace-normal", "break-all");
  });

  it("creates a profile and refreshes credential-backed capabilities", async () => {
    const user = userEvent.setup();
    vi.mocked(createIbmCredentialProfile).mockResolvedValue(getMainProfile());

    render(<SettingsPage />);

    await screen.findByText("Main IBM");
    await user.type(screen.getByLabelText("Profile name"), "Lab IBM");
    await user.type(screen.getByLabelText("IBM token"), "token-value");
    await user.type(screen.getByLabelText("CRN or instance"), "crn-value");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(createIbmCredentialProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Lab IBM",
          token: "token-value",
          crn: "crn-value",
          activate: true,
        }),
      );
    });
    expect(forceRefreshBackendCapabilities).toHaveBeenCalled();
  });

  it("edits a profile without resending blank secrets", async () => {
    const user = userEvent.setup();
    vi.mocked(updateIbmCredentialProfile).mockResolvedValue(getMainProfile());

    render(<SettingsPage />);

    await user.click(await screen.findByRole("button", { name: "Edit Main IBM" }));
    const nameInput = screen.getByLabelText("Profile name");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed IBM");
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(updateIbmCredentialProfile).toHaveBeenCalledWith(
        "profile-1",
        expect.objectContaining({
          name: "Renamed IBM",
          token: null,
          crn: null,
        }),
      );
    });
  });

  it("activates another profile when its row is clicked", async () => {
    const user = userEvent.setup();
    const backupProfile = {
      id: "profile-2",
      name: "EU-West",
      channel: "ibm_cloud",
      active: false,
      created_at: "2026-05-31T09:00:00Z",
      updated_at: "2026-05-31T09:30:00Z",
    };
    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce({
        ...profileList,
        profiles: [...profileList.profiles, backupProfile],
      })
      .mockResolvedValueOnce({
        ...profileList,
        active_profile_id: "profile-2",
        profiles: [
          { ...getMainProfile(), active: false },
          { ...backupProfile, active: true },
        ],
      });
    vi.mocked(activateIbmCredentialProfile).mockResolvedValue({
      ...backupProfile,
      active: true,
    });

    render(<SettingsPage />);

    await user.click(await screen.findByText("EU-West"));

    await waitFor(() => {
      expect(activateIbmCredentialProfile).toHaveBeenCalledWith("profile-2");
    });
    expect(await screen.findByRole("status")).toHaveTextContent('Loaded profile "EU-West".');
  });

  it("keeps the table visible and shows a loading state while switching profiles", async () => {
    const user = userEvent.setup();
    const backupProfile = {
      id: "profile-2",
      name: "EU-West",
      channel: "ibm_cloud",
      active: false,
      created_at: "2026-05-31T09:00:00Z",
      updated_at: "2026-05-31T09:30:00Z",
    };

    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce({
        ...profileList,
        profiles: [...profileList.profiles, backupProfile],
      })
      .mockImplementationOnce(() => new Promise<IbmCredentialProfileListResponse>(() => {}));
    vi.mocked(activateIbmCredentialProfile).mockResolvedValue({
      ...backupProfile,
      active: true,
    });

    render(<SettingsPage />);

    await user.click(await screen.findByText("EU-West"));

    expect(screen.getByText("Main IBM")).toBeInTheDocument();
    expect(screen.getByText("Loading")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refreshing/i })).toBeDisabled();
  });

  it("deletes a profile with confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(deleteIbmCredentialProfile).mockResolvedValue(undefined);
    vi.mocked(listIbmCredentialProfiles)
      .mockResolvedValueOnce(profileList)
      .mockResolvedValueOnce({
        ...profileList,
        active_profile_id: null,
        profiles: [],
      });
    vi.mocked(forceRefreshBackendCapabilities).mockImplementation(
      () => new Promise<Awaited<ReturnType<typeof forceRefreshBackendCapabilities>>>(() => {}),
    );

    render(<SettingsPage />);

    await user.click(await screen.findByRole("button", { name: "Delete Main IBM" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteIbmCredentialProfile).toHaveBeenCalledWith("profile-1", "Main IBM");
    });
    await waitFor(() => {
      expect(screen.queryByText("Main IBM")).not.toBeInTheDocument();
    });
  });
});
