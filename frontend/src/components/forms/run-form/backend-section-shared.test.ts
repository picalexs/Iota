import { describe, expect, it } from "vitest";

import {
  buildNoiseReferenceOptions,
  filterSuggestedBackendDevices,
  getNoiseReferenceDevice,
  getSuggestedBackendDevices,
} from "./backend-section-shared";

describe("backend-section-shared", () => {
  it("keeps suggested backends unique when least error and least busy match", () => {
    const devices = [
      {
        name: "ibm_aachen",
        simulator: false,
        operational: true,
        pending_jobs: 1,
        num_qubits: 156,
        error_rate: 0.0009,
      },
      {
        name: "ibm_berlin",
        simulator: false,
        operational: true,
        pending_jobs: 4,
        num_qubits: 120,
        error_rate: 0.0015,
      },
    ];

    expect(getSuggestedBackendDevices(devices).map((device) => device.name)).toEqual([
      "ibm_aachen",
    ]);
  });

  it("filters suggestion-backed devices out of the manual backend list", () => {
    const devices = [
      {
        name: "ibm_berlin",
        simulator: false,
        operational: true,
        pending_jobs: 1,
        num_qubits: 120,
        error_rate: 0.0015,
      },
      {
        name: "ibm_aachen",
        simulator: false,
        operational: true,
        pending_jobs: 1,
        num_qubits: 156,
        error_rate: 0.0009,
      },
      {
        name: "ibm_brisbane",
        simulator: false,
        operational: true,
        pending_jobs: 0,
        num_qubits: 127,
        error_rate: 0.0012,
      },
    ];

    expect(filterSuggestedBackendDevices(devices).map((device) => device.name)).toEqual([
      "ibm_berlin",
    ]);
  });

  it("does not fabricate a topology device before the noise reference loads", () => {
    expect(
      getNoiseReferenceDevice({ source: "backend_derived", reference_backend: "ibm_aachen" }, []),
    ).toBeNull();
  });

  it("does not fabricate options for a missing noise reference", () => {
    expect(
      buildNoiseReferenceOptions([], {
        source: "backend_derived",
        reference_backend: "ibm_aachen",
      }),
    ).toEqual([]);
  });
});
