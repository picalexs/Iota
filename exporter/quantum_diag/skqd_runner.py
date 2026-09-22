"""Sample-based Krylov Quantum Diagonalization (SKQD) runner."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from scipy.linalg import eigh

from quantum_diag.ansatz_factory import (
    create_lucj_ansatz,
    create_real_amplitudes_ansatz,
    create_two_local_ansatz,
    create_uccsd_ansatz_stub,
)
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle
from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics
from quantum_diag.primitive_adapter import create_sampler, sample_counts
from quantum_diag.reproducibility import SeedManager
from quantum_diag.test_fixtures import MoleculeGeometry
from quantum_diag.time_evolution import build_trotter_time_evolution


class SKQDRunner:
    """Sample-based Krylov Quantum Diagonalization runner."""

    _MAX_TROTTER_MATRIX_DIM = 2048

    def __init__(self, experiment_spec: ExperimentSpec, reference_energy: float):
        """Initialize SKQD runner."""
        self.experiment_spec = experiment_spec
        self.reference_energy = reference_energy
        self.seed_manager = SeedManager()
        self.seed_manager.set_global_seed(experiment_spec.seed)

    def _get_ansatz(self, num_qubits: int, depth: int = 2) -> QuantumCircuit:
        """Get ansatz based on experiment specification."""
        ansatz_type = self.experiment_spec.ansatz_type

        if ansatz_type == "RealAmplitudes":
            return create_real_amplitudes_ansatz(
                num_qubits=num_qubits,
                depth=depth,
                entanglement="full",
            )
        if ansatz_type == "HEA":
            return create_two_local_ansatz(
                num_qubits=num_qubits,
                depth=depth,
                rotation_blocks="ry",
                entanglement_blocks="cx",
            )
        if ansatz_type == "EDA":
            return create_real_amplitudes_ansatz(
                num_qubits=num_qubits,
                depth=depth,
                entanglement="linear",
            )
        if ansatz_type == "TwoLocal":
            return create_two_local_ansatz(
                num_qubits=num_qubits,
                depth=depth,
                rotation_blocks="ry",
                entanglement_blocks="cx",
            )
        if ansatz_type == "UCCSD":
            num_params = 2 * num_qubits * depth
            return create_uccsd_ansatz_stub(
                num_qubits=num_qubits,
                num_parameters=num_params,
            )
        if ansatz_type == "LUCJ":
            return create_lucj_ansatz(
                num_qubits=num_qubits,
                depth=depth,
            )
        raise ValueError(
            f"Unsupported ansatz_type '{ansatz_type}'. "
            "Valid options are: RealAmplitudes, TwoLocal, UCCSD, HEA, EDA, LUCJ"
        )

    @staticmethod
    def _bind_sampling_parameters(
        circuit: QuantumCircuit,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Generate non-degenerate sampling parameters."""
        if circuit.num_parameters == 0:
            return np.array([], dtype=float)
        return rng.uniform(-np.pi, np.pi, circuit.num_parameters)

    def _sample_bitstrings(
        self,
        circuit: QuantumCircuit,
        num_samples: int = 10,
        parameter_values: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str | int, int]]:
        """Sample bitstrings from the quantum circuit."""
        if num_samples < 1:
            raise ValueError(f"num_samples must be >= 1, got {num_samples}")

        n_qubits = circuit.num_qubits
        circuit_with_measure = circuit.copy()
        if circuit_with_measure.num_clbits == 0:
            circuit_with_measure.measure_all()

        sampler = create_sampler()

        if circuit_with_measure.parameters:
            if parameter_values is None:
                raise ValueError(
                    "SKQD sampling circuit has free parameters but no parameter_values were provided."
                )
            raw_counts = sample_counts(
                sampler=sampler,
                circuit=circuit_with_measure,
                shots=num_samples,
                parameter_values=parameter_values,
            )
        else:
            raw_counts = sample_counts(
                sampler=sampler,
                circuit=circuit_with_measure,
                shots=num_samples,
            )

        bitstrings_list: list[np.ndarray] = []
        counts: dict[str | int, int] = {}

        for bitstring, count in raw_counts.items():
            if isinstance(bitstring, str):
                bs_array = np.array([int(b) for b in bitstring[::-1]], dtype=np.uint8)
            else:
                bs_array = np.array(
                    [(bitstring >> i) & 1 for i in range(n_qubits)],
                    dtype=np.uint8,
                )

            for _ in range(count):
                bitstrings_list.append(bs_array)
            counts[bitstring] = int(count)

        if len(bitstrings_list) < num_samples:
            first_bs = (
                bitstrings_list[0]
                if bitstrings_list
                else np.zeros(n_qubits, dtype=np.uint8)
            )
            while len(bitstrings_list) < num_samples:
                bitstrings_list.append(first_bs)
        elif len(bitstrings_list) > num_samples:
            bitstrings_list = bitstrings_list[:num_samples]

        bitstring_array = np.array(bitstrings_list, dtype=np.uint8)
        return bitstring_array, counts

    @staticmethod
    def _hartree_fock_seed_bitstring(
        num_qubits: int,
        num_elec_alpha: int,
        num_elec_beta: int,
    ) -> np.ndarray:
        """Create one HF-like bitstring in little-endian qubit order."""
        if num_qubits % 2 != 0:
            raise ValueError(f"num_qubits must be even, got {num_qubits}")

        half = num_qubits // 2
        bs = np.zeros((1, num_qubits), dtype=np.uint8)
        bs[0, :num_elec_beta] = 1
        bs[0, half:half + num_elec_alpha] = 1
        return bs

    @staticmethod
    def _filter_bitstrings_by_electron_number(
        bitstrings: np.ndarray,
        num_elec_alpha: int,
        num_elec_beta: int,
    ) -> np.ndarray:
        """Keep only bitstrings with target electron counts per spin half."""
        if bitstrings.size == 0:
            return bitstrings

        num_qubits = bitstrings.shape[1]
        if num_qubits % 2 != 0:
            raise ValueError(f"Expected even num_qubits, got {num_qubits}")

        half = num_qubits // 2
        beta_counts = np.sum(bitstrings[:, :half], axis=1)
        alpha_counts = np.sum(bitstrings[:, half:], axis=1)
        mask = (alpha_counts == num_elec_alpha) & (beta_counts == num_elec_beta)
        return bitstrings[mask]

    def _build_configuration_matrix(
        self,
        bitstrings: np.ndarray,
    ) -> tuple[list[int], np.ndarray]:
        """Convert sampled bitstrings to unique Fock configurations."""
        unique_bs, inverse_indices = np.unique(
            bitstrings,
            axis=0,
            return_inverse=True,
        )

        unique_configs = []
        for bs in unique_bs:
            config_index = int(np.sum(bs * (2 ** np.arange(len(bs)))))
            unique_configs.append(config_index)

        return unique_configs, inverse_indices

    def _build_krylov_subspace_from_samples(
        self,
        configs: list[int],
        hamiltonian: np.ndarray,
        krylov_extension_dim: int,
        u_dt: np.ndarray | None,
    ) -> list[np.ndarray]:
        """Build Krylov subspace starting from sampled configurations."""
        dim = hamiltonian.shape[0]
        basis = []

        for config in configs:
            vec = np.zeros(dim, dtype=complex)
            vec[config] = 1.0
            basis.append(vec)

        orthonorm_basis: list[np.ndarray] = []
        for vec in basis:
            for prev_vec in orthonorm_basis:
                overlap = np.vdot(prev_vec, vec)
                vec = vec - overlap * prev_vec

            norm = np.linalg.norm(vec)
            if norm > 1e-10:
                orthonorm_basis.append(vec / norm)

        if (
            krylov_extension_dim > 0
            and len(orthonorm_basis) > 0
            and u_dt is not None
        ):
            psi_current = orthonorm_basis[-1].copy()

            for _ in range(krylov_extension_dim):
                psi_current = u_dt @ psi_current

                for prev_vec in orthonorm_basis:
                    overlap = np.vdot(prev_vec, psi_current)
                    psi_current = psi_current - overlap * prev_vec

                norm = np.linalg.norm(psi_current)
                if norm > 1e-10:
                    orthonorm_basis.append(psi_current / norm)
                else:
                    break

        return orthonorm_basis

    @staticmethod
    def _project_hamiltonian(
        hamiltonian: np.ndarray,
        basis: list[np.ndarray],
    ) -> np.ndarray:
        """Project Hamiltonian onto basis."""
        k = len(basis)
        h_proj = np.zeros((k, k), dtype=complex)

        # Precompute H|phi_j> once to avoid repeated matvec work.
        h_basis_vectors = [hamiltonian @ basis_j for basis_j in basis]

        for i in range(k):
            for j in range(k):
                h_proj[i, j] = np.vdot(basis[i], h_basis_vectors[j])

        return h_proj

    def run(
        self,
        geometry: MoleculeGeometry,
        num_samples: int = 10,
        krylov_extension_dim: int = 2,
        max_iterations: int = 10,
        energy_tol: float = 1e-3,
    ) -> tuple[float, BenchmarkMetrics]:
        """Run SKQD algorithm with molecule-sensitive geometry."""
        if num_samples < 1:
            raise ValueError(f"num_samples must be >= 1, got {num_samples}")
        if krylov_extension_dim < 0:
            raise ValueError(
                f"krylov_extension_dim must be >= 0, got {krylov_extension_dim}"
            )
        if max_iterations < 1:
            raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")
        if energy_tol < 0:
            raise ValueError(f"energy_tol must be >= 0, got {energy_tol}")

        algorithm_start = time.time()

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=geometry,
            basis_set=self.experiment_spec.basis_set,
        )

        hamiltonian = bundle.qubit_hamiltonian_matrix
        num_qubits = bundle.num_qubits
        rng = np.random.default_rng(self.experiment_spec.seed)

        effective_krylov_extension_dim = krylov_extension_dim
        krylov_extension_disabled_reason: str | None = None
        if (
            krylov_extension_dim > 0
            and hamiltonian.shape[0] > self._MAX_TROTTER_MATRIX_DIM
        ):
            effective_krylov_extension_dim = 0
            krylov_extension_disabled_reason = (
                "disabled_krylov_trotter_extension_for_large_dense_hamiltonian"
            )

        depth = max(2, self.experiment_spec.max_iterations // 20)
        ansatz = self._get_ansatz(num_qubits, depth=depth)
        sampling_params = self._bind_sampling_parameters(ansatz, rng)

        u_dt = None
        if effective_krylov_extension_dim > 0:
            u_dt = build_trotter_time_evolution(
                hamiltonian,
                time_step=0.2,
                trotter_steps=1,
            )

        hf_seed = self._hartree_fock_seed_bitstring(
            num_qubits=num_qubits,
            num_elec_alpha=bundle.num_electrons_alpha,
            num_elec_beta=bundle.num_electrons_beta,
        )

        convergence_history: list[float] = []
        iteration_diagnostics: list[dict[str, Any]] = []
        converged = False
        shots_used = 0
        max_unique_configs = 0

        for iteration in range(max_iterations):
            current_num_samples = num_samples * (iteration + 1)

            bitstrings, counts = self._sample_bitstrings(
                circuit=ansatz,
                num_samples=current_num_samples,
                parameter_values=sampling_params if sampling_params.size > 0 else None,
            )
            shots_used += int(sum(counts.values())) if counts else current_num_samples

            filtered_bitstrings = self._filter_bitstrings_by_electron_number(
                bitstrings,
                num_elec_alpha=bundle.num_electrons_alpha,
                num_elec_beta=bundle.num_electrons_beta,
            )
            if filtered_bitstrings.shape[0] == 0:
                filtered_bitstrings = hf_seed

            unique_configs, _ = self._build_configuration_matrix(filtered_bitstrings)
            max_unique_configs = max(max_unique_configs, len(unique_configs))

            basis = self._build_krylov_subspace_from_samples(
                unique_configs,
                hamiltonian,
                krylov_extension_dim=effective_krylov_extension_dim,
                u_dt=u_dt,
            )

            if not basis:
                hf_config, _ = self._build_configuration_matrix(hf_seed)
                basis = self._build_krylov_subspace_from_samples(
                    hf_config,
                    hamiltonian,
                    krylov_extension_dim=0,
                    u_dt=None,
                )

            h_proj = self._project_hamiltonian(hamiltonian, basis)
            eigenvalues, _ = eigh(h_proj)
            energy = float(np.real(eigenvalues[0]))
            convergence_history.append(energy)

            energy_delta = None
            if len(convergence_history) >= 2:
                energy_delta = abs(convergence_history[-1] - convergence_history[-2])

            iteration_diagnostics.append(
                {
                    "iteration": iteration,
                    "num_raw_samples": current_num_samples,
                    "num_filtered_bitstrings": int(filtered_bitstrings.shape[0]),
                    "num_unique_configs": len(unique_configs),
                    "basis_dimension": len(basis),
                    "energy": energy,
                    "energy_delta": energy_delta,
                }
            )

            if energy_delta is not None and energy_delta <= energy_tol:
                converged = True
                break

            if sampling_params.size > 0:
                sampling_params = np.asarray(
                    sampling_params + rng.normal(loc=0.0, scale=0.05, size=sampling_params.shape),
                    dtype=float,
                )

        algorithm_wall_time = time.time() - algorithm_start

        ground_energy = convergence_history[-1]
        energy_error = abs(ground_energy - self.reference_energy)

        metrics = BenchmarkMetrics(
            final_energy=ground_energy,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=len(convergence_history),
            wall_time_seconds=algorithm_wall_time,
            converged=converged,
            convergence_history=convergence_history,
            shots_used=shots_used,
            chemistry_pipeline="pyscf+ffsim+sampling+krylov",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(hamiltonian.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion=f"abs(delta_energy) <= {energy_tol}",
            diagnostics={
                "max_unique_configs": max_unique_configs,
                "iterations_executed": len(convergence_history),
                "krylov_extension_dim_requested": krylov_extension_dim,
                "krylov_extension_dim_used": effective_krylov_extension_dim,
                "krylov_extension_disabled_reason": krylov_extension_disabled_reason,
                "iteration_diagnostics": iteration_diagnostics,
            },
        )

        return ground_energy, metrics
