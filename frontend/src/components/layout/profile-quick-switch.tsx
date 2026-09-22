import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, Check, ChevronDown, KeyRound, Plus, X } from "lucide-react";
import { Link } from "@tanstack/react-router";

import {
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
  setActiveBackendCapabilitiesProfile,
} from "@/api/backends";
import { activateIbmCredentialProfile, listIbmCredentialProfiles } from "@/api/profiles";
import {
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Spinner } from "@/components/ui/spinner";
import { getIbmBackendStatus } from "@/components/forms/run-form/backend-card-state";
import { showErrorToast } from "@/lib/error-handler";
import {
  notifyIbmCredentialProfilesChanged,
  subscribeToIbmCredentialProfilesChanged,
  type IbmBackendStatus,
} from "@/lib/ibm-profile-events";
import { cn } from "@/lib/utils";
import { useLocalStorage } from "@/hooks/use-local-storage";
import type { IbmCredentialProfile } from "@/types/profile";
import { preloadPageModule } from "@/routes/lazy-pages";

const MAX_RECENT_PROFILES = 3;
export const SIDEBAR_RECENT_PROFILE_STORAGE_KEY = "qvs-sidebar-recent-ibm-profiles";

function rememberRecentProfile(current: string[], profileId: string | null): string[] {
  if (profileId === null) return current;
  return [profileId, ...current.filter((existingId) => existingId !== profileId)].slice(
    0,
    MAX_RECENT_PROFILES,
  );
}

function compareProfiles(left: IbmCredentialProfile, right: IbmCredentialProfile): number {
  return right.updated_at.localeCompare(left.updated_at) || right.name.localeCompare(left.name);
}

function profileButtonLabel(
  loading: boolean,
  activeProfile: IbmCredentialProfile | null,
  profileCount: number,
): string {
  if (loading) return "Loading profiles";
  if (activeProfile) return activeProfile.name;
  return profileCount > 0 ? "Choose profile" : "IBM Profiles";
}

function profileButtonAriaLabel(
  loading: boolean,
  activeProfile: IbmCredentialProfile | null,
  open: boolean,
): string {
  if (loading) return "IBM profiles are loading";
  const action = open ? "hide" : "show";
  if (activeProfile) {
    return `IBM profile: ${activeProfile.name}. Click to ${action} recent profiles`;
  }
  return `IBM profiles. Click to ${action} recent profiles`;
}

function ProfileSwitchIcon({
  isPending,
  isActive,
  backendStatus,
}: Readonly<{
  isPending: boolean;
  isActive: boolean;
  backendStatus: IbmBackendStatus;
}>) {
  if (isPending) return <Spinner />;
  if (isActive) return <BackendStatusIcon status={backendStatus} />;
  return <KeyRound className="size-4" />;
}

function BackendStatusIcon({ status }: Readonly<{ status: IbmBackendStatus }>) {
  if (status === "ready") return <Check aria-hidden className="size-4 text-success" />;
  if (status === "inactive") return <X aria-hidden className="size-4 text-destructive" />;
  return <AlertTriangle aria-hidden className="size-4 text-warning" />;
}

function readActiveBackendStatus(profileId: string | null): {
  status: IbmBackendStatus;
} {
  if (profileId == null) {
    return { status: "inactive" };
  }
  const capability = getBackendCapabilitiesCached(profileId)?.backends.find(
    (item) => item.target === "ibm_runtime",
  );
  if (capability == null) {
    return { status: "loading" };
  }
  return { status: getIbmBackendStatus(capability) };
}

