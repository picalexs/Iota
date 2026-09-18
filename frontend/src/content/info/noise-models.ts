import type { InfoEntry } from "./types";

export type NoiseModelId =
  | "depolarizing_cx"
  | "thermal_relaxation"
  | "readout_bias"
  | "backend_derived";

export const NOISE_MODEL_INFO: Record<NoiseModelId, InfoEntry> = {
  depolarizing_cx: {
    id: "depolarizing_cx",
    title: "Depolarizing CX Noise",
    summary:
      "A compact two-qubit gate-noise model that injects symmetric Pauli error after each CX and is useful for quick circuit-depth stress tests.",
    sections: [
      {
        heading: "Depolarizing channel",
        body: "A depolarizing channel with error probability p replaces the ideal gate output with a completely mixed state with probability p, and leaves it unchanged with probability 1-p. Equivalently, it applies one of the Pauli operators {X, Y, Z} uniformly at random with total probability p. For a two-qubit gate this generalises to the 15-element Pauli tensor-product group.",
      },
      {
        heading: "Why CX gates dominate",
        body: "In superconducting architectures, single-qubit gates achieve fidelities > 99.9% while two-qubit CX gates are typically 99.0–99.5%. This order-of-magnitude difference makes CX error the primary noise source in most circuits. VQE algorithms rely heavily on CX gates for entangling operations, so this preset directly targets the relevant error mechanism.",
      },
      {
        heading: "Configuration",
        body: "Set the strength field to the depolarizing error probability for each CX gate. A value of 0 disables this preset. The worker does not add hidden single-qubit errors.",
      },
      {
        heading: "When to use it in Quantum Studio",
        body: "Choose this preset when you want a fast local check of how sensitive an algorithm is to entangling-gate errors without committing to a device-specific calibration model. It is especially useful for comparing VQE ansatz depth choices or judging whether an SQD or KQD path becomes fragile as two-qubit count grows.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Symmetric Pauli Mixing",
        body: "Depolarizing noise is a compact way to study two-qubit gate error because it spreads probability uniformly across non-identity Pauli errors.",
      },
      {
        kind: "equation",
        label: "One-Qubit Channel",
        latex: String.raw`\mathcal{E}(\rho) = (1-p)\rho + \frac{p}{3}(X\rho X + Y\rho Y + Z\rho Z)`,
        caption:
          "For a CX gate, the same idea extends across the non-identity two-qubit Pauli products.",
      },
      {
        kind: "callout",
        title: "Useful Stress Test",
        body: "This preset is not device-specific, but it quickly exposes algorithms that rely on deep entangling circuits.",
        tone: "info",
      },
      {
        kind: "list",
        heading: "Best Fit",
        items: [
          "Quick local comparisons between shallow and deep variational circuits.",
          "Sanity-checking whether a workflow is dominated by two-qubit gate depth.",
          "Fast Aer studies when you want a simple knob instead of a full calibration snapshot.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit Aer — depolarizing_error",
        href: "https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.depolarizing_error.html",
      },
    ],
  },

  thermal_relaxation: {
    id: "thermal_relaxation",
    title: "Thermal Relaxation",
    summary:
      "A time-aware noise model for T1 decay and T2 dephasing, useful when circuit duration and idle windows matter as much as raw gate count.",
    sections: [
      {
        heading: "T1 and T2 times",
        body: "T1 (longitudinal relaxation) is the characteristic time for a qubit in the excited state |1⟩ to decay to the ground state |0⟩ via energy emission. T2 (transverse relaxation) captures the combined effect of T1 decay and pure dephasing (T2* effects). Physically T2 ≤ 2·T1. On current IBM hardware T1 and T2 are typically 50–300 µs.",
      },
      {
        heading: "Gate-time model",
        body: "Set T1, T2, and gate_time_us in microseconds. The worker applies the thermal channel to id, sx, and x, and applies the tensor-product channel to CX. It requires T2 ≤ 2·T1.",
      },
      {
        heading: "Effect on VQE",
        body: "Thermal relaxation introduces a state-preparation and measurement (SPAM) bias and smooths the energy landscape, making convergence harder and shifting the optimal parameters. Techniques like dynamical decoupling (inserting refocusing pulses) partially mitigate T2 effects.",
      },
      {
        heading: "When to use it in Quantum Studio",
        body: "Use thermal relaxation when you care about elapsed circuit time, not just the number of faulty gates. It is a good fit for comparing time-evolution-based methods, deeper ansatzes, or any workflow where idle qubits and long entangling schedules may dominate the error budget.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Time-Dependent Decay",
        body: "Thermal relaxation depends on how long gates and idle windows last, so circuit depth and scheduling both matter.",
      },
      {
        kind: "equation",
        label: "Decay Probability",
        latex: String.raw`P_{1\rightarrow0}(t) = 1 - e^{-t/T_1}`,
        caption: "Longer gate durations accumulate more amplitude damping.",
      },
      {
        kind: "list",
        heading: "Watch For",
        items: [
          "Deep ansatz circuits that keep qubits coherent for longer.",
          "Backend choices whose two-qubit gate durations dominate the schedule.",
          "Shot noise and relaxation bias combining in sampler-heavy workflows.",
        ],
      },
      {
        kind: "callout",
        title: "Not Just A Gate Count Problem",
        body: "Two circuits with similar gate counts can behave differently under thermal relaxation if one schedules more idle time or spends longer in slow two-qubit operations.",
        tone: "info",
      },
    ],
    references: [
      {
        label: "Qiskit Aer — thermal_relaxation_error",
        href: "https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.thermal_relaxation_error.html",
      },
    ],
  },

  readout_bias: {
    id: "readout_bias",
    title: "Readout Bias",
    summary:
      "A measurement-noise model for asymmetric bit-flip confusion at readout, especially relevant for workflows that depend directly on sampled bitstring distributions.",
    sections: [
      {
        heading: "Readout confusion matrix",
        body: "Set p01 to P(1|0) and p10 to P(0|1). Aer receives the assignment matrix [[1-p01, p01], [p10, 1-p10]], with rows for the true value and columns for the recorded value.",
      },
      {
        heading: "Typical magnitudes",
        body: "On IBM Quantum hardware readout errors range from 0.5% to 5% per qubit. The dominant direction is P(1|0) > P(0|1): thermal relaxation during readout causes |1⟩ to decay to |0⟩ before measurement completes, but residual excited-state population can also cause |0⟩ to appear as |1⟩.",
      },
      {
        heading: "Mitigation",
        body: "Readout errors can be partly corrected by calibrating the assignment matrix experimentally and applying its inverse as a classical post-processing step (measurement error mitigation, M3). This is distinct from gate-error mitigation and can be applied on top of other noise mitigation methods.",
      },
      {
        heading: "When to use it in Quantum Studio",
        body: "Readout bias is most relevant for algorithms whose classical post-processing starts from counts rather than from expectation values alone. That makes it a particularly natural stress test for SQD and SKQD, where corrupted bitstrings directly change the selected determinant space.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Measurement Assignment",
        body: "Readout bias changes observed bitstrings after the circuit has finished, so it is especially visible in algorithms that depend directly on bitstring distributions.",
      },
      {
        kind: "equation",
        label: "Assignment Matrix",
        latex: String.raw`A = \begin{pmatrix} P(0|0) & P(0|1) \\ P(1|0) & P(1|1) \end{pmatrix}`,
        caption:
          "Mitigation estimates the inverse assignment process and applies it during classical post-processing.",
      },
      {
        kind: "list",
        heading: "Best Fit",
        items: [
          "SQD or SKQD studies where bitstring quality is the main concern.",
          "Checking whether a result is robust to measurement confusion without changing gate noise.",
          "Comparing expectation-value workflows against sample-driven workflows under the same readout stress.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit Aer — ReadoutError",
        href: "https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.ReadoutError.html",
      },
    ],
  },

  backend_derived: {
    id: "backend_derived",
    title: "Backend-Derived Noise",
    summary:
      "A calibration-driven Aer noise model built from a specific IBM backend's current device properties, combining gate, relaxation, and readout signals into one local simulation target.",
    sections: [
      {
        heading: "Automatic calibration import",
        body: "When backend_derived is selected, Quantum Studio loads the named IBM backend through the active IBM Runtime profile. Aer builds a noise model from the backend properties. The worker fails the run if it cannot load the requested backend.",
      },
      {
        heading: "Fidelity to real hardware",
        body: "The model uses calibration data exposed by the selected backend at load time. Calibration drift can make the local model differ from later hardware execution. The run metadata records the requested and resolved backend names, version, topology, and model fingerprint.",
      },
      {
        heading: "Computational cost",
        body: "A full device noise model increases density-matrix simulation cost considerably. For a 20-qubit system the number of density-matrix operations scales as 4²⁰ ≈ 10¹² — impractical for exact simulation. In practice backend_derived is recommended for small circuits (≤ 15 qubits) or used with the MPS simulation method for larger systems.",
      },
      {
        heading: "Requires IBM credentials",
        body: "Fetching calibration data requires a valid IBM Quantum account, even though the actual simulation runs locally on Aer. Save and activate an IBM profile in Settings before using this preset.",
      },
      {
        heading: "When to use it in Quantum Studio",
        body: "Use backend-derived noise when the question is 'how might this specific device behave?' rather than 'how does generic noise hurt me?'. It pairs naturally with the backend topology panel because you can inspect the same reference device before simulating its calibration locally on Aer.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Calibration Snapshot",
        body: "Backend-derived noise converts current device properties into a local Aer noise model, giving simulations a closer relationship to a real target backend.",
      },
      {
        kind: "list",
        heading: "Included Signals",
        items: [
          "Per-gate error rates where backend properties expose them.",
          "T1/T2 relaxation parameters for individual qubits.",
          "Readout assignment errors that vary across the device.",
        ],
      },
      {
        kind: "callout",
        title: "Snapshot, Not Forecast",
        body: "Calibration data can drift between simulation and hardware execution, so the model is predictive context rather than a guarantee.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "Best Fit",
        items: [
          "Testing a run against a specific IBM device before spending hardware queue time.",
          "Comparing local Aer behavior against the topology and calibration metadata shown in the run form.",
          "Small-to-moderate noisy studies where realism matters more than raw simulator speed.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit IBM Runtime — backend properties",
        href: "https://docs.quantum.ibm.com/api/qiskit-ibm-runtime/qiskit_ibm_runtime.IBMBackend",
      },
      {
        label: "Qiskit Aer — NoiseModel.from_backend",
        href: "https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.NoiseModel.html",
      },
    ],
  },
};

export const NOISE_MODEL_IDS: NoiseModelId[] = [
  "depolarizing_cx",
  "thermal_relaxation",
  "readout_bias",
  "backend_derived",
];
