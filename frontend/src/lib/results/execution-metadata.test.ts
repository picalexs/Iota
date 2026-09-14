import { describe, expect, it } from "vitest";

import {
  formatPhysicalQubitList,
  formatSelectionPolicy,
  formatTranspilationLayout,
  getRunExecutionMetadata,
} from "./execution-metadata";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

const run: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "COMPLETED",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "ibm_runtime",
  config_json: {
    backend_options: {
      selection_policy: "least_busy",
      backend_name: "ibm_brisbane",
      shots: 4096,
      optimization_level: 2,
      seed_simulator: null,
      seed_transpiler: 17,
      aer_method: "automatic",
    },
  },
  basis_set: "sto-3g",
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: {
    resolved_backend_name: "ibm_brisbane",
    transpilation_summary: {
      optimization_level: 2,
      transpiled_depth: 88,
      two_qubit_depth: 31,
      final_layout: [112, 113, 118, 119],
      used_physical_qubits: [112, 113, 118, 119],
    },
    execution: {
      primitive_family: "qiskit_ibm_runtime",
      ibm_job_id: "job-123",
    },
  },
  created_at: "2026-05-17T12:00:00Z",
  updated_at: "2026-05-17T12:05:00Z",
};

const events: RunEventResponse[] = [
  {
    id: 1,
    run_id: "run-1",
    sequence: 1,
    type: "iteration_update",
    payload: {
      stage: "setup",
      num_qubits: 4,
    },
    created_at: "2026-05-17T12:00:01Z",
  },
];

