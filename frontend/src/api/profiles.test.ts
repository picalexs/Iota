import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  activateIbmCredentialProfile,
  createIbmCredentialProfile,
  deleteIbmCredentialProfile,
  listIbmCredentialProfiles,
  parseIbmCredentialProfileListResponse,
  parseIbmCredentialProfileResponse,
  parseIbmCredentialProfileTestResponse,
  testIbmCredentialProfile,
  updateIbmCredentialProfile,
} from "./profiles";
import { getFetchCall, mockJsonResponse } from "./test-helpers";

const profile = {
  id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  name: "Main IBM",
  channel: "ibm_quantum_platform",
  active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("IBM profile transport boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    localStorage.clear();
  });

  it("rejects malformed generated profile responses without exposing secrets", () => {
    expect(() => parseIbmCredentialProfileResponse({ id: profile.id, token: "secret" })).toThrow(
      "Invalid IBM credential profile response",
    );
    expect(() =>
      parseIbmCredentialProfileListResponse({
        profiles: [profile],
        encryption_key_source: "local_key_file",
        encryption_warning: 42,
      }),
    ).toThrow("Invalid IBM credential profile list response");
    expect(() =>
      parseIbmCredentialProfileTestResponse({ id: profile.id, ok: "yes", message: "ok" }),
    ).toThrow("Invalid IBM credential profile test response");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("normalizes the profile list and tracks its active profile", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({
        profiles: [profile],
        active_profile_id: profile.id,
        encryption_key_source: "local_key_file",
      }),
    );

    await expect(listIbmCredentialProfiles()).resolves.toMatchObject({
      profiles: [{ id: profile.id, active: true }],
      active_profile_id: profile.id,
      encryption_warning: null,
    });
    expect(getFetchCall().url).toBe("/api/settings/ibm-profiles");
  });

  it("applies server defaults to profile creation and keeps credentials in the request body only", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockJsonResponse(profile));

    await createIbmCredentialProfile({
      name: "Main IBM",
      token: "token",
      crn: "crn",
    });

    const { url, options } = getFetchCall();
    expect(url).toBe("/api/settings/ibm-profiles");
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toMatchObject({
      name: "Main IBM",
      token: "token",
      crn: "crn",
      activate: true,
      channel: "ibm_quantum_platform",
    });
  });

  it("routes update, activation, test, and deletion to their named endpoints", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse(profile))
      .mockResolvedValueOnce(mockJsonResponse(profile))
      .mockResolvedValueOnce(mockJsonResponse({ id: profile.id, ok: true, message: "ok" }))
      .mockResolvedValueOnce(mockJsonResponse(null, 204));

    await updateIbmCredentialProfile(profile.id, { name: "Renamed IBM" });
    await activateIbmCredentialProfile(profile.id);
    await expect(testIbmCredentialProfile(profile.id)).resolves.toMatchObject({
      id: profile.id,
      ok: true,
      active_instance: null,
    });
    await deleteIbmCredentialProfile(profile.id, "Renamed IBM");

    expect(vi.mocked(fetch).mock.calls.map(([url]) => url)).toEqual([
      `/api/settings/ibm-profiles/${profile.id}`,
      `/api/settings/ibm-profiles/${profile.id}/activate`,
      `/api/settings/ibm-profiles/${profile.id}/test`,
      `/api/settings/ibm-profiles/${profile.id}?confirm_name=Renamed+IBM`,
    ]);
    expect(vi.mocked(fetch).mock.calls.map(([, options]) => options?.method)).toEqual([
      "PATCH",
      "POST",
      "POST",
      "DELETE",
    ]);
  });
});
