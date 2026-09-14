import { describe, expect, it } from "vitest";

import { getBackendCardStateText, isBackendSelectable } from "./backend-card-state";

describe("backend card state", () => {
  it("shows IBM profile warmup progress while capabilities load", () => {
    expect(
      getBackendCardStateText({
        value: "ibm_runtime",
        capability: undefined,
        selectable: false,
        capabilitiesLoading: true,
        capabilitiesWarmupProgress: { loadedProfiles: 1, totalProfiles: 3 },
      }),
    ).toBe("1/3 IBM profiles loaded.");
  });

  it("shows a singular ready label for one IBM backend", () => {
    expect(
      getBackendCardStateText({
        value: "ibm_runtime",
        capability: {
          target: "ibm_runtime",
          enabled: true,
          credentials_usable: true,
          backends: [{ name: "ibm_aachen" }],
        },
        selectable: true,
      }),
    ).toBe("1 IBM hardware backend ready.");
  });

  it("shows refresh progress when IBM backends are being refreshed", () => {
    expect(
      getBackendCardStateText({
        value: "ibm_runtime",
        capability: {
          target: "ibm_runtime",
          enabled: true,
          credentials_usable: true,
          backends: [{ name: "ibm_aachen" }, { name: "ibm_brisbane" }],
        },
        selectable: true,
        capabilitiesRefreshing: true,
      }),
    ).toBe("Refreshing 2 IBM hardware backends...");
  });

  it("uses capability reasons for selectable and unavailable cards", () => {
    expect(
      getBackendCardStateText({
        value: "aer_simulator",
        capability: {
          target: "aer_simulator",
          enabled: true,
          reason: "Aer is ready for local execution.",
        },
        selectable: true,
      }),
    ).toBe("Aer is ready for local execution.");

    expect(
      getBackendCardStateText({
        value: "aer_simulator",
        capability: {
          target: "aer_simulator",
          enabled: false,
          available: false,
          reason: "Aer is unavailable.",
        },
        selectable: false,
      }),
    ).toBe("Aer is unavailable.");
  });

  it("keeps IBM credential messages distinct", () => {
    expect(
      getBackendCardStateText({
        value: "ibm_runtime",
        capability: {
          target: "ibm_runtime",
          enabled: false,
          credential_configured: false,
        },
        selectable: false,
      }),
    ).toContain("Save and activate an encrypted IBM profile");

    expect(
      getBackendCardStateText({
        value: "ibm_runtime",
        capability: {
          target: "ibm_runtime",
          enabled: true,
          credential_configured: true,
          credentials_usable: false,
          reason: "Profile token expired.",
        },
        selectable: false,
      }),
    ).toBe("Profile token expired.");
  });

  it("requires enabled credentials for IBM and normal availability for local backends", () => {
    expect(
      isBackendSelectable({
        target: "ibm_runtime",
        enabled: true,
        credentials_usable: false,
      }),
    ).toBe(false);
    expect(
      isBackendSelectable({
        target: "ibm_runtime",
        enabled: true,
        credentials_usable: true,
      }),
    ).toBe(true);
    expect(
      isBackendSelectable({
        target: "aer_simulator",
        enabled: true,
        available: true,
        credential_configured: true,
      }),
    ).toBe(true);
  });
});
