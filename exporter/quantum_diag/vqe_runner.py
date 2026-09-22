"""VQE (Variational Quantum Eigensolver) executor."""

from __future__ import annotations

import time
import numpy as np
import warnings

from qiskit import QuantumCircuit

from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics
from quantum_diag.test_fixtures import MoleculeGeometry
from quantum_diag.reproducibility import SeedManager
from quantum_diag.ansatz_factory import (
    create_real_amplitudes_ansatz,
    create_two_local_ansatz,
    create_uccsd_ansatz_stub,
    create_lucj_ansatz,
)
from quantum_diag.optimizers import get_optimizer
from quantum_diag.callbacks import IterationCallback
from quantum_diag.primitive_adapter import create_estimator, estimate_expectation
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle


class VQERunner:
    """VQE executor for quantum diagonalization experiments."""

    def __init__(
        self,
        experiment_spec: ExperimentSpec,
        reference_energy: float,
    ) -> None:
        """Initialize VQE runner.

        Args:
            experiment_spec: ExperimentSpec with configuration.
            reference_energy: Reference energy for convergence comparison.
        """
        self.experiment_spec = experiment_spec
        self.reference_energy = reference_energy

    def _get_ansatz(self, num_qubits: int) -> QuantumCircuit:
        """Get ansatz based on experiment specification.

        Args:
            num_qubits: Number of qubits for the ansatz.

        Returns:
            Parameterized QuantumCircuit ansatz.
        """
        ansatz_type = self.experiment_spec.ansatz_type
        max_depth = max(1, self.experiment_spec.max_iterations // 20)  # Reasonable depth

        if ansatz_type == "RealAmplitudes":
            return create_real_amplitudes_ansatz(
                num_qubits=num_qubits,
                depth=max_depth,
                entanglement='full',
            )
        elif ansatz_type == "HEA":
            # Hardware-efficient ansatz proxy via TwoLocal.
            return create_two_local_ansatz(
                num_qubits=num_qubits,
                depth=max_depth,
                rotation_blocks='ry',
                entanglement_blocks='cx',
            )
        elif ansatz_type == "EDA":
            # Entanglement-driven ansatz proxy with linear connectivity.
            return create_real_amplitudes_ansatz(
                num_qubits=num_qubits,
                depth=max_depth,
                entanglement='linear',
            )
        elif ansatz_type == "TwoLocal":
            return create_two_local_ansatz(
                num_qubits=num_qubits,
                depth=max_depth,
                rotation_blocks='ry',
                entanglement_blocks='cx',
            )
        elif ansatz_type == "UCCSD":
            num_params = 2 * num_qubits * max_depth
            return create_uccsd_ansatz_stub(
                num_qubits=num_qubits,
                num_parameters=num_params,
            )
        elif ansatz_type == "LUCJ":
            return create_lucj_ansatz(
                num_qubits=num_qubits,
                depth=max_depth,
            )
        raise ValueError(
            f"Unsupported ansatz_type '{ansatz_type}'. "
            "Valid options are: RealAmplitudes, TwoLocal, UCCSD, HEA, EDA, LUCJ"
        )

    def run(
        self,
        molecule_geometry: MoleculeGeometry,
    ) -> tuple[float, BenchmarkMetrics]:
        """Run VQE on the given molecule geometry.

        Args:
            molecule_geometry: MoleculeGeometry specification.

        Returns:
            Tuple of (final_energy, BenchmarkMetrics).
        """
        start_time = time.time()

        # Set seed for reproducibility
        seed_manager = SeedManager()
        seed_manager.set_global_seed(self.experiment_spec.seed)

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=molecule_geometry,
            basis_set=self.experiment_spec.basis_set,
        )
        num_qubits = bundle.num_qubits
        pauli_hamiltonian = bundle.pauli_hamiltonian

        # Create ansatz
        ansatz = self._get_ansatz(num_qubits)

        # Create callback for tracking iteration metrics
        callback = IterationCallback(reference_energy=self.reference_energy)

        # Initial parameters (random based on seed)
        num_params = ansatz.num_parameters
        initial_params = np.random.uniform(-2 * np.pi, 2 * np.pi, num_params)

        if self.experiment_spec.optimizer == "COBYLA":
            min_maxfun = num_params + 2
            if self.experiment_spec.max_iterations < min_maxfun:
                warnings.warn(
                    "Configured max_iterations is smaller than COBYLA minimum "
                    f"MAXFUN for this ansatz (max_iterations={self.experiment_spec.max_iterations}, "
                    f"required>={min_maxfun}). SciPy will auto-adjust MAXFUN.",
                    UserWarning,
                )

        # Get optimizer (note: optimizer expects objective function signature)
        optimizer = get_optimizer(
            self.experiment_spec.optimizer,
            maxiter=self.experiment_spec.max_iterations,
            num_vars=num_params,
        )

        # Use simplified VQE with manual energy evaluation via statevector estimator.
        # In this execution mode, shots are not consumed.
        estimator = create_estimator()
        failure_count = 0

        # Define energy evaluation function
        def evaluate_energy(parameters: np.ndarray) -> float:
            try:
                # Ensure parameters are 1D
                if parameters.ndim > 1:
                    parameters = parameters.flatten()

                # Assign parameters to ansatz
                param_dict = dict(zip(ansatz.parameters, parameters))
                bound_circuit = ansatz.assign_parameters(param_dict)

                # Run estimator to get expectation value
                energy = estimate_expectation(
                    estimator=estimator,
                    circuit=bound_circuit,
                    observable=pauli_hamiltonian,
                )

                # Call callback
                iteration_num = len(callback.iteration_history)
                callback(iteration=iteration_num,
                        parameters=parameters,
                        energy=energy)

                return energy
            except Exception as e:
                nonlocal failure_count
                failure_count += 1
                if failure_count >= 3:
                    raise RuntimeError(
                        "Energy evaluation failed repeatedly during VQE optimization"
                    ) from e
                return 1e10

        # Run optimization
        try:
            result = optimizer.minimize(evaluate_energy, initial_params)
        except RuntimeError as exc:
            raise ValueError("VQE optimization failed due to repeated estimator errors") from exc

        final_energy = result.fun

        wall_time = time.time() - start_time

        # Compute metrics
        energy_error = abs(final_energy - self.reference_energy)
        converged = callback.convergence_reached(tolerance=1e-2)

        metrics = BenchmarkMetrics(
            final_energy=final_energy,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=len(callback.iteration_history),
            wall_time_seconds=wall_time,
            converged=converged,
            convergence_history=callback.energy_history.copy(),
            shots_used=0,
            chemistry_pipeline="pyscf+ffsim",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(bundle.qubit_hamiltonian_matrix.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion="energy_range(last_3_iterations) <= 1e-2",
        )

        return final_energy, metrics
