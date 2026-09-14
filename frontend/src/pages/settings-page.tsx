import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { KeyRound, Pencil, Plus, RefreshCw, Save, ShieldCheck, Trash2 } from "lucide-react";

import {
  forceRefreshBackendCapabilities,
  setActiveBackendCapabilitiesProfile,
} from "@/api/backends";
import {
  activateIbmCredentialProfile,
  createIbmCredentialProfile,
  deleteIbmCredentialProfile,
  listIbmCredentialProfiles,
  updateIbmCredentialProfile,
} from "@/api/profiles";
import { FormField } from "@/components/forms/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";
import { SettingsPageSkeleton } from "@/components/ui/route-skeleton-variants";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getErrorMessage } from "@/lib/error-handler";
import { notifyIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";
import type { IbmCredentialProfile, IbmCredentialProfileListResponse } from "@/types/profile";

const DEFAULT_CHANNEL = "ibm_quantum_platform";
const CHANNEL_OPTIONS = [
  { value: "ibm_quantum_platform", label: "IBM Quantum Platform" },
  { value: "ibm_cloud", label: "IBM Cloud" },
];

interface ProfileForm {
  name: string;
  token: string;
  crn: string;
  channel: string;
  activate: boolean;
}

const EMPTY_FORM: ProfileForm = {
  name: "",
  token: "",
  crn: "",
  channel: DEFAULT_CHANNEL,
  activate: true,
};

function trimOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function refreshButtonLabel(loading: boolean, refreshing: boolean): string {
  return loading || refreshing ? "Refreshing" : "Refresh";
}

function profileEditorTitle(editingProfile: IbmCredentialProfile | null): string {
  return editingProfile ? "Edit Profile" : "New Profile";
}

function secretPlaceholder(editingProfile: IbmCredentialProfile | null): string | undefined {
  return editingProfile ? "Leave unchanged" : undefined;
}

function deleteProfileDescription(profile: IbmCredentialProfile | null): string | undefined {
  return profile ? `${profile.name} will be removed from local encrypted storage.` : undefined;
}

function ProfileStatusBadge({ active, pending }: Readonly<{ active: boolean; pending: boolean }>) {
  if (pending) {
    return (
      <Badge variant="secondary" className="gap-1 rounded-sm">
        <Spinner className="size-3 border-[1.5px]" />
        Loading
      </Badge>
    );
  }

  if (!active) return null;

  return (
    <Badge variant="success" className="rounded-sm">
      Active
    </Badge>
  );
}

function ProfilesLoadingState() {
  return (
    <div className="space-y-2" aria-hidden="true">
      {Array.from({ length: 4 }, (_, index) => `profile-skeleton-${index}`).map((id) => (
        <Skeleton key={id} className="h-12 w-full" />
      ))}
    </div>
  );
}

function ProfilesEmptyState() {
  return (
    <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
      No profiles saved.
    </div>
  );
}

interface ProfileRowProps {
  readonly profile: IbmCredentialProfile;
  readonly pending: boolean;
  readonly onActivate: (profile: IbmCredentialProfile) => void;
  readonly onEdit: (profile: IbmCredentialProfile) => void;
  readonly onDelete: (profile: IbmCredentialProfile) => void;
}

function ProfileRow({ profile, pending, onActivate, onEdit, onDelete }: ProfileRowProps) {
  const canActivate = !profile.active && !pending;

  function activateIfAllowed() {
    if (canActivate) {
      onActivate(profile);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>) {
    if (!canActivate || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    onActivate(profile);
  }

  function handleEdit(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    onEdit(profile);
  }

  function handleDelete(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    onDelete(profile);
  }

  return (
    <TableRow
      tabIndex={canActivate ? 0 : -1}
      onClick={activateIfAllowed}
      onKeyDown={handleKeyDown}
      aria-busy={pending}
      className={[canActivate ? "cursor-pointer" : "", pending ? "bg-muted/40 opacity-80" : ""]
        .filter(Boolean)
        .join(" ")}
    >
      <TableCell className="min-w-0 whitespace-normal align-top">
        <div className="flex flex-wrap items-center gap-2">
          <span className="break-words font-medium">{profile.name}</span>
          <ProfileStatusBadge active={profile.active} pending={pending} />
        </div>
      </TableCell>
      <TableCell className="whitespace-normal break-all align-top text-sm">
        {profile.channel}
      </TableCell>
      <TableCell className="align-top">
        <div className="flex flex-wrap justify-end gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Edit ${profile.name}`}
            onClick={handleEdit}
            disabled={pending}
          >
            <Pencil className="size-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={`Delete ${profile.name}`}
            onClick={handleDelete}
            disabled={pending}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

interface ProfilesTableProps {
  readonly profiles: readonly IbmCredentialProfile[];
  readonly pendingProfileId: string | null;
  readonly onActivate: (profile: IbmCredentialProfile) => void;
  readonly onEdit: (profile: IbmCredentialProfile) => void;
  readonly onDelete: (profile: IbmCredentialProfile) => void;
}

function ProfilesTable({
  profiles,
  pendingProfileId,
  onActivate,
  onEdit,
  onDelete,
}: ProfilesTableProps) {
  return (
    <Table className="table-fixed">
      <TableHeader>
        <TableRow>
          <TableHead className="w-[45%] whitespace-normal">Name</TableHead>
          <TableHead className="whitespace-normal">Channel</TableHead>
          <TableHead className="w-32 text-right whitespace-normal">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {profiles.map((profile) => (
          <ProfileRow
            key={profile.id}
            profile={profile}
            pending={pendingProfileId === profile.id}
            onActivate={onActivate}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </TableBody>
    </Table>
  );
}

interface ProfilesContentProps extends ProfilesTableProps {
  readonly loading: boolean;
}

function ProfilesContent(props: ProfilesContentProps) {
  if (props.loading) return <ProfilesLoadingState />;
  if (props.profiles.length === 0) return <ProfilesEmptyState />;
  return <ProfilesTable {...props} />;
}

export function SettingsPage() {
  const [profiles, setProfiles] = useState<IbmCredentialProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [encryptionKeySource, setEncryptionKeySource] = useState("unknown");
  const [encryptionWarning, setEncryptionWarning] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingProfile, setDeletingProfile] = useState<IbmCredentialProfile | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pendingProfileId, setPendingProfileId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasProfilesRef = useRef(profiles.length > 0);
  hasProfilesRef.current = profiles.length > 0;

  const editingProfile = useMemo(
    () => profiles.find((profile) => profile.id === editingId) ?? null,
    [editingId, profiles],
  );
  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [activeProfileId, profiles],
  );

  const refreshProfiles = useCallback(
    async ({
      preserveContent = true,
    }: { preserveContent?: boolean } = {}): Promise<IbmCredentialProfileListResponse | null> => {
      if (preserveContent && hasProfilesRef.current) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const response: IbmCredentialProfileListResponse = await listIbmCredentialProfiles();
        setProfiles(response.profiles);
        setActiveProfileId(response.active_profile_id);
        setEncryptionKeySource(response.encryption_key_source);
        setEncryptionWarning(response.encryption_warning);
        return response;
      } catch (err) {
        setError(getErrorMessage(err, "IBM profile settings are unavailable."));
        return null;
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [],
  );

  useEffect(() => {
    void refreshProfiles({ preserveContent: false });
  }, [refreshProfiles]);

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setStatusMessage(null);
    setError(null);
  }

  function editProfile(profile: IbmCredentialProfile) {
    setEditingId(profile.id);
    setForm({
      name: profile.name,
      token: "",
      crn: "",
      channel: profile.channel || DEFAULT_CHANNEL,
      activate: profile.active,
    });
    setStatusMessage(null);
    setError(null);
  }

  async function afterCredentialChange() {
    const response = await refreshProfiles();
    const activeProfileId =
      response?.active_profile_id ??
      response?.profiles.find((profile) => profile.active)?.id ??
      null;

    notifyIbmCredentialProfilesChanged({
      activeProfileId,
      backendCapabilitiesRefresh: "started",
      backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
    });
    setActiveBackendCapabilitiesProfile(activeProfileId ?? null);
    void forceRefreshBackendCapabilities(activeProfileId ?? undefined)
      .then(() => {
        notifyIbmCredentialProfilesChanged({
          activeProfileId,
          backendCapabilitiesRefresh: "completed",
          backendWarmupProgress: { loadedProfiles: 1, totalProfiles: 1 },
        });
      })
      .catch(() => {
        notifyIbmCredentialProfilesChanged({
          activeProfileId,
          backendCapabilitiesRefresh: "failed",
          backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
        });
      });
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      if (editingId) {
        await updateIbmCredentialProfile(editingId, {
          name: trimOrNull(form.name),
          token: trimOrNull(form.token),
          crn: trimOrNull(form.crn),
          channel: form.channel,
          activate: form.activate,
        });
      } else {
        await createIbmCredentialProfile({
          name: form.name.trim(),
          token: form.token.trim(),
          crn: form.crn.trim(),
          channel: form.channel,
          activate: form.activate,
        });
      }
      resetForm();
      await afterCredentialChange();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save IBM profile."));
    } finally {
      setSaving(false);
    }
  }

  async function handleActivate(profile: IbmCredentialProfile) {
    const previousActiveProfileId = activeProfileId;
    const previousProfiles = profiles.map((existing) => ({ ...existing }));
    setPendingProfileId(profile.id);
    setError(null);
    setStatusMessage(null);
    setActiveProfileId(profile.id);
    setProfiles((current) =>
      current.map((existing) => ({
        ...existing,
        active: existing.id === profile.id,
      })),
    );
    try {
      await activateIbmCredentialProfile(profile.id);
      await afterCredentialChange();
      setStatusMessage(`Loaded profile "${profile.name}".`);
    } catch (err) {
      setActiveProfileId(previousActiveProfileId);
      setProfiles(previousProfiles);
      setError(getErrorMessage(err, "Failed to activate IBM profile."));
    } finally {
      setPendingProfileId(null);
    }
  }

  async function handleDelete() {
    if (!deletingProfile) return;
    setPendingProfileId(deletingProfile.id);
    setError(null);
    setStatusMessage(null);
    try {
      await deleteIbmCredentialProfile(deletingProfile.id, deletingProfile.name);
      setDeletingProfile(null);
      if (editingId === deletingProfile.id) {
        resetForm();
      }
      await afterCredentialChange();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete IBM profile."));
    } finally {
      setPendingProfileId(null);
    }
  }

  const canSave =
    form.name.trim().length > 0 &&
    (editingId != null || (form.token.trim().length > 0 && form.crn.trim().length > 0));

  if (loading && profiles.length === 0) {
    return <SettingsPageSkeleton />;
  }

  const errorPresentation = error
    ? getErrorPresentation(new Error(error), "the settings page")
    : null;
  const refreshLabel = refreshButtonLabel(loading, refreshing);
  const editorTitle = profileEditorTitle(editingProfile);
  const secretFieldPlaceholder = secretPlaceholder(editingProfile);
  const deleteDescription = deleteProfileDescription(deletingProfile);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">IBM Runtime account profiles</p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => void refreshProfiles()}
          disabled={loading || refreshing}
        >
          <RefreshCw className={`size-4 ${loading || refreshing ? "animate-spin" : ""}`} />
          {refreshLabel}
        </Button>
      </div>

      {error && errorPresentation ? (
        <PageErrorState
          title={errorPresentation.title}
          description={errorPresentation.description}
          detail={errorPresentation.detail}
          onRetry={() => void refreshProfiles()}
        />
      ) : null}

      {statusMessage && (
        <output className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
          {statusMessage}
        </output>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex min-w-0 items-center gap-2 text-base">
              <KeyRound className="size-4" />
              <span>Profiles</span>
              <span className="min-w-0 truncate text-sm font-normal text-muted-foreground">
                Active: {activeProfile?.name ?? "none"}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ProfilesContent
              loading={loading}
              profiles={profiles}
              pendingProfileId={pendingProfileId}
              onActivate={(profile) => void handleActivate(profile)}
              onEdit={editProfile}
              onDelete={setDeletingProfile}
            />
          </CardContent>
        </Card>

        <div className="flex flex-col gap-5">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                {editingProfile ? <Save className="size-4" /> : <Plus className="size-4" />}
                {editorTitle}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <FormField label="Profile name" htmlFor="ibm-profile-name">
                <Input
                  id="ibm-profile-name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, name: event.target.value }))
                  }
                  disabled={saving}
                />
              </FormField>

              <FormField label="IBM token" htmlFor="ibm-profile-token">
                <Input
                  id="ibm-profile-token"
                  type="password"
                  value={form.token}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, token: event.target.value }))
                  }
                  placeholder={secretFieldPlaceholder}
                  disabled={saving}
                  autoComplete="off"
                />
              </FormField>

              <FormField label="CRN or instance" htmlFor="ibm-profile-crn">
                <Input
                  id="ibm-profile-crn"
                  type="password"
                  value={form.crn}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, crn: event.target.value }))
                  }
                  placeholder={secretFieldPlaceholder}
                  disabled={saving}
                  autoComplete="off"
                />
              </FormField>

              <FormField label="Channel" htmlFor="ibm-profile-channel">
                <Select
                  value={form.channel}
                  onValueChange={(value) => setForm((current) => ({ ...current, channel: value }))}
                >
                  <SelectTrigger id="ibm-profile-channel" disabled={saving}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNEL_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>

              <div className="flex gap-2">
                <Button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={!canSave || saving}
                  className="flex-1"
                >
                  <Save className="size-4" />
                  {saving ? "Saving" : "Save"}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm} disabled={saving}>
                  New
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="size-4" />
                Encryption
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-3">
                <span className="text-muted-foreground">Key source</span>
                <Badge
                  variant="secondary"
                  className="w-full min-w-0 justify-start rounded-sm font-mono whitespace-normal break-all text-left"
                >
                  {encryptionKeySource}
                </Badge>
              </div>
              {encryptionWarning && (
                <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-warning">
                  {encryptionWarning}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={deletingProfile !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingProfile(null);
        }}
        title="Delete IBM profile?"
        description={deleteDescription}
        confirmText="Delete"
        cancelText="Keep"
        variant="destructive"
        onConfirm={handleDelete}
        loading={deletingProfile?.id === pendingProfileId}
      />
    </div>
  );
}
