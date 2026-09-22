"""Sample-based Quantum Diagonalization (SQD) runner."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit_addon_sqd.configuration_recovery import recover_configurations
from qiskit_addon_sqd.counts import counts_to_arrays
from qiskit_addon_sqd.fermion import solve_fermion
from qiskit_addon_sqd.subsampling import (
    postselect_by_hamming_right_and_left,
    subsample,
)

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


class SQDRunner:
    """Sample-based Quantum Diagonalization runner.

    Uses sampling + configuration-recovery + selected-CI refinement via
    ``qiskit-addon-sqd`` for chemically meaningful subspace energies.
    """

    def __init__(self, experiment_spec: ExperimentSpec, reference_energy: float):
        """Initialize SQD runner.

        Args:
            experiment_spec: ExperimentSpec with configuration.
            reference_energy: Reference (ground truth) energy in Hartree.
        """
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

    def _bind_sampling_parameters(
        self,
        circuit: QuantumCircuit,
        rng: np.random.Generator,
    ) -> tuple[QuantumCircuit, np.ndarray]:
        """Bind non-zero sampling parameters to avoid degenerate zero-state sampling."""
        if circuit.num_parameters == 0:
            return circuit.copy(), np.array([], dtype=float)

        params = rng.uniform(-np.pi, np.pi, circuit.num_parameters)
        param_dict = dict(zip(circuit.parameters, params))
        return circuit.assign_parameters(param_dict), params

    def _sample_counts(
        self,
        circuit: QuantumCircuit,
        shots: int,
    ) -> dict[str, int]:
        """Sample measured bitstring counts from a bound circuit."""
        if shots < 1:
            raise ValueError(f"shots must be >= 1, got {shots}")

        measured = circuit.copy()
        if measured.num_clbits == 0:
            measured.measure_all()

        if measured.parameters:
            raise ValueError(
                "SQD sampling circuit must be bound before sampling. "
                "Received a circuit with free parameters."
            )

        sampler = create_sampler()
        counts = sample_counts(
            sampler=sampler,
            circuit=measured,
            shots=shots,
        )
        if not counts:
            return {"0" * circuit.num_qubits: shots}
        return counts

    @staticmethod
    def _hartree_fock_seed_bitstring(
        norb: int,
        num_elec_alpha: int,
        num_elec_beta: int,
    ) -> np.ndarray:
        """Create one HF-style bitstring in SQD's spin-partitioned convention."""
        seed = np.zeros((1, 2 * norb), dtype=bool)
        seed[0, :num_elec_beta] = True
        seed[0, norb:norb + num_elec_alpha] = True
        return seed

    @staticmethod
    def _filter_bitstrings_by_hamming(
        bitstring_matrix: np.ndarray,
        hamming_left: int,
        hamming_right: int,
    ) -> np.ndarray:
        """Keep rows with the target electron counts in each half."""
        if bitstring_matrix.size == 0:
            return bitstring_matrix

        num_bits = bitstring_matrix.shape[1]
        if num_bits % 2 != 0:
            raise ValueError(
                f"Expected even number of bits, got {num_bits}."
            )

        half = num_bits // 2
        left_counts = np.sum(bitstring_matrix[:, :half], axis=1)
        right_counts = np.sum(bitstring_matrix[:, half:], axis=1)
        mask = (left_counts == hamming_left) & (right_counts == hamming_right)
        return bitstring_matrix[mask]

    def run(
        self,
        geometry: MoleculeGeometry,
        num_samples: int = 10,
        max_iterations: int = 10,
        samples_per_batch: int | None = None,
        num_batches: int = 1,
        energy_tol: float = 1e-3,
        occupancies_tol: float = 1e-3,
    ) -> tuple[float, BenchmarkMetrics]:
        """Run SQD algorithm with chemistry-consistent post-processing.

        Args:
            geometry: MoleculeGeometry specifying the molecule.
            num_samples: Base number of raw samples per iteration.
            max_iterations: Maximum SQD iterations.
            samples_per_batch: Subsample size passed to post-selection.
            num_batches: Number of subsamples to evaluate per iteration.
            energy_tol: Convergence threshold for absolute energy change.
            occupancies_tol: Convergence threshold for occupancy drift.

        Returns:
            Tuple of (ground_state_energy, BenchmarkMetrics).

        Raises:
            ValueError: If numeric controls are invalid.
        """
        if num_samples < 1:
            raise ValueError(f"num_samples must be >= 1, got {num_samples}")
        if max_iterations < 1:
            raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")
        if num_batches < 1:
            raise ValueError(f"num_batches must be >= 1, got {num_batches}")
        if energy_tol < 0:
            raise ValueError(f"energy_tol must be >= 0, got {energy_tol}")
        if occupancies_tol < 0:
            raise ValueError(f"occupancies_tol must be >= 0, got {occupancies_tol}")

        algorithm_start = time.time()

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=geometry,
            basis_set=self.experiment_spec.basis_set,
        )

        norb = bundle.num_spatial_orbitals
        num_elec_alpha = bundle.num_electrons_alpha
        num_elec_beta = bundle.num_electrons_beta
        rng = np.random.default_rng(self.experiment_spec.seed)

        depth = max(2, self.experiment_spec.max_iterations // 20)
        ansatz = self._get_ansatz(bundle.num_qubits, depth=depth)
        sampling_circuit, sampling_params = self._bind_sampling_parameters(ansatz, rng)

        if samples_per_batch is None:
            samples_per_batch = num_samples
        samples_per_batch = max(1, samples_per_batch)

        avg_occupancies: tuple[np.ndarray, np.ndarray] = (
            np.full(norb, num_elec_alpha / max(1, norb), dtype=float),
            np.full(norb, num_elec_beta / max(1, norb), dtype=float),
        )

        convergence_history: list[float] = []
        iteration_diagnostics: list[dict[str, Any]] = []
        converged = False
        shots_used = 0
        valid_subsample_total = 0
        max_unique_bitstrings = 0
        best_subspace_dim = 0
        prev_occupancies: tuple[np.ndarray, np.ndarray] | None = None

        hf_seed = self._hartree_fock_seed_bitstring(
            norb=norb,
            num_elec_alpha=num_elec_alpha,
            num_elec_beta=num_elec_beta,
        )

        for iteration in range(max_iterations):
            current_num_samples = num_samples * (iteration + 1)
            raw_counts = self._sample_counts(
                circuit=sampling_circuit,
                shots=current_num_samples,
            )
            shots_used += int(sum(raw_counts.values()))

            bitstring_matrix, probabilities = counts_to_arrays(raw_counts)
            max_unique_bitstrings = max(
                max_unique_bitstrings,
                int(bitstring_matrix.shape[0]),
            )

            recovered_bitstrings, recovered_probabilities = recover_configurations(
                bitstring_matrix,
                probabilities,
                avg_occupancies=avg_occupancies,
                num_elec_a=num_elec_alpha,
                num_elec_b=num_elec_beta,
                rand_seed=rng,
            )

            recovered_bitstrings = np.unique(
                np.vstack([recovered_bitstrings, hf_seed]),
                axis=0,
            )

            # Keep probabilities normalized after appending a zero-probability HF seed row.
            if recovered_probabilities.shape[0] == recovered_bitstrings.shape[0] - 1:
                recovered_probabilities = np.append(recovered_probabilities, 0.0)
            prob_sum = float(np.sum(recovered_probabilities))
            if prob_sum > 0:
                recovered_probabilities = recovered_probabilities / prob_sum
            else:
                recovered_probabilities = np.full(
                    recovered_bitstrings.shape[0],
                    1.0 / recovered_bitstrings.shape[0],
                    dtype=float,
                )

            try:
                postselected_bitstrings, postselected_probabilities = (
                    postselect_by_hamming_right_and_left(
                        recovered_bitstrings,
                        recovered_probabilities,
                        hamming_left=num_elec_beta,
                        hamming_right=num_elec_alpha,
                    )
                )
                subsamples = subsample(
                    postselected_bitstrings,
                    postselected_probabilities,
                    samples_per_batch=min(samples_per_batch, max(1, current_num_samples)),
                    num_batches=num_batches,
                    rand_seed=rng,
                )
            except ValueError:
                subsamples = []
            except Exception:
                subsamples = []

            if not subsamples:
                filtered = self._filter_bitstrings_by_hamming(
                    recovered_bitstrings,
                    hamming_left=num_elec_beta,
                    hamming_right=num_elec_alpha,
                )
                subsamples = [filtered if filtered.shape[0] > 0 else hf_seed]

            best_energy: float | None = None
            best_occupancies: tuple[np.ndarray, np.ndarray] | None = None
            best_valid_subsamples = 0
            best_iteration_subspace_dim = 0

            for subspace in subsamples:
                filtered_subspace = self._filter_bitstrings_by_hamming(
                    subspace,
                    hamming_left=num_elec_beta,
                    hamming_right=num_elec_alpha,
                )
                if filtered_subspace.shape[0] == 0:
                    continue

                try:
                    electronic_energy, sci_state, occupancies, _ = solve_fermion(
                        filtered_subspace,
                        bundle.one_body_tensor,
                        bundle.two_body_tensor,
                        open_shell=False,
                        spin_sq=0.0,
                        max_cycle=200,
                    )
                except Exception:
                    continue

                total_energy = float(electronic_energy + bundle.core_energy)
                subspace_dim = int(np.asarray(sci_state.amplitudes).size)
                best_valid_subsamples += 1

                if best_energy is None or total_energy < best_energy:
                    best_energy = total_energy
                    best_occupancies = (
                        np.asarray(occupancies[0], dtype=float),
                        np.asarray(occupancies[1], dtype=float),
                    )
                    best_iteration_subspace_dim = subspace_dim

            valid_subsample_total += best_valid_subsamples
            if best_energy is None or best_occupancies is None:
                best_energy = float(bundle.core_energy)
                best_occupancies = avg_occupancies

            convergence_history.append(best_energy)
            best_subspace_dim = max(best_subspace_dim, best_iteration_subspace_dim)

            energy_delta = None
            if len(convergence_history) >= 2:
                energy_delta = abs(convergence_history[-1] - convergence_history[-2])

            occupancy_delta = None
            if prev_occupancies is not None:
                occupancy_delta = float(
                    max(
                        np.max(np.abs(best_occupancies[0] - prev_occupancies[0])),
                        np.max(np.abs(best_occupancies[1] - prev_occupancies[1])),
                    )
                )
            prev_occupancies = best_occupancies
            avg_occupancies = best_occupancies

            iteration_diagnostics.append(
                {
                    "iteration": iteration,
                    "num_raw_samples": current_num_samples,
                    "num_unique_bitstrings": int(bitstring_matrix.shape[0]),
                    "num_recovered_bitstrings": int(recovered_bitstrings.shape[0]),
                    "num_valid_subsamples": best_valid_subsamples,
                    "best_subspace_dimension": best_iteration_subspace_dim,
                    "energy": best_energy,
                    "energy_delta": energy_delta,
                    "occupancy_delta": occupancy_delta,
                }
            )

            if (
                energy_delta is not None
                and occupancy_delta is not None
                and energy_delta <= energy_tol
                and occupancy_delta <= occupancies_tol
            ):
                converged = True
                break

            # Mild parameter drift increases subspace diversity without adding a VQE loop.
            if sampling_params.size > 0:
                sampling_params = np.asarray(
                    sampling_params + rng.normal(loc=0.0, scale=0.05, size=sampling_params.shape),
                    dtype=float,
                )
                sampling_circuit = ansatz.assign_parameters(
                    dict(zip(ansatz.parameters, sampling_params))
                )

        algorithm_wall_time = time.time() - algorithm_start

        final_energy = convergence_history[-1] if convergence_history else float(bundle.core_energy)
        energy_error = abs(final_energy - self.reference_energy)
        convergence_criterion = (
            f"abs(delta_energy) <= {energy_tol} and "
            f"max_orbital_occupancy_delta <= {occupancies_tol}"
        )

        metrics = BenchmarkMetrics(
            final_energy=final_energy,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=len(convergence_history),
            wall_time_seconds=algorithm_wall_time,
            converged=converged,
            convergence_history=convergence_history,
            shots_used=shots_used,
            chemistry_pipeline="pyscf+ffsim+qiskit-addon-sqd",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(bundle.qubit_hamiltonian_matrix.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion=convergence_criterion,
            diagnostics={
                "max_unique_bitstrings": max_unique_bitstrings,
                "valid_subsample_count_total": valid_subsample_total,
                "best_subspace_dimension": best_subspace_dim,
                "iterations_executed": len(convergence_history),
                "samples_per_batch": samples_per_batch,
                "num_batches": num_batches,
                "iteration_diagnostics": iteration_diagnostics,
            },
        )

        return final_energy, metrics
