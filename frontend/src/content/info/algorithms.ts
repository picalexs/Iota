import type { InfoEntry } from "./types";
import type { RunAlgorithm } from "@/types/run";

export const ALGORITHM_INFO: Record<RunAlgorithm, InfoEntry> = {
  vqe: {
    id: "vqe",
    title: "Variational Quantum Eigensolver (VQE)",
    summary:
      "A variational solver that searches a parameterized circuit family for the lowest expectation value of the mapped qubit Hamiltonian by alternating quantum energy estimation with classical parameter updates.",
    sections: [
      {
        heading: "What object it optimizes",
        body: "After active-space selection, second quantization, and a fermion-to-qubit mapping such as Jordan-Wigner, the molecule arrives as a Pauli-sum Hamiltonian. VQE chooses a parameterized state |psi(theta)> = U(theta)|psi_ref> and turns ground-state estimation into the scalar objective E(theta) = <psi(theta)|H|psi(theta)>. Unlike the subspace methods below, VQE does not first build a projected Hamiltonian. Its main mathematical object is the energy landscape induced by the ansatz family and the optimizer.",
      },
      {
        heading: "Workflow in practice",
        body: "A run prepares the reference state and ansatz circuit, estimates grouped Pauli expectations, combines them into an energy, and lets a classical optimizer propose the next parameter vector. This repeats until the convergence threshold, iteration limit, or function-evaluation budget is exhausted. The expensive part is usually not the optimizer step itself, but the repeated measurement of many non-commuting Hamiltonian terms with enough shots to make the updates meaningful.",
      },
      {
        heading: "Controls that change behavior",
        body: "The strongest knobs are `ansatz_name`, `reps`, `optimizer_name`, `max_iterations`, and `max_function_evaluations`. The starting-point controls also matter in practice: `initial_point_strategy`, `initial_point_candidates`, optional explicit `initial_parameters`, `seed`, and any optimizer-specific JSON options. In other words, one group of settings chooses the reachable wavefunctions, and the other group chooses how aggressively the optimizer searches them.",
      },
      {
        heading: "Typical failure modes",
        body: "A shallow or mismatched ansatz can leave the true ground state outside the search family. A deep hardware-efficient ansatz can do the opposite and create a hard optimization problem with many parameters, flat gradients, or barren-plateau behavior. Shot noise can send the optimizer in the wrong direction, and on noisy hardware the finite-shot energy trace can briefly dip below the exact variational bound even though the ideal expectation value still obeys it. Deep two-qubit-heavy circuits also make hardware noise show up directly as bias in the reported energy.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Shared Hamiltonian Starting Point",
        body: "All of the algorithms in this reference center start from the same qubit Hamiltonian H = sum_j h_j P_j. VQE is the most direct consumer of that object because it estimates expectation values of the Pauli terms themselves instead of first building a reduced classical subspace.",
      },
      {
        kind: "video",
        src: "https://video.ibm.com/embed/recorded/134325519?showtitle=false",
        title: "IBM Quantum overview of VQE",
        caption:
          "IBM's diagonalization course includes a concise VQE walkthrough covering the Hamiltonian, ansatz, optimizer, and the main factors that affect runtime and accuracy.",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
        linkLabel: "Open IBM VQE lesson",
      },
      {
        kind: "equation",
        label: "Objective",
        latex: String.raw`H = \sum_{j=1}^{M} h_j P_j, \quad E(\boldsymbol{\theta}) = \sum_{j=1}^{M} h_j \langle \psi(\boldsymbol{\theta}) | P_j | \psi(\boldsymbol{\theta}) \rangle, \quad E_0 \le E(\boldsymbol{\theta})`,
        displayText:
          "H = ∑_{j=1}^{M} h_j P_j    E(θ) = ∑_{j=1}^{M} h_j ⟨ψ(θ)|P_j|ψ(θ)⟩    E₀ ≤ E(θ)",
        caption:
          "The exact expectation value is variational; finite-shot or noisy estimates can fluctuate around that ideal bound.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Choose a reference state and ansatz family, then initialize the parameter vector.",
          "Measure Pauli expectations for the current circuit and reconstruct the energy.",
          "Update the parameters with the chosen optimizer, optionally after comparing several candidate starts.",
          "Stop on convergence or budget exhaustion and report the best observed parameter set and circuit.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "Ansatz family and `reps`, which set expressiveness, circuit depth, and two-qubit cost.",
          "Optimizer choice plus `max_iterations` and `max_function_evaluations`, which set how far the search can run.",
          "Initialization controls such as `initial_point_strategy`, `initial_point_candidates`, explicit `initial_parameters`, and `seed`.",
          "Optional `optimizer_options`, `convergence_threshold`, and `parameter_bounds` when you need tighter or more reproducible optimization behavior.",
        ],
      },
      {
        kind: "callout",
        title: "The Lowest Sampled Point Is Not Automatically The Best Run",
        body: "Trust the overall convergence story, the optimizer status, and the circuit depth together. A single unusually low point can be a shot-noise artifact, while a flat trace can simply mean the run hit a budget before the optimizer found a useful direction.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `Convergence` tile: are energies still drifting downward, bouncing with shot noise, or flat because the budget ran out?",
          "The total objective-evaluation count and whether the run stopped because of convergence or a hard cap.",
          "The `VQE Circuit` tile: ansatz depth, transpiled mapping, and whether the hardware circuit grew much deeper than the logical one.",
          "The gap between the final energy and the HF or exact-reference lines when those references are available.",
        ],
      },
    ],
    references: [
      {
        label: "Peruzzo et al. 2014 - original VQE paper",
        href: "https://www.nature.com/articles/ncomms5213",
      },
      {
        label: "IBM Quantum Learning - VQE lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/vqe",
      },
      {
        label: "Qiskit Algorithms - VQE API reference",
        href: "https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.VQE.html",
      },
    ],
  },

  qse: {
    id: "qse",
    title: "Quantum Subspace Expansion (QSE)",
    summary:
      "A reference-state subspace method that applies excitation operators to HF, VQE, or provided references, then solves a generalized eigenproblem in that local expansion space.",
    sections: [
      {
        heading: "What subspace it builds",
        body: "QSE starts from a prepared reference state and generates nearby states by applying operators such as the identity, single excitations, and sometimes double excitations. Those generated vectors are usually not orthogonal, so QSE builds both a projected Hamiltonian and an overlap matrix before diagonalizing. In chemistry language, it asks whether a compact excitation manifold around a good reference already contains the important low-energy corrections.",
      },
      {
        heading: "Workflow in practice",
        body: "A run first chooses `reference_method`: HF, an internal VQE reference, a full provided statevector, or provided determinant-sector amplitudes. Measured QSE on noisy Aer or IBM Runtime currently supports HF only because its circuit prepares the Hartree-Fock state. Use statevector or ideal Aer for non-HF references. The run then chooses the operator pool through `excitation_level`, constructs the projected matrices, and solves the small generalized eigenproblem. Additional projected eigenvalues can approximate low-lying excited states, while the lowest projected eigenvalue becomes the main energy reported by the app.",
      },
      {
        heading: "Controls that change behavior",
        body: "The most important decisions are reference quality and basis size: `reference_method`, `excitation_level`, and `max_subspace_dim`. If the reference itself is built variationally, the VQE reference controls (`vqe_reference_ansatz_name`, `vqe_reference_optimizer_name`, `vqe_reference_max_iterations`, `vqe_reference_reps`) directly affect the QSE starting point. `regularization` has a path-specific role: measured QSE uses it as an overlap-mode cutoff floor, dense exact QSE uses it for intermediate progress estimates, and fixed-sector QSE does not apply it. The final dense exact solve does not shift the projected metric. `overlap_threshold` prunes basis directions. `residual_tolerance` sets the residual convergence threshold.",
      },
      {
        heading: "Typical failure modes",
        body: "QSE cannot rescue a reference that fundamentally misses the relevant physics. Large excitation pools also increase the O(m^2) projected-matrix workload and can create nearly linearly dependent basis states, which makes the overlap matrix ill-conditioned. In measured QSE, an overly high regularization cutoff can remove useful overlap modes. Too much overlap pruning can also remove useful directions. Noise in the reference preparation or in projected matrix elements enters the generalized eigenproblem directly, where bad conditioning can amplify it.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "What QSE Buys You",
        body: "QSE is attractive when you already have a defensible reference and do not want to launch a brand-new nonlinear optimization for every improvement. It can both lower the ground-state estimate and expose nearby projected excited states from the same subspace solve.",
      },
      {
        kind: "equation",
        label: "Projected Basis",
        latex: String.raw`|\phi_i\rangle = O_i |\psi_{\mathrm{ref}}\rangle, \quad H_{ij}=\langle \phi_i | H | \phi_j \rangle, \quad S_{ij}=\langle \phi_i | \phi_j \rangle, \quad H\mathbf{c}=E S\mathbf{c}`,
        displayText: "|φᵢ⟩ = Oᵢ |ψ_ref⟩    Hᵢⱼ = ⟨φᵢ|H|φⱼ⟩    Sᵢⱼ = ⟨φᵢ|φⱼ⟩    Hc = ESc",
        caption:
          "QSE returns the lowest projected eigenvalue as the main energy and can expose higher projected eigenvalues as local spectral information.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Prepare or import the reference state.",
          "Generate singles or singles-and-doubles expansion states, optionally capping the subspace size.",
          "Assemble the projected Hamiltonian and overlap matrices in that basis.",
          "Solve the generalized eigenproblem and compare the lowest projected eigenvalue to the reference energy.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "Reference choice: `hf`, `vqe`, `provided_state`, or `provided_sector`.",
          "Expansion choice: `excitation_level` and `max_subspace_dim`.",
          "Reference-VQE controls when `reference_method` is `vqe`.",
          "Numerical stabilizers such as `regularization`, `overlap_threshold`, and `residual_tolerance`.",
        ],
      },
      {
        kind: "callout",
        title: "Reference Quality Dominates",
        body: "QSE expands around what you already know. If the reference is poor, the expanded space is still centered on the wrong part of Hilbert space, and a numerically stable solve can still return the wrong physics.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `QSE Subspace` tile: projected eigenvalues, subspace size, and whether the lowest value improves meaningfully over the reference.",
          "Conditioning clues such as overlap pruning, regularization, or residual metadata that suggest the solve needed damping.",
          "The event log for `Reference VQE` steps when the reference was built variationally.",
          "Whether a large apparent improvement comes from a stable projected solve or from a nearly singular overlap matrix.",
        ],
      },
    ],
    references: [
      {
        label: "McClean et al. 2017 - original QSE framework",
        href: "https://journals.aps.org/pra/abstract/10.1103/PhysRevA.95.042308",
      },
      {
        label: "Epperly et al. 2022 - A Theory of Quantum Subspace Diagonalization",
        href: "https://arxiv.org/abs/2110.07492",
      },
      {
        label: "O'Leary et al. 2024 - Partitioned Quantum Subspace Expansion",
        href: "https://arxiv.org/abs/2403.08868",
      },
    ],
  },

  kqd: {
    id: "kqd",
    title: "Krylov Quantum Diagonalization (KQD)",
    summary:
      "A time-evolution subspace method that builds a non-orthogonal Krylov basis from short-time evolved reference states and extracts Ritz energies from a small generalized eigenproblem.",
    sections: [
      {
        heading: "What subspace it builds",
        body: "KQD starts from a reference state |psi0> and applies short-time evolution repeatedly to build a unitary Krylov basis. The basis vectors are usually non-orthogonal, so the algorithm constructs both the projected Hamiltonian and the overlap matrix before solving for Ritz values. The key idea is that the system's own dynamics can generate a compact low-energy basis without a large variational ansatz search.",
      },
      {
        heading: "Workflow in practice",
        body: "A run chooses the Krylov order through `krylov_dim`, chooses the evolution schedule through `time_step` and `evolution_method`, prepares the evolved states, estimates the projected matrix elements, and solves the generalized eigenproblem locally. Exact evolution uses a local matrix path. IBM Runtime and noisy Aer estimator paths use Trotter circuits. Small statevector runs can build dense Krylov states directly, while larger statevector, Aer, and IBM paths switch to sector-based or estimator-based projected workflows before the final local solve.",
      },
      {
        heading: "Controls that change behavior",
        body: "The most important knobs are `krylov_dim`, `time_step`, `evolution_method`, and `trotter_steps`. Together they decide how much new information each basis vector adds, how expensive each evolved state is to prepare, and how strongly time-evolution error can leak into the final projected matrices. `residual_tolerance` then affects how strict the local projected solve is when deciding whether the Ritz solution is numerically acceptable.",
      },
      {
        heading: "Typical failure modes",
        body: "If the reference state has little ground-state overlap, the Krylov basis starts from the wrong place and may improve very slowly. If `time_step` is too small, consecutive states become nearly redundant and the overlap matrix becomes ill-conditioned. If it is too large, the basis can stop resolving the low-energy structure you care about. Larger Krylov dimensions also increase the number of projected matrix elements that must be estimated. On approximate evolution paths, Trotter error and matrix-element noise enter the generalized eigenproblem directly, and bad conditioning can magnify both.",
      },
    ],
    blocks: [
      {
        kind: "video",
        src: "https://video.ibm.com/embed/recorded/134325510?showtitle=false",
        title: "IBM Quantum overview of Krylov quantum diagonalization",
        caption:
          "The IBM lesson frames KQD through classical Krylov intuition first, then shows how short-time quantum evolution supplies the basis states for the projected solve.",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/krylov",
        linkLabel: "Open IBM Krylov lesson",
      },
      {
        kind: "equation",
        label: "Krylov Basis And Projected Solve",
        latex: String.raw`|\psi_k\rangle = e^{-ikH\Delta t}|\psi_0\rangle, \quad H^K_{ij}=\langle \psi_i | H | \psi_j \rangle, \quad S^K_{ij}=\langle \psi_i | \psi_j \rangle, \quad H^K\mathbf{c}=E S^K\mathbf{c}`,
        displayText: "|ψ_k⟩ = e^(-ikHΔt)|ψ₀⟩    Hᴷᵢⱼ = ⟨ψᵢ|H|ψⱼ⟩    Sᴷᵢⱼ = ⟨ψᵢ|ψⱼ⟩    Hᴷc = ESᴷc",
        caption:
          "KQD reports the lowest Ritz value from this generalized eigenproblem together with basis-size diagnostics.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Choose a reference state with some expected overlap with the target low-energy sector.",
          "Generate `krylov_dim` time-evolved states using the selected time step and evolution method.",
          "Estimate the projected Hamiltonian and overlap matrices in that basis.",
          "Solve the generalized eigenproblem and inspect the Ritz values and residuals.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "`krylov_dim`, which sets the basis size and projected matrix cost.",
          "`time_step`, which sets how distinct neighboring Krylov vectors really are.",
          "`evolution_method` and `trotter_steps`, which trade circuit depth for evolution fidelity.",
          "`residual_tolerance`, which affects how strictly the local Ritz solve accepts a solution.",
        ],
      },
      {
        kind: "callout",
        title: "Conditioning Usually Fails Before Raw Dimension Does",
        body: "Adding more Krylov vectors is only helpful if they contribute genuinely new directions. In practice the overlap matrix becoming nearly singular is often the first sign that a larger basis is hurting more than helping.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `KQD Ritz Values` tile: the lowest Ritz value, the spread of nearby values, and whether extra Krylov states actually improved the result.",
          "Krylov rank and basis-conditioning metadata, especially if the result changed sharply after a small parameter tweak.",
          "Whether the run used a dense, fixed-sector, or measured projected path, because the available diagnostics differ.",
          "Residual or matrix-element coverage diagnostics that reveal whether the projected solve is trustworthy.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - KQD lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/krylov",
      },
      {
        label: "IBM Quantum tutorial - Krylov quantum diagonalization",
        href: "https://quantum.cloud.ibm.com/docs/en/tutorials/krylov-quantum-diagonalization",
      },
      {
        label: "Stair et al. 2020 - Multireference quantum Krylov diagonalization",
        href: "https://arxiv.org/abs/1911.05163",
      },
      {
        label: "Epperly et al. 2022 - A Theory of Quantum Subspace Diagonalization",
        href: "https://arxiv.org/abs/2110.07492",
      },
    ],
  },

  qfd: {
    id: "qfd",
    title: "Quantum Filter Diagonalization (QFD)",
    summary:
      "A reference-state filtering method that uses time-evolved states and linear-combination weights to isolate an energy window before solving the projected problem in that filtered subspace.",
    sections: [
      {
        heading: "What filter it builds",
        body: "QFD expands the reference in the exact eigenbasis, evolves that reference at several time points, and then searches for linear combinations whose phases reinforce the target energies and suppress the rest. The filtered states still feed a projected Hamiltonian and overlap solve, but the design question is different from KQD: instead of only asking how many basis states to keep, QFD asks which time grid creates the right spectral window.",
      },
      {
        heading: "Workflow in practice",
        body: "A run chooses the time grid through `num_time_points`, `max_time`, and `time_grid_type`, generates the corresponding time-evolved states, assembles the projected matrices, and solves the generalized eigenproblem locally. In Quantum Studio, small statevector paths can evolve densely, while larger statevector, Aer, and IBM routes use sector-based or measured projected workflows before the local spectral extraction step.",
      },
      {
        heading: "Controls that change behavior",
        body: "The main knobs are `num_time_points`, `max_time`, and `time_grid_type`, because they determine the basic energy resolution and how strongly neighboring filtered states overlap. `trotter_steps` matters whenever the evolution is synthesized approximately, since more accurate time evolution usually means deeper circuits. `residual_tolerance` then acts on the final projected solve rather than on the filter design itself.",
      },
      {
        heading: "Typical failure modes",
        body: "A short total time window cannot resolve nearby energies well, while time points that are too close together create nearly dependent states and an unstable overlap matrix. Pushing to larger times can improve nominal resolution but also deepens the evolution circuits and increases approximation error. A poor reference state weakens the filter before the projected solve even begins, because the desired eigencomponents may barely be present in the original state. As with KQD, conditioning and matrix-element noise can dominate once the projected basis becomes nearly redundant.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Why QFD Is Not Just Another Name For KQD",
        body: "Both algorithms use time-evolved states and end in a projected generalized eigenproblem, but their design logic is different. KQD treats time evolution as a basis generator. QFD treats it as a spectral probe whose interference pattern can emphasize one energy window over another.",
      },
      {
        kind: "equation",
        label: "Filter Action",
        latex: String.raw`|\Gamma_k\rangle = e^{-iHt_k}|\psi_{\mathrm{ref}}\rangle, \quad \sum_k c_k |\Gamma_k\rangle = \sum_n b_n \left(\sum_k c_k e^{-iE_n t_k}\right)|E_n\rangle`,
        displayText:
          "|Γ_k⟩ = e^(-iHt_k)|ψ_ref⟩\n∑_k c_k |Γ_k⟩ = ∑_n b_n (∑_k c_k e^(-iE_n t_k)) |E_n⟩",
        caption:
          "The inner sum acts like an energy-domain filter: some eigencomponents add constructively while others are suppressed.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Choose a reference state and a time grid.",
          "Prepare or characterize the time-evolved states across that grid.",
          "Assemble the projected Hamiltonian and overlap matrices in the filtered basis.",
          "Solve the generalized eigenproblem and inspect how the spectrum changes as the grid is widened or refined.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "`num_time_points` and `max_time`, which set the basic filter window and spectral resolution.",
          "`time_grid_type`, which decides whether the method spends its resolution more uniformly or more selectively.",
          "`trotter_steps`, which matters when time evolution must be approximated circuit-wise.",
          "`residual_tolerance`, which governs acceptance of the final projected solve rather than the filter construction itself.",
        ],
      },
      {
        kind: "callout",
        title: "Resolution And Conditioning Pull Against Each Other",
        body: "More time information is only useful if the resulting states stay distinguishable and the evolution remains accurate enough. A nominally finer filter can still produce a worse answer if it creates an unstable projected basis.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `QFD Spectrum` tile: whether the lowest filtered value stabilizes as the time grid changes.",
          "The reported time-grid settings, because `num_time_points` and `max_time` explain most large result shifts.",
          "Conditioning or residual diagnostics that suggest the filtered basis became too redundant.",
          "How the QFD energy compares with KQD under similar evolution budgets, since the two methods stress different parts of the same time-domain information.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - Quantum diagonalization algorithms introduction",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/introduction",
      },
      {
        label: "Parrish and McMahon 2019 - original QFD paper",
        href: "https://arxiv.org/abs/1909.08925",
      },
      {
        label: "Cohn et al. 2021 - QFD with double-factorized Hamiltonians",
        href: "https://arxiv.org/abs/2104.08957",
      },
      {
        label: "Rossmannek et al. 2021 - compressed double-factorized QFD",
        href: "https://journals.aps.org/prxquantum/abstract/10.1103/PRXQuantum.2.040352",
      },
    ],
  },

  sqd: {
    id: "sqd",
    title: "Sample-based Quantum Diagonalization (SQD)",
    summary:
      "A sampling-based diagonalization method that treats measured bitstrings as candidate determinants, repairs and postselects them, and solves the molecular Hamiltonian in the selected orthonormal determinant subspace.",
    sections: [
      {
        heading: "What subspace it builds",
        body: "SQD reuses the occupation-number picture from the introduction: a measured computational-basis bitstring corresponds to a pattern of occupied and empty spin orbitals. After postselection and configuration recovery, the accepted bitstrings define a determinant set S and therefore a selected subspace V_S = span{|z> : z in S}. Because those determinant basis states are orthonormal, SQD solves an ordinary projected eigenvalue problem rather than the generalized overlap problem used by KQD, QSE, and QFD.",
      },
      {
        heading: "Workflow in practice",
        body: "A run measures one bitstring sample set, validates electron-number sectors, optionally repairs invalid strings using occupancy estimates, splits the recovered determinants into selected-CI batches, and feeds the resulting occupancies back into the next recovery round. Each recovery round reuses the same measured rows. Quantum Studio follows the qiskit-addon-sqd recovery pattern and reports the best observed recovery iteration as the top-level SQD energy.",
      },
      {
        heading: "Controls that change behavior",
        body: "The base measurement budget is `samples_per_batch × num_batches` for one run. Each recovery round reuses that measured set; `max_iterations` controls occupancy-guided recovery and selected-CI updates, not new measurements. Local sampler retries can request more shots after submission errors. Check the work ledger for the worker's requested total. `energy_tol`, `occupancies_tol`, and `min_selected_configurations` control recovery stopping. The size and cost of the classical diagonalization are controlled by `max_dim` and `sci_solver_options`. Electron-count overrides (`num_elec_a`, `num_elec_b`), `spin_sq_target`, and `seed` are most useful for reproducibility or debugging. An unset `spin_sq_target` targets the closed-shell singlet only when alpha and beta counts match; it imposes no spin penalty for open-shell counts. Set it explicitly for another total-spin target. `carryover_threshold` keeps large-weight determinant strings in the selected-CI pool from one recovery round to the next. `symmetrize_spin` makes the alpha/beta determinant pools match in balanced-spin studies.",
      },
      {
        heading: "Typical failure modes",
        body: "SQD relies on sparsity: if the important determinants have tiny sampling probability, the selected subspace never becomes good no matter how cleanly you diagonalize it. Readout noise can push samples into the wrong particle-number sector, and while recovery can fix some of that, it can also oscillate or stabilize on a misleading occupancy pattern if the raw sample support is weak. Overly small determinant caps can make the selected-CI side look converged only because the classical subspace was truncated too hard. Broad strongly correlated states can also make the selected basis grow until the classical post-processing becomes the true bottleneck.",
      },
    ],
    blocks: [
      {
        kind: "image",
        src: "/info-assets/sqd-diagram.png",
        alt: "SQD workflow diagram from bitstring sampling to selected-CI diagonalization",
        caption:
          "SQD uses measured bitstrings as the raw material for a selected-CI style projected solve instead of measuring every Hamiltonian matrix element directly.",
      },
      {
        kind: "video",
        src: "https://video.ibm.com/embed/recorded/134325501?showtitle=false",
        title: "IBM Quantum overview of SQD",
        caption:
          "This IBM course video pairs well with the workflow figure because it explains why SQD can avoid the projected-matrix measurement burden of other subspace methods.",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/sqd-overview",
        linkLabel: "Open IBM SQD lesson",
      },
      {
        kind: "equation",
        label: "Selected Determinant Problem",
        latex: String.raw`\mathcal{X}=\{\mathbf{z}^{(1)},\ldots,\mathbf{z}^{(N_{\mathrm{shots}})}\}, \quad \mathcal{V}_{\mathcal{S}} = \mathrm{span}\{ |\mathbf{z}\rangle : \mathbf{z} \in \mathcal{S} \}, \quad H_{\mathcal{S}}\mathbf{c}=E_{\mathcal{S}}\mathbf{c}`,
        displayText: "X = {z^(1), …, z^(Nshots)}    V_S = span{|z⟩ : z ∈ S}    H_S c = E_S c",
        caption:
          "Because determinant basis states are orthonormal, SQD does not need a separate overlap matrix in the final projected solve.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Sample bitstrings from the chosen circuit family or backend path.",
          "Postselect or recover strings so the particle-number sector is chemically valid.",
          "Build a selected determinant pool and diagonalize batch-wise selected-CI subspaces.",
          "Update occupancies from the best solutions and repeat recovery until the stopping criteria are met.",
          "Report the best observed recovery energy together with occupancy and determinant diagnostics.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "`samples_per_batch` and `num_batches`, which set the raw bitstring budget.",
          "`max_iterations`, `energy_tol`, and `occupancies_tol`, which control the recovery loop stopping rules.",
          "`max_dim` and `sci_solver_options`, which cap and shape the classical selected-CI solve.",
          "Electron-count, spin-target, and seed overrides when reproducibility or sector debugging matters.",
        ],
      },
      {
        kind: "callout",
        title: "The Upper Bound Only Applies Inside The Selected Subspace",
        body: "SQD is variational with respect to the determinant space it actually found, not with respect to the full molecular Hilbert space. Missing a few important determinants can leave a large energy gap even when the classical diagonalization itself is exact inside the chosen subset.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `SQD Recovery` tile: accepted counts, recovered counts, and whether the recovery loop still changed the energy meaningfully near the end.",
          "The `SQD Occupancy` tile: do occupancies stabilize smoothly or oscillate from one recovery round to the next?",
          "Whether the best observed energy came before the final iteration, which often signals a recovery loop that stopped after the most informative point.",
          "Signs that `max_dim` or other selected-CI caps were binding so tightly that the classical side could not grow with the sampled support.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - SQD overview lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/sqd-overview",
      },
      {
        label: "IBM Quantum tutorial - Sample-based quantum diagonalization",
        href: "https://quantum.cloud.ibm.com/docs/en/tutorials/sample-based-quantum-diagonalization",
      },
      {
        label: "qiskit-addon-sqd documentation",
        href: "https://qiskit.github.io/qiskit-addon-sqd/",
      },
      {
        label:
          "Robledo-Moreno et al. 2024 - Chemistry beyond the scale of exact diagonalization on a quantum-centric supercomputer",
        href: "https://arxiv.org/abs/2405.05068",
      },
    ],
  },

  skqd: {
    id: "skqd",
    title: "Sample-based Krylov Quantum Diagonalization (SKQD)",
    summary:
      "A hybrid method that uses several Krylov-evolved states to enrich SQD-style sampling, then refines the sampled result with a Krylov-style local extension when that extension helps.",
    sections: [
      {
        heading: "What it builds",
        body: "In the ideal SKQD picture, the quantum computer prepares several time-evolved states and samples bitstrings from each of them. Those samples are merged, postselected, and used to build a determinant subspace exactly as in SQD, except now the determinant pool comes from multiple Krylov-related sampling distributions instead of one. In Quantum Studio's production path, the SQD core is then followed by a local Krylov refinement over the best sampled fixed-sector state, and the app keeps whichever path gives the better stable energy.",
      },
      {
        heading: "Workflow in practice",
        body: "The first stage is still mostly an SQD problem: choose the base sampling budget, gather samples, recover and diagonalize them, and identify the best SQD seed. The second stage chooses the Krylov extension size through `krylov_extension_dim`, evolves the SQD seed locally with `time_step`, builds a small projected solve, and checks whether that refinement beats the SQD core. This makes SKQD a two-stage method in the UI and in the result interpretation.",
      },
      {
        heading: "Controls that change behavior",
        body: "The dominant controls are `samples_per_state` and `krylov_extension_dim`. SKQD collects the declared number of samples from each sampled Krylov state, merges the sector-valid determinants, and solves one selected-CI problem over that union. `max_dim` and `sci_solver_options` control the classical selected-CI solve, while `time_step` and `residual_tolerance` control the Krylov state construction and diagnostics.",
      },
      {
        heading: "Typical failure modes",
        body: "SKQD depends on basis sparsity and sample coverage. If important determinants have low probability in every sampled Krylov state, the selected union cannot recover them. If the time step is too small, states can be redundant; if it is too large, the sampled distributions can become difficult to resolve. The result records the sampled-state count, union size, selected-CI cap, and final path so that a weak sample union is not mistaken for convergence.",
      },
    ],
    blocks: [
      {
        kind: "text",
        heading: "Why Basis Choice Still Matters",
        body: "IBM's SKQD lesson makes an important conceptual point that carries over to chemistry too: the method is strongest when the target state is sparse in the basis you are sampling. Sampling multiple Krylov states enriches the determinant union, but it does not remove the need for enough samples per state.",
      },
      {
        kind: "video",
        src: "https://video.ibm.com/embed/recorded/134680646?showtitle=false",
        title: "IBM Quantum overview of SQD and SKQD in an HPC-integrated workflow",
        caption:
          "IBM's SQD/SKQD lesson uses a hybrid HPC workflow to show how multiple sampled Krylov states enrich the determinant pool before the final diagonalization step.",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/integrating-quantum-and-high-performance-computing/sqd-skqd",
        linkLabel: "Open IBM SQD and SKQD lesson",
      },
      {
        kind: "equation",
        label: "Krylov-Sampled Determinant Pool",
        latex: String.raw`|\psi_k\rangle = e^{-ikH\Delta t}|\psi_0\rangle, \quad \mathcal{X}_K = \{ \mathbf{z}^{(k,m)} \mid k=0,\ldots,d-1,\; m=1,\ldots,M \}`,
        displayText: "|ψ_k⟩ = e^(-ikHΔt)|ψ₀⟩    X_K = { z^(k,m) | k = 0, …, d - 1 ; m = 1, …, M }",
        caption:
          "The merged samples define the determinant space for the SQD-style core; Quantum Studio may then apply a local Krylov extension to the best sampled seed.",
      },
      {
        kind: "list",
        heading: "Typical Workflow",
        items: [
          "Run the SQD-style sampling and recovery core to obtain a best sampled seed state.",
          "Choose the Krylov extension size and time step for the local follow-up solve.",
          "Build and solve the small projected Krylov problem around that SQD seed.",
          "Keep the Krylov-refined answer only if it improves on the SQD core without failing the local diagnostics.",
        ],
      },
      {
        kind: "list",
        heading: "Controls That Usually Matter Most",
        items: [
          "The full SQD sampling budget inside `base_sampling_options`, because the seed quality dominates everything downstream.",
          "`krylov_extension_dim`, which controls how far the local refinement is allowed to expand.",
          "`time_step`, which controls whether the extension explores a genuinely new neighborhood or mostly repeats the seed.",
          "`residual_tolerance`, which governs the acceptability of the local Krylov projected solve.",
        ],
      },
      {
        kind: "callout",
        title: "Sampling Is Still The Main Bottleneck",
        body: "A larger Krylov extension cannot rescue a seed state that never captured the right determinants. If SKQD underperforms, improving the SQD stage is often more valuable than immediately increasing the extension size.",
        tone: "warning",
      },
      {
        kind: "list",
        heading: "What To Watch In The Result View",
        items: [
          "The `SKQD Diagnostics` tile: whether the final energy came from the SQD core or from the Krylov extension.",
          "Krylov rank, Ritz-value structure, and any local residual metadata that reveal whether the extension was numerically useful.",
          "The sampled-outcome and seed-circuit diagnostics, which often explain why the Krylov extension had good or bad raw material to work with.",
          "Whether changing the SQD sample budget would likely matter more than changing `krylov_extension_dim`.",
        ],
      },
    ],
    references: [
      {
        label: "IBM Quantum Learning - SKQD lesson",
        href: "https://quantum.cloud.ibm.com/learning/en/courses/quantum-diagonalization-algorithms/skqd",
      },
      {
        label: "IBM Quantum tutorial - Sample-based Krylov quantum diagonalization",
        href: "https://quantum.cloud.ibm.com/docs/en/tutorials/sample-based-krylov-quantum-diagonalization",
      },
      {
        label: "Yu et al. 2025 - Quantum-Centric Algorithm for Sample-Based Krylov Diagonalization",
        href: "https://arxiv.org/abs/2501.09702",
      },
      {
        label: "qiskit-addon-sqd documentation",
        href: "https://qiskit.github.io/qiskit-addon-sqd/",
      },
    ],
  },
};
