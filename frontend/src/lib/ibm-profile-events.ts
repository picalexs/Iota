const IBM_CREDENTIAL_PROFILES_CHANGED_EVENT = "ibm-credential-profiles-changed";

export type IbmBackendWarmupProgress = Readonly<{
  loadedProfiles: number;
  totalProfiles: number;
}>;

export type IbmCredentialProfilesChangedDetail = Readonly<{
  profilesChanged?: boolean;
  activeProfileId?: string | null;
  backendCapabilitiesRefresh?: "started" | "progress" | "completed" | "failed";
  backendWarmupProgress?: IbmBackendWarmupProgress | null;
}>;

export function notifyIbmCredentialProfilesChanged(
  detail: IbmCredentialProfilesChangedDetail = {},
) {
  if (globalThis.window === undefined) return;
  globalThis.window.dispatchEvent(
    new CustomEvent<IbmCredentialProfilesChangedDetail>(IBM_CREDENTIAL_PROFILES_CHANGED_EVENT, {
      detail,
    }),
  );
}

export function subscribeToIbmCredentialProfilesChanged(
  callback: (detail: IbmCredentialProfilesChangedDetail) => void,
) {
  if (globalThis.window === undefined) {
    return () => undefined;
  }

  const listener = (event: Event) => {
    const detail = (event as CustomEvent<IbmCredentialProfilesChangedDetail>).detail ?? {};
    callback(detail);
  };
  globalThis.window.addEventListener(IBM_CREDENTIAL_PROFILES_CHANGED_EVENT, listener);

  return () => {
    globalThis.window.removeEventListener(IBM_CREDENTIAL_PROFILES_CHANGED_EVENT, listener);
  };
}
