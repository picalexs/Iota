import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
  parseBackendListResponse,
  parseTranspilePreviewResponse,
  previewTranspilation,
  resetBackendCapabilitiesStateForTests,
  startBackendCapabilitiesAutoRefresh,
} from "./backends";
import { getFetchCall, mockJsonResponse } from "./test-helpers";

const backendRows = [
  {
    target: "statevector",
    name: "statevector",
    display_name: "Statevector",
    available: true,
    simulator: true,
    supports_noise_profile: false,
    supports_transpile_preview: false,
  },
  {
    target: "aer_simulator",
    name: "aer_simulator",
    display_name: "Aer simulator",
    available: true,
    simulator: true,
    supports_noise_profile: true,
    supports_transpile_preview: true,
  },
  {
    target: "ibm_runtime",
    name: "ibm_brisbane",
    display_name: "IBM Brisbane",
    available: false,
    credential_configured: true,
    credentials_usable: null,
    simulator: false,
    supports_noise_profile: false,
    supports_transpile_preview: true,
    status_message: "IBM discovery is warming up",
  },
];

describe("backend capability transport boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    resetBackendCapabilitiesStateForTests();
  });

  it("rejects malformed generated backend envelopes", () => {
    expect(() => parseBackendListResponse({ backends: [{ target: "unknown" }] })).toThrow(
      "Invalid backend list response",
    );
    expect(() => parseBackendListResponse({ backends: backendRows, warnings: [42] })).toThrow(
      "Invalid backend list response",
    );
    expect(() => parseTranspilePreviewResponse({ feasible: true, requested_qubits: 4 })).toThrow(
      "Invalid transpilation preview response",
    );
  });

  afterEach(() => {
    resetBackendCapabilitiesStateForTests();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("groups flat server rows into the frontend capability catalog", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({ backends: backendRows, warnings: [] }),
    );

    const result = await forceRefreshBackendCapabilities();

    expect(result.backends).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ target: "statevector", enabled: true, backends: [] }),
        expect.objectContaining({ target: "aer_simulator", enabled: true }),
        expect.objectContaining({
          target: "ibm_runtime",
          enabled: false,
          credential_configured: true,
          credentials_usable: null,
          reason: "IBM discovery is warming up",
          backends: [expect.objectContaining({ name: "ibm_brisbane" })],
        }),
      ]),
    );
  });

  it("sends transpilation defaults and adapts depth metadata", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({
        backend_name: "ibm_brisbane",
        feasible: true,
        requested_qubits: 4,
        target: "ibm_runtime",
        metadata: { input_depth: 12, estimated_depth: 18, pending_jobs: 2 },
        warnings: [],
      }),
    );

    await expect(
      previewTranspilation({
        molecule_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        backend_target: "ibm_runtime",
        algorithm: "vqe",
        num_qubits: 4,
        backend_options: {
          selection_policy: "least_busy",
          backend_name: null,
          shots: 4000,
          optimization_level: 1,
          seed_simulator: null,
          seed_transpiler: null,
          aer_method: null,
        },
      }),
    ).resolves.toMatchObject({
      available: true,
      backend_name: "ibm_brisbane",
      circuit_depth: 12,
      transpiled_depth: 18,
      estimated_queue_seconds: 120,
    });

    expect(JSON.parse(String(getFetchCall().options.body))).toMatchObject({
      target: "ibm_runtime",
      backend_options: { aer_method: "automatic" },
    });
  });

  it("keeps the last successful cache entry when a refresh fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({ backends: backendRows, warnings: [] }),
    );
    const first = await forceRefreshBackendCapabilities();

    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("offline"));
    await expect(forceRefreshBackendCapabilities()).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });

    expect(getBackendCapabilitiesCached()).toEqual(first);
  });

  it("broadcasts periodic active-profile refresh state", async () => {
    vi.useFakeTimers();
    const events: CustomEvent[] = [];
    const listener = (event: Event) => events.push(event as CustomEvent);
    window.addEventListener("ibm-credential-profiles-changed", listener);
    vi.mocked(fetch).mockResolvedValue(mockJsonResponse({ backends: backendRows, warnings: [] }));

    startBackendCapabilitiesAutoRefresh();
    await vi.advanceTimersByTimeAsync(1000 * 60);

    expect(events.map((event) => event.detail.backendCapabilitiesRefresh)).toEqual([
      "started",
      "completed",
    ]);
    window.removeEventListener("ibm-credential-profiles-changed", listener);
  });
});
