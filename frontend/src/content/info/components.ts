import type { InfoEntry } from "./types";

export type InfoComponentId = "ansatzes" | "optimizers" | "basis-sets" | "reference-states";

export const COMPONENT_IDS: InfoComponentId[] = [
  "ansatzes",
  "optimizers",
  "basis-sets",
  "reference-states",
];

export const COMPONENT_INFO: Record<InfoComponentId, InfoEntry> = {
  ansatzes: {
    id: "ansatzes",
    title: "Ansatz families",
    summary:
      "The circuit family that defines which trial states VQE can actually reach, and therefore which part of Hilbert space the optimizer is searching.",
    blocks: [
      {
        kind: "text",
        heading: "Why the ansatz matters so much",
        body: "In VQE, the optimizer never searches over all possible states. It only searches over the states that the chosen circuit family can prepare. That is why `ansatz_name` and `reps` are not cosmetic controls: they decide both the reachable physics and the hardware cost.",
      },
      {
        kind: "equation",
        label: "Parameterized trial state",
        latex: String.raw`|\psi(\boldsymbol{\theta})\rangle = U_{\mathrm{ans}}(\boldsymbol{\theta}) |\psi_{\mathrm{ref}}\rangle, \quad E(\boldsymbol{\theta}) = \langle \psi(\boldsymbol{\theta}) | H | \psi(\boldsymbol{\theta}) \rangle`,
        displayText: "|ψ(θ)⟩ = U_ans(θ)|ψ_ref⟩    E(θ) = ⟨ψ(θ)|H|ψ(θ)⟩",
        caption:
          "Changing the ansatz changes the family of states that can appear in the objective landscape before the optimizer even starts.",
      },
      {
        kind: "text",
        heading: "Hardware-efficient versus chemistry-inspired circuits",
        body: "The thesis chapter compares chemistry-inspired constructions such as UCCSD with hardware-efficient templates. Chemistry-inspired ansatzes encode orbital excitations more directly, but they usually compile into longer circuits. This app instead exposes hardware-efficient templates because they are lighter-weight, available directly in Qiskit, and practical on statevector, Aer, and IBM Runtime paths.",
      },
      {
        kind: "list",
        heading: "The ansatzes used in this app",
        items: [
          "`RealAmplitudes`: alternating `R_y` layers and CX entanglement. It keeps amplitudes real and is often the simplest baseline when you want fewer parameters and a cleaner convergence story.",
          "`TwoLocal`: a general alternating pattern of single-qubit rotation blocks and entangling blocks. In this app it is built with `R_y` plus `R_z` rotations and `CX` entanglers, so it is more flexible than `RealAmplitudes` but usually also more expensive.",
          "`EfficientSU2`: repeated single-qubit `SU(2)`-style rotations plus CX entanglement. It is the most expressive of the three exposed templates, but that broader search space also means more parameters and a higher risk of slow or noisy optimization.",
        ],
      },
      {
        kind: "list",
        heading: "What `reps` really changes",
        items: [
          "Each extra `reps` value adds another rotation-plus-entanglement layer.",
          "More `reps` usually means more parameters, more two-qubit gates, and a deeper transpiled circuit.",
          "On `statevector`, that mostly affects optimizer difficulty and simulation cost.",
          "On `aer_simulator` or `ibm_runtime`, extra depth also amplifies sampling noise, routing overhead, and two-qubit error exposure.",
        ],
      },
      {
        kind: "callout",
        title: "Depth helps only when it adds useful structure",
        body: "A larger `reps` value is not automatically better. If the new layers mostly add random-looking flexibility, the landscape can flatten, gradients can become less informative, and the optimizer may spend more evaluations exploring a harder problem without improving the energy meaningfully.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "How to choose in practice",
        items: [
          "Start with `RealAmplitudes` when you want a compact baseline and easier debugging.",
          "Move to `EfficientSU2` when the shallow real-valued family stalls too early and you can afford extra circuit depth.",
          "Use `TwoLocal` when you specifically want the app's `R_y`/`R_z` structure and a middle ground between the other two templates.",
          "Increase `reps` one step at a time and always re-check the transpiled circuit, not just the logical template.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - VQE lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
      },
      {
        label: "Qiskit circuit library - efficient_su2",
        href: "https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.circuit.library.efficient_su2",
      },
      {
        label: "Qiskit circuit library - real_amplitudes",
        href: "https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.circuit.library.real_amplitudes",
      },
      {
        label: "Qiskit circuit library - TwoLocal",
        href: "https://qiskit.qotlabs.org/docs/api/qiskit/qiskit.circuit.library.TwoLocal",
      },
      {
        label: "Kandala et al. 2017 - hardware-efficient VQE",
        href: "https://www.nature.com/articles/nature23879",
      },
      {
        label: "Tilly et al. 2022 - VQE review and best practices",
        href: "https://arxiv.org/abs/2111.05176",
      },
      {
        label: "McClean et al. 2018 - barren plateaus",
        href: "https://www.nature.com/articles/s41467-018-07090-4",
      },
    ],
  },

  optimizers: {
    id: "optimizers",
    title: "Classical optimizers",
    summary:
      "The classical loop that turns noisy energy estimates into the next parameter vector, and often decides whether a variational run looks stable or chaotic.",
    blocks: [
      {
        kind: "text",
        heading: "What the optimizer is really doing",
        body: "For VQE, the quantum side only evaluates the current circuit. The optimizer is the part that decides where to sample next. It therefore controls how aggressively the run explores the landscape, how much it trusts noisy estimates, and how many objective calls are spent before the budget ends.",
      },
      {
        kind: "equation",
        label: "Outer-loop update",
        latex: String.raw`\boldsymbol{\theta}_{k+1} = \boldsymbol{\theta}_k + \Delta \boldsymbol{\theta}_k, \quad \Delta \boldsymbol{\theta}_k = \mathcal{O}\left(\widehat{E}(\boldsymbol{\theta}_0), \ldots, \widehat{E}(\boldsymbol{\theta}_k)\right)`,
        displayText: "θₖ₊₁ = θₖ + Δθₖ, where Δθₖ is chosen from the measured energy history",
        caption:
          "Different optimizers vary mainly in how they build that update from current and past objective information.",
      },
      {
        kind: "equation",
        label: "SPSA gradient estimate",
        latex: String.raw`\hat g_k = \frac{f(\boldsymbol{\theta}_k + c_k \Delta_k) - f(\boldsymbol{\theta}_k - c_k \Delta_k)}{2c_k}\,\Delta_k^{-1}`,
        displayText: "ĝₖ = [f(θₖ + cₖΔₖ) - f(θₖ - cₖΔₖ)] / (2cₖ) · Δₖ⁻¹",
        caption:
          "SPSA is attractive on noisy backends because it estimates a full gradient direction from only two objective calls, independent of parameter count.",
      },
      {
        kind: "list",
        heading: "The optimizers exposed in this app",
        items: [
          "`COBYLA`: derivative-free local search based on linear models. It is a strong default when gradients are unavailable or too noisy, and it maps well to the app's simple option surface.",
          "`SPSA`: stochastic gradient-style optimizer built for noisy measurements. It is usually the safest option once shot noise or hardware noise dominates the objective trace.",
          "`SLSQP`: sequential least-squares programming. It is better suited to smoother objectives, where numerical gradients are still meaningful and you want more deliberate local refinement.",
          "`L-BFGS-B`: limited-memory quasi-Newton method with bound handling. It can be very efficient on clean simulator objectives, but it is usually less forgiving when the energy is visibly noisy.",
        ],
      },
      {
        kind: "list",
        heading: "How the UI controls map to optimizer behavior",
        items: [
          "`max_iterations` limits optimizer steps or outer-loop updates.",
          "`max_function_evaluations` matters especially when the optimizer probes extra points per step or when you evaluate several starting candidates first.",
          "`optimizer_options` exposes method-specific low-level knobs such as `tol`, `ftol`, `gtol`, `rhobeg`, `eps`, `maxfun`, `learning_rate`, and `perturbation`.",
          "`initial_point_strategy`, `initial_point_candidates`, and explicit `initial_parameters` often matter as much as the optimizer name because they decide where the search starts.",
        ],
      },
      {
        kind: "callout",
        title: "Match the optimizer to the noise regime",
        body: "If your convergence trace already looks jagged on `aer_simulator` with shots or on `ibm_runtime`, switching from a smooth-objective method to `SPSA` is often more useful than tweaking tolerances. Clean optimizers shine when the objective is informative; noisy optimizers shine when the objective is not.",
        tone: "info",
      },
      {
        kind: "list",
        heading: "Practical rule of thumb",
        items: [
          "Prefer `COBYLA` or `L-BFGS-B` on exact or nearly exact simulator objectives.",
          "Prefer `SPSA` once you care about finite-shot realism or hardware execution.",
          "Use `SLSQP` when you want a cleaner local finish on smooth landscapes and the gradients are not being drowned by noise.",
          "Treat `max_function_evaluations` as a real runtime budget, because every extra objective call means another full energy evaluation.",
        ],
      },
    ],
    references: [
      {
        label: "Qiskit Algorithms - SPSA optimizer",
        href: "https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.optimizers.SPSA.html",
      },
      {
        label: "SciPy minimize(method='COBYLA')",
        href: "https://docs.scipy.org/doc/scipy-1.16.0/reference/optimize.minimize-cobyla.html",
      },
      {
        label: "SciPy minimize(method='SLSQP')",
        href: "https://docs.scipy.org/doc/scipy-1.16.2/reference/optimize.minimize-slsqp.html",
      },
      {
        label: "SciPy minimize(method='L-BFGS-B')",
        href: "https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html",
      },
      {
        label: "Spall - SPSA overview",
        href: "https://www.jhuapl.edu/spsa/PDF-SPSA/Spall_An_Overview.PDF",
      },
      {
        label: "Tilly et al. 2022 - VQE review and best practices",
        href: "https://arxiv.org/abs/2111.05176",
      },
      {
        label: "Powell 1994 - COBYLA linear interpolation method",
        href: "https://doi.org/10.1007/978-94-015-8330-5_4",
      },
    ],
  },

  "basis-sets": {
    id: "basis-sets",
    title: "Basis sets",
    summary:
      "The orbital functions used to represent the molecular wavefunction before any fermion-to-qubit mapping happens, and one of the strongest chemistry-side cost controls in the app.",
    blocks: [
      {
        kind: "text",
        heading: "What a basis set changes",
        body: "The basis set decides which one-particle functions are available to describe the electrons. That choice happens long before VQE, QSE, or SQD see a qubit Hamiltonian. A richer basis usually improves chemical accuracy, but it also expands the orbital description that later feeds active-space selection, integral generation, and qubit mapping.",
      },
      {
        kind: "equation",
        label: "Orbital expansion",
        latex: String.raw`\phi_i(\mathbf{r}) = \sum_{\mu} C_{\mu i}\,\chi_\mu(\mathbf{r}), \quad \chi_\mu(\mathbf{r}) = \sum_p d_{\mu p}\,g_p(\mathbf{r})`,
        displayText:
          "φᵢ(r) = Σ_μ C_{μi} χ_μ(r), with contracted functions χ_μ built from primitive Gaussians g_p(r)",
        caption:
          "In practice the molecular orbitals are expanded in basis functions, and many widely used chemistry bases contract Gaussian primitives for efficiency.",
      },
      {
        kind: "image",
        src: "/info-assets/basis-set-orbitals.png",
        alt: "Comparison of orbitals included by STO-3G, 6-31G, and cc-pVDZ for H2",
        caption:
          "Orbital content grows as the basis becomes more flexible. Image adapted from McArdle et al. 2020 and reused from the thesis Chapter 2 discussion.",
      },
      {
        kind: "list",
        heading: "The supported families in this app",
        items: [
          "`STO-3G`: minimal basis. Fastest and useful for exploratory checks, but it compresses the physics aggressively and can hide correlation demands behind an undersized orbital space.",
          "`3-21G`, `6-31G`, `6-31G*`: Pople-style split-valence families. They give valence orbitals extra radial flexibility, while the `*` version adds polarization functions that help directional bonding and distorted charge distributions.",
          "`cc-pVDZ`, `cc-pVTZ`: Dunning correlation-consistent hierarchies. These are designed for more systematic post-Hartree-Fock convergence and are often the most interpretable step-up path when you want to compare basis size carefully.",
          "`def2-SVP`, `def2-TZVP`: balanced Ahlrichs bases. They often offer a strong cost-versus-quality compromise and broader element coverage for practical workflows.",
        ],
      },
      {
        kind: "text",
        heading: "Basis set versus active space",
        body: "These are related but not identical choices. The basis set defines the large orbital pool first. The active space then chooses which orbitals and electrons survive into the explicit correlated problem. A large basis with a conservative active space can still be cheaper than a smaller basis with too many orbitals promoted into the active sector.",
      },
      {
        kind: "callout",
        title: "A cheaper basis can make an algorithm look better than it really is",
        body: "If you shrink the orbital description too aggressively, you are not only making the backend workload smaller. You are also changing the chemistry problem itself. Basis comparisons should therefore be read as problem changes, not just solver-parameter changes.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "How to choose in this app",
        items: [
          "Use `STO-3G` for the fastest end-to-end checks or when you mainly want to validate algorithm wiring.",
          "Use `6-31G` or `6-31G*` when you want a familiar small-molecule middle ground.",
          "Use `cc-pVDZ` or `def2-SVP` when you want a more serious chemistry baseline without jumping all the way to the heaviest options.",
          "Treat `cc-pVTZ` and `def2-TZVP` as deliberate upgrades: they often improve the Hamiltonian description, but they can enlarge the subsequent quantum workload sharply.",
        ],
      },
    ],
    references: [
      {
        label: "McArdle et al. 2020 - Quantum computational chemistry review",
        href: "https://harvest.aps.org/v2/journals/articles/10.1103/RevModPhys.92.015003/fulltext",
      },
      {
        label: "Hehre, Stewart, and Pople 1969 - Gaussian expansions of Slater-type orbitals",
        href: "https://doi.org/10.1063/1.1672392",
      },
      {
        label: "Binkley, Pople, and Hehre 1980 - 3-21G split-valence basis",
        href: "https://doi.org/10.1021/ja00523a008",
      },
      {
        label: "Hariharan and Pople 1973 - polarization functions and 6-31G*",
        href: "https://doi.org/10.1007/BF00533485",
      },
      {
        label: "Dunning 1989 - correlation-consistent basis sets",
        href: "https://doi.org/10.1063/1.456153",
      },
      {
        label: "Weigend and Ahlrichs 2005 - def2 basis sets",
        href: "https://doi.org/10.1039/B508541A",
      },
    ],
  },

  "reference-states": {
    id: "reference-states",
    title: "Reference states",
    summary:
      "The starting state around which VQE, QSE, KQD, and related methods build their search or projected subspace, plus the active-space context that gives those states meaning.",
    blocks: [
      {
        kind: "text",
        heading: "Why the reference is a first-class design choice",
        body: "Several algorithms in the app assume you begin near the part of Hilbert space that matters. VQE uses a reference as the state prepared before variational layers act. QSE expands around a reference. KQD and QFD evolve a reference in time. If the starting state has poor overlap with the target physics, the later quantum or classical post-processing has much less to work with.",
      },
      {
        kind: "equation",
        label: "Reference-state context",
        latex: String.raw`\mathrm{CAS}(n,m), \quad N_{\mathrm{qubits}} = 2m, \quad |\psi(\boldsymbol{\theta})\rangle = U(\boldsymbol{\theta})|\psi_{\mathrm{ref}}\rangle`,
        displayText:
          "CAS(n,m), N_qubits = 2m, and the prepared state is built on top of a chosen reference |ψ_ref⟩",
        caption:
          "The active space fixes the orbital sector first; the reference state is then interpreted inside that reduced problem.",
      },
      {
        kind: "list",
        heading: "Reference choices exposed by the app",
        items: [
          "`HF` reference: the mean-field Hartree-Fock determinant. It is cheap, scalable, and the most common default for chemistry-style subspace methods.",
          "`VQE` reference: a correlated state produced by a separate VQE solve. It costs more, but it can give QSE a much stronger starting point than plain Hartree-Fock.",
          "`Provided dense state`: a full statevector supplied explicitly. This is only realistic for small systems, but it is useful when you already have a trusted reference from another calculation.",
          "`Provided determinant sector`: a sparse list of bitstrings and amplitudes. This is a more structured way to inject prior knowledge without paying the cost of a dense vector.",
        ],
      },
      {
        kind: "text",
        heading: "How active space changes the meaning of a reference",
        body: "A Hartree-Fock bitstring or a provided determinant list only makes sense relative to the selected active orbitals. Change the basis or change the active-space reduction, and the same-looking bitstring can represent a different physical configuration. That is why reference import and active-space setup should be treated as one workflow, not two unrelated panels.",
      },
      {
        kind: "list",
        heading: "When to use which",
        items: [
          "Choose `HF` when you want the most stable and scalable baseline for QSE or Krylov-style methods.",
          "Choose a `VQE` reference when Hartree-Fock is clearly too poor but you still want a local projected correction instead of a full new algorithm family.",
          "Choose `Provided dense state` only for very small systems where you can actually trust and inspect the entire vector.",
          "Choose `Provided determinant sector` when you already know the important occupation patterns and want to stay inside the physically relevant particle-number sector.",
        ],
      },
      {
        kind: "callout",
        title: "Reference quality and basis quality interact",
        body: "A good reference in a weak orbital description may still cap the final accuracy, while a better basis can expose correlation that a plain Hartree-Fock reference no longer captures well. Basis set, active-space reduction, and reference preparation should be tuned together.",
        tone: "info",
      },
      {
        kind: "list",
        heading: "Fields tied most directly to this page",
        items: [
          "`reference_method` decides whether QSE starts from Hartree-Fock, an internal VQE, or user-provided amplitudes.",
          "`provided_state_vector` and the determinant-sector editor define explicit custom references.",
          "`vqe_reference_ansatz_name`, `vqe_reference_optimizer_name`, `vqe_reference_max_iterations`, and `vqe_reference_reps` control how expensive and how strong the VQE-built reference can become.",
          "The molecule, basis set, and active-space choices define the orbital problem inside which all of those references live.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - VQE lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
      },
      {
        label: "McArdle et al. 2020 - Quantum computational chemistry review",
        href: "https://harvest.aps.org/v2/journals/articles/10.1103/RevModPhys.92.015003/fulltext",
      },
      {
        label: "McClean et al. 2017 - QSE and hybrid excited-state hierarchy",
        href: "https://arxiv.org/abs/1603.05681",
      },
      {
        label: "Tilly et al. 2022 - VQE review and best practices",
        href: "https://arxiv.org/abs/2111.05176",
      },
    ],
  },
};