export function ProfileQuickSwitch() {
  const { state, isMobile, openMobile } = useSidebar();
  const [profiles, setProfiles] = useState<IbmCredentialProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [pendingProfileId, setPendingProfileId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileLoadError, setProfileLoadError] = useState(false);
  const [backendStatus, setBackendStatus] = useState<IbmBackendStatus>("loading");
  const [open, setOpen] = useState(false);
  const [recentProfileIds, setRecentProfileIds] = useLocalStorage<string[]>(
    SIDEBAR_RECENT_PROFILE_STORAGE_KEY,
    [],
  );

  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [activeProfileId, profiles],
  );

  const recentProfiles = useMemo(() => {
    const byId = new Map(profiles.map((profile) => [profile.id, profile]));
    const recent = recentProfileIds
      .map((profileId) => byId.get(profileId))
      .filter((profile): profile is IbmCredentialProfile => profile != null);
    const remaining = [...profiles]
      .sort(compareProfiles)
      .filter((profile) => !recent.some((existing) => existing.id === profile.id));
    return [...recent, ...remaining].slice(0, MAX_RECENT_PROFILES);
  }, [profiles, recentProfileIds]);

  const refreshProfiles = useCallback(async () => {
    try {
      const response = await listIbmCredentialProfiles();
      setProfileLoadError(false);
      setProfiles(response.profiles);
      setActiveProfileId(response.active_profile_id);
      const activeBackendStatus = readActiveBackendStatus(response.active_profile_id);
      setBackendStatus(activeBackendStatus.status);
      setRecentProfileIds((current) => rememberRecentProfile(current, response.active_profile_id));
    } catch {
      setProfileLoadError(true);
      setProfiles([]);
      setActiveProfileId(null);
    } finally {
      setLoading(false);
    }
  }, [setRecentProfileIds]);

  useEffect(() => {
    void refreshProfiles();
  }, [refreshProfiles]);

  useEffect(() => {
    return subscribeToIbmCredentialProfilesChanged((detail) => {
      if (detail.activeProfileId !== undefined) {
        setActiveProfileId(detail.activeProfileId ?? null);
      }
      if (
        detail.backendCapabilitiesRefresh === "started" ||
        detail.backendCapabilitiesRefresh === "progress"
      ) {
        setBackendStatus("loading");
      } else if (detail.backendCapabilitiesRefresh === "completed") {
        const refreshed = readActiveBackendStatus(detail.activeProfileId ?? activeProfileId);
        setBackendStatus(detail.backendStatus ?? refreshed.status);
      } else if (detail.backendCapabilitiesRefresh === "failed") {
        setBackendStatus("unavailable");
      }
      if (detail.profilesChanged === true) {
        setLoading(true);
        void refreshProfiles();
      }
    });
  }, [activeProfileId, refreshProfiles]);

  useEffect(() => {
    if (state === "collapsed" || (isMobile && !openMobile)) {
      setOpen(false);
    }
  }, [isMobile, openMobile, state]);

  async function handleActivate(profile: IbmCredentialProfile) {
    if (profile.id === activeProfileId || pendingProfileId !== null) return;

    const previousActiveProfileId = activeProfileId;
    const previousProfiles = profiles.map((existing) => ({ ...existing }));
    setPendingProfileId(profile.id);
    setActiveProfileId(profile.id);
    setProfiles((current) =>
      current.map((existing) => ({
        ...existing,
        active: existing.id === profile.id,
      })),
    );
    setRecentProfileIds((current) => rememberRecentProfile(current, profile.id));

    try {
      await activateIbmCredentialProfile(profile.id);
      setActiveBackendCapabilitiesProfile(profile.id);
      setOpen(false);
      setBackendStatus("loading");
      notifyIbmCredentialProfilesChanged({
        activeProfileId: profile.id,
        backendCapabilitiesRefresh: "started",
        backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
      });
      void forceRefreshBackendCapabilities(profile.id)
        .then(() => {
          notifyIbmCredentialProfilesChanged({
            activeProfileId: profile.id,
            backendCapabilitiesRefresh: "completed",
            backendWarmupProgress: { loadedProfiles: 1, totalProfiles: 1 },
          });
        })
        .catch(() => {
          notifyIbmCredentialProfilesChanged({
            activeProfileId: profile.id,
            backendCapabilitiesRefresh: "failed",
            backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
          });
        });
    } catch (error) {
      setActiveProfileId(previousActiveProfileId);
      setProfiles(previousProfiles);
      showErrorToast(error, {
        title: "Profile Switch Failed",
        fallbackDescription: "Failed to activate IBM profile.",
      });
    } finally {
      setPendingProfileId(null);
    }
  }

  const buttonLabel = profileButtonLabel(loading, activeProfile, profiles.length);
  const buttonAriaLabel = profileButtonAriaLabel(loading, activeProfile, open);
  let profileMenuContent: ReactNode;

  if (loading) {
    profileMenuContent = (
      <SidebarMenuSubItem>
        <SidebarMenuSubButton asChild>
          <button type="button" disabled>
            <Spinner />
            <span>Loading profiles</span>
          </button>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    );
  } else if (profileLoadError) {
    profileMenuContent = (
      <SidebarMenuSubItem>
        <SidebarMenuSubButton asChild>
          <Link
            to="/settings"
            onClick={() => setOpen(false)}
            onFocus={() => preloadPageModule("/settings")}
            onPointerEnter={() => preloadPageModule("/settings")}
            aria-label="Open IBM profile settings"
          >
            <KeyRound className="size-4" />
            <span>Profiles unavailable</span>
          </Link>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    );
  } else if (recentProfiles.length === 0) {
    profileMenuContent = (
      <SidebarMenuSubItem>
        <SidebarMenuSubButton asChild>
          <Link
            to="/settings"
            onClick={() => setOpen(false)}
            onFocus={() => preloadPageModule("/settings")}
            onPointerEnter={() => preloadPageModule("/settings")}
            aria-label="Add IBM profile in settings"
          >
            <Plus className="size-4" />
            <span>Add profile</span>
          </Link>
        </SidebarMenuSubButton>
      </SidebarMenuSubItem>
    );
  } else {
    profileMenuContent = recentProfiles.map((profile) => {
      const isActive = profile.id === activeProfileId;
      const isPending = profile.id === pendingProfileId;
      return (
        <SidebarMenuSubItem key={profile.id}>
          <SidebarMenuSubButton
            asChild
            isActive={isActive || isPending}
            className={cn(
              isActive &&
                "disabled:!opacity-100 data-[active=true]:!bg-success/10 data-[active=true]:!text-success dark:data-[active=true]:!bg-success/15",
            )}
            aria-busy={isPending}
          >
            <button
              type="button"
              onClick={() => void handleActivate(profile)}
              disabled={isActive || pendingProfileId !== null}
              aria-label={isActive ? `${profile.name} active` : `Switch to ${profile.name}`}
            >
              <ProfileSwitchIcon
                isPending={isPending}
                isActive={isActive}
                backendStatus={backendStatus}
              />
              <span className="flex-1 truncate">{profile.name}</span>
            </button>
          </SidebarMenuSubButton>
        </SidebarMenuSubItem>
      );
    });
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        tooltip={activeProfile ? `IBM profile: ${activeProfile.name}` : "IBM profiles"}
        aria-label={buttonAriaLabel}
        className="cursor-pointer"
        onClick={() => setOpen((current) => !current)}
        isActive={open}
      >
        {loading ? <Spinner /> : <KeyRound className="size-4" />}
        <span className="min-w-0 flex-1 truncate whitespace-nowrap group-data-[collapsible=icon]:hidden">
          {buttonLabel}
        </span>
        <ChevronDown
          className={cn(
            "ml-auto size-4 transition-transform duration-200 group-data-[collapsible=icon]:hidden",
            open ? "rotate-180" : "",
          )}
        />
      </SidebarMenuButton>

      {open ? <SidebarMenuSub>{profileMenuContent}</SidebarMenuSub> : null}
    </SidebarMenuItem>
  );
}
