import type { InfoEntry } from "./types";
import type { BackendTarget } from "@/types/run";

export const BACKEND_INFO: Record<BackendTarget, InfoEntry> = {
  statevector: {
    id: "statevector",
    title: "Statevector Simulator",
    summary:
      "An exact, noiseless simulator that stores the full complex state of the circuit and is the clearest baseline for validating chemistry workflows on modest qubit counts.",
    sections: [
      {
        heading: "How it works",
        body: "Statevector simulation keeps the complete 2^n-dimensional quantum state in memory and updates it exactly under gate application. For chemistry experiments, that makes it ideal for checking whether an algorithm is conceptually working before you introduce shot noise, hardware latency, or calibration drift.",
      },
      {
        heading: "Performance characteristics",
        body: "The cost is exponential memory growth. Every additional qubit doubles the number of amplitudes you must store, so exact simulation remains practical only for relatively small active spaces. It is usually the fastest way to debug logic on a small molecule, but it becomes infeasible long before the interesting large-system hardware regime.",
      },
      {
        heading: "When to use",
        body: "Use statevector when you want a deterministic baseline, exact expectation values, or a trusted comparison point for other backends. It is especially useful for VQE baselines, for checking whether a subspace method is failing because of algorithm choice rather than hardware noise, and for validating the meaning of result dashboards.",
      },
      {
        heading: "Noise",
        body: "The statevector backend is noiseless. To study noise, select the Aer simulator when it is available and attach a supported noise profile.",
      },
      {
        heading: "How Quantum Studio uses it",
        body: "Quantum Studio relies on statevector runs as the reference path for many algorithm diagnostics and for small dense problem variants. Several larger algorithms also switch to local fixed-particle-sector logic before they would require a full dense statevector over the entire Hilbert space.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Exact Amplitudes",
        body: "If a result looks surprising on Aer or IBM Runtime, statevector is usually the first place to check whether the issue is physics, configuration, or hardware realism.",
      },
      {
        kind: "equation",
        label: "Memory Scale",
        latex: String.raw`\mathrm{memory}(n) \propto 2^n \text{ complex amplitudes}`,
        caption:
          "The exponential state size is why exact simulation is useful but bounded to modest qubit counts.",
      },
      {
        kind: "callout",
        title: "Why This Backend Stays In The Reference Flow",
        body: "Statevector is the cleanest place to decide whether a strange result comes from the algorithm itself or only appears once noise, shots, or hardware routing are introduced.",
        tone: "info",
      },
      {
        kind: "list",
        heading: "Best Fit",
        items: [
          "Ground-truth comparisons on small active spaces.",
          "Algorithm debugging before adding shots, queueing, or noise.",
          "Interpreting what the run-detail diagnostics should look like in an ideal path.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit Aer — StatevectorSimulator",
        href: "https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.StatevectorSimulator.html",
      },
    ],
  },

  aer_simulator: {
    id: "aer_simulator",
    title: "Aer Simulator",
    summary:
      "Qiskit's high-performance local simulator for shot-based execution, simulator-method selection, and noise studies that should stay on your machine.",
    sections: [
      {
        heading: "Simulation methods",
        body: "Aer supports several internal simulation styles such as statevector, density matrix, matrix product state, and stabilizer-like methods. Quantum Studio exposes the method choice so you can decide whether you want an ideal simulation, a richer noisy representation, or a more scalable approximate simulation for circuits with limited entanglement.",
      },
      {
        heading: "Noise models",
        body: "Aer is the local backend for noise experimentation. Quantum Studio supports custom preset profiles such as depolarizing, thermal relaxation, and readout bias, as well as backend-derived profiles that mimic a chosen IBM device calibration snapshot when that metadata is available.",
      },
      {
        heading: "Performance",
        body: "Aer is much more capable than a pure teaching simulator, but noise is expensive. Density-matrix-style simulation grows far faster than statevector simulation, and realistic noise models can dominate runtime and memory. Matrix-product-state methods can help on the right circuits, but they are still sensitive to entanglement growth.",
      },
      {
        heading: "Shot-based sampling",
        body: "Unlike a pure exact statevector path, Aer can behave like a finite-shot backend. That means the run form's shot count matters, repeated runs can differ slightly, and sample-based algorithms such as SQD and SKQD can be tested locally before paying hardware queue time.",
      },
      {
        heading: "How Quantum Studio uses it",
        body: "Aer is the bridge between exact local debugging and IBM hardware. It is where you can test shot budgets, noise sensitivity, topology-aware reasoning, and backend-derived noise without leaving the local stack.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Shot-Based Local Simulation",
        body: "Aer is usually the best first stop when you want realism without queueing: same run form, same algorithms, but with local control over shots and noise.",
      },
      {
        kind: "list",
        heading: "Common Choices",
        items: [
          "Statevector method for ideal local validation.",
          "Density matrix or automatic methods for small noisy circuits.",
          "Matrix product state when circuit entanglement is limited enough to benefit.",
        ],
      },
      {
        kind: "callout",
        title: "Noise Cost",
        body: "Noise profiles can make simulation much more expensive, especially when they force density-matrix-style evolution.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "Best Fit",
        items: [
          "Checking whether an algorithm survives finite-shot sampling before moving to hardware.",
          "Comparing ideal and noisy runs with the same molecule and parameters.",
          "Testing backend-derived noise against a concrete IBM target without waiting in queue.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit Aer documentation",
        href: "https://qiskit.github.io/qiskit-aer/",
      },
      {
        label: "Qiskit Aer noise module",
        href: "https://qiskit.github.io/qiskit-aer/apidocs/aer_noise.html",
      },
    ],
  },

  ibm_runtime: {
    id: "ibm_runtime",
    title: "IBM Quantum Runtime",
    summary:
      "IBM's managed hardware-and-primitives execution path, used when you want real-device sampling or estimation and the chosen algorithm supports a hardware route.",
    sections: [
      {
        heading: "Primitives",
        body: "IBM Runtime exposes hardware-backed primitives such as Sampler and Estimator. Quantum Studio uses those primitives for supported algorithms once credential checks, backend selection, and algorithm constraints all pass.",
      },
      {
        heading: "Transpilation and optimization",
        body: "Real hardware execution requires transpilation to a device's native gate set and coupling map. IBM tutorials often emphasize connectivity-aware circuit design, such as heavy-hex-friendly mappings. Quantum Studio surfaces that concern in the run form through backend selection, topology views, processor-family labels, and calibration-derived metadata before you submit the job.",
      },
      {
        heading: "Queue and latency",
        body: "Hardware runs are remote jobs with queue time, network latency, and calibration drift. Even a small circuit can spend more wall-clock time waiting than computing. Quantum Studio records backend metadata and IBM job identifiers when available so the run history and event log can explain where that time went.",
      },
      {
        heading: "Error mitigation",
        body: "Hardware execution is where topology, readout quality, two-qubit error rates, and queue state matter most. The app does not expose every mitigation feature IBM Runtime can support, so you should treat the current path as a practical hardware route, not a full hardware-tuning console.",
      },
      {
        heading: "Credentials",
        body: "IBM Runtime needs IBM Quantum credentials configured in the root environment file. Without credentials, Quantum Studio lists IBM Runtime as unavailable instead of pretending hardware is ready.",
      },
      {
        heading: "How Quantum Studio uses it",
        body: "IBM Runtime is currently the managed submission path for supported algorithms, especially when you want real bitstrings or hardware-backed projected matrix elements. The app helps you choose a backend, inspect its topology, and understand availability, but it still keeps the final algorithm workflow inside the same run-detail experience as local runs.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Managed Hardware Path",
        body: "This is the backend to choose when hardware realism is the point of the run, not just a nuisance to estimate locally.",
      },
      {
        kind: "list",
        heading: "Before Running",
        items: [
          "Credentials must be configured and the backend must be available.",
          "Circuit width and coupling layout should fit the selected device.",
          "Queue time and calibration drift can dominate wall-clock behavior.",
        ],
      },
      {
        kind: "callout",
        title: "Why The Topology View Matters",
        body: "IBM devices are not fully connected. The qubit map, coupling graph, and per-qubit calibration data help you judge whether an ansatz or sampled workflow is likely to survive transpilation and hardware noise.",
        tone: "info",
      },
      {
        kind: "list",
        heading: "What The App Surfaces Before Submission",
        items: [
          "Processor family, queue, and availability status for the selected device.",
          "Topology and coupling-map context so you can judge routing pressure early.",
          "Calibration-derived metadata that pairs naturally with backend-derived local noise rehearsal.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit IBM Runtime documentation",
        href: "https://docs.quantum.ibm.com/api/qiskit-ibm-runtime",
      },
      {
        label: "IBM Quantum platform",
        href: "https://quantum.ibm.com/",
      },
      {
        label: "IBM Quantum learning course — Quantum diagonalization algorithms",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms",
      },
    ],
  },
};