describe("execution metadata helpers", () => {
  it("extracts transpilation layout and used physical qubits from run metadata", () => {
    const metadata = getRunExecutionMetadata(run, events);

    expect(metadata.backendName).toBe("ibm_brisbane");
    expect(metadata.selectionPolicy).toBe("least_busy");
    expect(metadata.shots).toBe(4096);
    expect(metadata.optimizationLevel).toBe(2);
    expect(metadata.depth).toBe(88);
    expect(metadata.twoQubitDepth).toBe(31);
    expect(metadata.ibmJobId).toBe("job-123");
    expect(metadata.transpilationLayout).toEqual([
      { logical: 0, physical: 112 },
      { logical: 1, physical: 113 },
      { logical: 2, physical: 118 },
      { logical: 3, physical: 119 },
    ]);
    expect(metadata.usedPhysicalQubits).toEqual([112, 113, 118, 119]);
  });

  it("formats the layout and qubit lists for tile display", () => {
    expect(formatSelectionPolicy("least_busy")).toBe("least busy");
    expect(
      formatTranspilationLayout([
        { logical: 0, physical: 112 },
        { logical: 1, physical: 113 },
      ]),
    ).toBe("q0→112, q1→113");
    expect(formatPhysicalQubitList([112, 113, 118])).toBe("112, 113, 118");
  });

  it("extracts backend execution metadata from the run result payload", () => {
    const runWithoutMetadata: RunResponse = {
      ...run,
      config_json: {},
      metadata: null,
    };
    const result: RunResultResponse = {
      run_id: "run-1",
      energy: -1.1,
      iterations: 1,
      optimal_parameters: [],
      converged: true,
      algorithm_metrics: {
        backend_execution: {
          resolved_backend_name: "ibm_sherbrooke",
          ibm_job_id: "job-from-result",
          transpilation_summary: {
            optimization_level: 3,
            transpiled_depth: 42,
            two_qubit_depth: 12,
            logical_to_physical: [
              { logical: 0, physical: 73 },
              { logical: 1, physical: 74 },
            ],
            used_physical_qubits: [73, 74],
          },
        },
      },
      created_at: "2026-05-17T12:05:00Z",
    };

    const metadata = getRunExecutionMetadata(runWithoutMetadata, [], result);

    expect(metadata.backendName).toBe("ibm_sherbrooke");
    expect(metadata.ibmJobId).toBe("job-from-result");
    expect(metadata.optimizationLevel).toBe(3);
    expect(metadata.depth).toBe(42);
    expect(metadata.twoQubitDepth).toBe(12);
    expect(metadata.transpilationLayout).toEqual([
      { logical: 0, physical: 73 },
      { logical: 1, physical: 74 },
    ]);
    expect(metadata.usedPhysicalQubits).toEqual([73, 74]);
  });

  it("extracts local simulator metadata from an execution event", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        backend_target: "aer_simulator",
        config_json: {
          backend_options: {
            selection_policy: "manual",
            backend_name: null,
            shots: 512,
            optimization_level: 1,
            seed_simulator: 23,
            seed_transpiler: null,
            aer_method: "statevector",
          },
        },
        metadata: null,
      },
      [
        {
          id: 2,
          run_id: "run-1",
          sequence: 2,
          type: "iteration_update",
          payload: {
            stage: "execution",
            simulator_method: "statevector",
            primitive_family: "aer_simulator",
            num_qubits: 4,
          },
          created_at: "2026-05-17T12:00:02Z",
        },
      ],
    );

    expect(metadata).toMatchObject({
      selectionPolicy: "manual",
      shots: 512,
      optimizationLevel: 1,
      aerMethod: "statevector",
      simulatorMethod: "statevector",
      primitiveFamily: "aer_simulator",
      qubits: 4,
      seedSimulator: 23,
    });
  });

  it("keeps scalar precedence from transpilation to execution to config", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        config_json: {
          backend_options: {
            selection_policy: "least_error",
            backend_name: null,
            shots: 100,
            optimization_level: 0,
            seed_simulator: null,
            seed_transpiler: null,
            aer_method: "density_matrix",
          },
        },
        metadata: {
          transpilation: {
            selection_policy: "manual",
            shots: 200,
            optimization_level: 2,
            simulator_method: "transpilation-simulator",
            primitive_family: "transpilation-primitive",
          },
          execution: {
            selection_policy: "least_busy",
            shots: 300,
            optimization_level: 3,
            simulator_method: "execution-simulator",
            primitive_family: "execution-primitive",
          },
          transpilation_summary: { optimization_level: 1 },
        },
      },
      [],
    );

    expect(metadata.selectionPolicy).toBe("manual");
    expect(metadata.shots).toBe(200);
    expect(metadata.optimizationLevel).toBe(1);
    expect(metadata.simulatorMethod).toBe("transpilation-simulator");
    expect(metadata.primitiveFamily).toBe("transpilation-primitive");
    expect(metadata.aerMethod).toBe("density_matrix");
  });

  it("ignores malformed scalar values", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        config_json: {
          backend_options: {
            selection_policy: "manual",
            backend_name: null,
            shots: "many" as unknown as number,
            optimization_level: "high" as unknown as 0,
            seed_simulator: "random" as unknown as number,
            seed_transpiler: null,
            aer_method: 42 as unknown as "automatic",
          },
        },
        metadata: {
          transpilation: {
            selection_policy: 7,
            shots: "many",
            optimization_level: {},
            simulator_method: 7,
            primitive_family: "",
          },
          execution: {
            shots: null,
            optimization_level: null,
          },
        },
      },
      [],
    );

    expect(metadata.selectionPolicy).toBe("manual");
    expect(metadata.shots).toBeNull();
    expect(metadata.optimizationLevel).toBeNull();
    expect(metadata.aerMethod).toBeNull();
    expect(metadata.simulatorMethod).toBeNull();
    expect(metadata.primitiveFamily).toBeNull();
    expect(metadata.seedSimulator).toBeNull();
    expect(metadata.seedTranspiler).toBeNull();
  });

  it("keeps IBM field precedence across run and runtime events", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        ibm_job_id: "run-job",
        metadata: {
          ibm_status: "metadata-status",
          ibm_queue_position: 1,
          ibm_pub_count: 2,
        },
      },
      [
        {
          id: 2,
          run_id: "run-1",
          sequence: 2,
          type: "ibm_job_submitted",
          payload: {
            ibm_job_id: "submitted-job",
            ibm_status: "submitted-status",
            queue_position: 3,
            pub_count: 4,
          },
          created_at: "2026-05-17T12:00:02Z",
        },
        {
          id: 3,
          run_id: "run-1",
          sequence: 3,
          type: "ibm_status_poll",
          payload: {
            ibm_job_id: "polled-job",
            ibm_status: "DONE",
            queue_position: 5,
            pub_count: 6,
          },
          created_at: "2026-05-17T12:00:03Z",
        },
      ],
    );

    expect(metadata.ibmJobId).toBe("run-job");
    expect(metadata.ibmStatus).toBe("DONE");
    expect(metadata.ibmQueuePosition).toBe(5);
    expect(metadata.ibmPubCount).toBe(6);
  });

  it("ignores malformed IBM fields", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        ibm_job_id: "",
        metadata: {
          ibm_job_id: 7,
          ibm_status: 8,
          ibm_queue_position: "waiting",
          ibm_pub_count: "many",
        },
      },
      [
        {
          id: 2,
          run_id: "run-1",
          sequence: 2,
          type: "ibm_status_poll",
          payload: {
            ibm_job_id: 7,
            ibm_status: 8,
            queue_position: "waiting",
            pub_count: "many",
          },
          created_at: "2026-05-17T12:00:02Z",
        },
      ],
    );

    expect(metadata.ibmJobId).toBeNull();
    expect(metadata.ibmStatus).toBeNull();
    expect(metadata.ibmQueuePosition).toBeNull();
    expect(metadata.ibmPubCount).toBeNull();
  });

  it("prefers the resolved IBM backend name over least_busy policy tokens", () => {
    const metadata = getRunExecutionMetadata(
      {
        ...run,
        config_json: {
          backend_options: {
            selection_policy: "least_busy",
            backend_name: "least_busy",
            shots: 4096,
            optimization_level: 2,
            seed_simulator: null,
            seed_transpiler: null,
            aer_method: "automatic",
          },
        },
        metadata: {
          resolved_backend_name: "ibm_brisbane",
        },
      },
      [],
    );

    expect(metadata.backendName).toBe("ibm_brisbane");
  });

  it("extracts IBM queue and timing metadata from runtime events", () => {
    const metadata = getRunExecutionMetadata(run, [
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "ibm_status_poll",
        payload: {
          ibm_job_id: "runtime-job-123",
          ibm_status: "DONE",
          queue_position: 4,
          pub_count: 1,
          ibm_timing: {
            created_at: "2026-05-18T19:50:00+00:00",
            running_at: "2026-05-18T20:16:50+00:00",
            finished_at: "2026-05-18T20:18:32+00:00",
            pending_seconds: 1610,
            usage_seconds: 101,
            total_seconds: 1712,
          },
        },
        created_at: "2026-05-18T20:18:33Z",
      },
    ]);

    expect(metadata.ibmJobId).toBe("runtime-job-123");
    expect(metadata.ibmStatus).toBe("DONE");
    expect(metadata.ibmQueuePosition).toBe(4);
    expect(metadata.ibmPubCount).toBe(1);
    expect(metadata.ibmTiming).toMatchObject({
      pendingSeconds: 1610,
      usageSeconds: 101,
      totalSeconds: 1712,
    });
  });

  it("aggregates completed IBM timing across multiple runtime jobs", () => {
    const metadata = getRunExecutionMetadata(run, [
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "ibm_status_poll",
        payload: {
          phase: "complete",
          ibm_job_id: "runtime-job-1",
          ibm_status: "DONE",
          ibm_timing: {
            created_at: "2026-05-18T20:00:00+00:00",
            running_at: "2026-05-18T20:00:01+00:00",
            finished_at: "2026-05-18T20:00:05+00:00",
            pending_seconds: 1,
            usage_seconds: 4,
            total_seconds: 5,
          },
        },
        created_at: "2026-05-18T20:00:06Z",
      },
      {
        id: 3,
        run_id: "run-1",
        sequence: 3,
        type: "ibm_status_poll",
        payload: {
          phase: "complete",
          ibm_job_id: "runtime-job-2",
          ibm_status: "DONE",
          ibm_timing: {
            created_at: "2026-05-18T20:00:10+00:00",
            running_at: "2026-05-18T20:00:10+00:00",
            finished_at: "2026-05-18T20:00:14+00:00",
            pending_seconds: 0,
            usage_seconds: 4,
            total_seconds: 4,
          },
        },
        created_at: "2026-05-18T20:00:15Z",
      },
    ]);

    expect(metadata.ibmTiming).toMatchObject({
      pendingSeconds: 1,
      usageSeconds: 8,
      totalSeconds: 9,
      createdAt: "2026-05-18T20:00:00+00:00",
      finishedAt: "2026-05-18T20:00:14+00:00",
    });
  });
});
