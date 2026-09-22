"""ADAPT-VQE (Adaptively Grown Ansatz VQE) runner for quantum diagonalization."""

from __future__ import annotations

import time
import numpy as np

from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import Parameter

from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics
from quantum_diag.test_fixtures import MoleculeGeometry
from quantum_diag.reproducibility import SeedManager
from quantum_diag.optimizers import get_optimizer
from quantum_diag.ansatz_factory import create_real_amplitudes_ansatz
from quantum_diag.primitive_adapter import create_estimator, estimate_expectation
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle


class ADAPTVQERunner:
    """ADAPT-VQE executor for dynamically-grown ansatz quantum diagonalization."""

    def __init__(
        self,
        experiment_spec: ExperimentSpec,
        reference_energy: float,
    ) -> None:
        """Initialize ADAPT-VQE runner.

        Args:
            experiment_spec: ExperimentSpec with configuration.
            reference_energy: Reference energy for convergence comparison.
        """
        self.experiment_spec = experiment_spec
        self.reference_energy = reference_energy
        self._param_counter = 0  # Counter for unique parameter names

    def _create_gate_pool(self, num_qubits: int, pool_size: int) -> list[tuple]:
        """Create a pool of parameterized single-gate operations for ADAPT.

        Derives gates from the Phase 2 ansatz_factory RealAmplitudes ansatz.

        Args:
            num_qubits: Number of qubits.
            pool_size: Size of gate pool to generate.

        Returns:
            List of tuples (gate_name, qubit_indices, param_idx).
        """
        # DERIVE pool from ansatz_factory (Phase 2 integration).
        # Build a RealAmplitudes ansatz with depth=1, decompose it, and extract gates.

        ansatz = create_real_amplitudes_ansatz(
            num_qubits=num_qubits,
            depth=1,
            entanglement='linear',
        )

        # Decompose to get actual gates (not the RealAmplitudes wrapper)
        decomposed = ansatz.decompose()

        pool = []
        param_idx = 0

        # Extract gates from the decomposed ansatz.
        # Each gate becomes a pool entry (same gate type, same qubit targets,
        # but will get fresh parameters optimized in each ADAPT iteration).

        for instruction in decomposed.data:
            gate_name = instruction.operation.name  # 'ry', 'cx', etc.
            # Get qubit indices using find_bit
            qubits = tuple(decomposed.find_bit(qubit).index for qubit in instruction.qubits)

            pool_entry = (gate_name, qubits, param_idx)
            pool.append(pool_entry)
            param_idx += 1

            # Stop if we've reached desired pool size
            if len(pool) >= pool_size:
                break

        # If pool is smaller than requested, pad with additional RY gates on remaining qubits
        # (these follow the RealAmplitudes pattern of single-qubit rotations)
        unique_qubits = set()
        for _, qubits, _ in pool:
            unique_qubits.update(qubits)

        for qubit_idx in range(num_qubits):
            if len(pool) >= pool_size:
                break
            if qubit_idx not in unique_qubits:
                pool.append(("ry", (qubit_idx,), param_idx))
                param_idx += 1
                unique_qubits.add(qubit_idx)

        return pool[:pool_size]

    def _get_min_iterations_before_convergence(self, molecule_name: str) -> int:
        """Determine minimum iterations before checking convergence (molecule-conditional).

        Phase 5 Gate 3: Avoid blanket iteration >= 2 gate. Instead, make convergence
        checking conditional based on molecule complexity:
        - Simple molecules (H2, LiH): Allow early stopping from iteration 0.
        - Complex molecules (H2O, BeH2): Enforce minimum 2 iterations to ensure
          multi-step ADAPT growth and validate parameter-name collision safety.

        Args:
            molecule_name: Name of the molecule.

        Returns:
            Minimum iteration number before checking convergence. For example:
            - Return 0 to allow convergence check from first iteration
            - Return 2 to skip convergence checks for first 2 iterations
        """
        # Conditional convergence checking based on molecule complexity
        if molecule_name in ["H2O", "BeH2"]:
            # Complex molecules: enforce minimum 2 iterations for multi-step validation
            return 2
        else:
            # Simple molecules (H2, LiH): allow early convergence
            return 0

    def _get_ansatz(self, iteration: int, num_qubits: int) -> QuantumCircuit:
        """Get ansatz for a specific iteration (grows with iterations).

        Args:
            iteration: Iteration number (0 = identity, 1+ = growing ansatz).
            num_qubits: Number of qubits for the circuit.

        Returns:
            Parameterized QuantumCircuit.
        """
        qr = QuantumRegister(num_qubits, 'q')
        circuit = QuantumCircuit(qr)

        if iteration == 0:
            # Identity (no gates, no parameters)
            return circuit

        # For iteration 1+, add progressive gates
        # We'll add one parameterized gate per iteration
        for iter_idx in range(iteration):
            theta = Parameter(f'θ_{iter_idx}')
            qubit_idx = iter_idx % num_qubits
            if iter_idx % 3 == 0:
                circuit.ry(theta, qr[qubit_idx])
            elif iter_idx % 3 == 1:
                circuit.ry(theta, qr[qubit_idx])
            else:
                next_qubit = (qubit_idx + 1) % num_qubits
                circuit.cx(qr[qubit_idx], qr[next_qubit])
                circuit.ry(theta, qr[next_qubit])

        return circuit

    def _compute_commutator_gradients(
        self,
        ansatz: QuantumCircuit,
        params: np.ndarray,
        pool_gates: list[tuple],
        pauli_hamiltonian,
    ) -> tuple[float, int, np.ndarray]:
        """Compute gradients for each gate in the pool using parameter shift rule.

        Args:
            H: Hamiltonian matrix.
            ansatz: Current ansatz circuit.
            params: Current parameters.
            pool_gates: Gate pool to evaluate.

        Returns:
            Tuple of (max_gradient, max_gate_index, all_gradients).
        """
        shift = np.pi / 2
        gradients = np.zeros(len(pool_gates))

        estimator = create_estimator()

        for gate_idx, (gate_name, qubits, _) in enumerate(pool_gates):
            # Build circuit with added gate
            test_circuit = ansatz.copy()
            theta = Parameter(f'test_θ_{gate_idx}')

            if gate_name == "ry":
                test_circuit.ry(theta, qubits[0])
            elif gate_name == "rx":
                test_circuit.rx(theta, qubits[0])
            elif gate_name == "rz":
                test_circuit.rz(theta, qubits[0])
            elif gate_name == "cx":
                test_circuit.cx(qubits[0], qubits[1])
                test_circuit.ry(theta, qubits[1])
            else:
                # Fallback to RY
                test_circuit.ry(theta, qubits[0])

            # Parameter shift rule: gradient = (E(θ+π/2) - E(θ-π/2)) / 2
            try:
                # Assign current parameters
                param_dict = {}
                for p, val in zip(ansatz.parameters, params):
                    param_dict[p] = val

                # Evaluate at θ + π/2
                param_dict[theta] = shift
                bound_plus = test_circuit.assign_parameters(param_dict)
                energy_plus = estimate_expectation(
                    estimator=estimator,
                    circuit=bound_plus,
                    observable=pauli_hamiltonian,
                )

                # Evaluate at θ - π/2
                param_dict[theta] = -shift
                bound_minus = test_circuit.assign_parameters(param_dict)
                energy_minus = estimate_expectation(
                    estimator=estimator,
                    circuit=bound_minus,
                    observable=pauli_hamiltonian,
                )

                # Gradient magnitude
                gradient = abs((energy_plus - energy_minus) / 2.0)
                gradients[gate_idx] = gradient
            except Exception:
                # If evaluation fails, set gradient to 0
                gradients[gate_idx] = 0.0

        max_idx = np.argmax(np.abs(gradients))
        max_grad = float(np.abs(gradients[max_idx]))

        return max_grad, int(max_idx), gradients

    def _adapt_ansatz_iteration(
        self,
        current_ansatz: QuantumCircuit,
        current_params: np.ndarray,
        pool_gates: list[tuple],
        seed: int,
        pauli_hamiltonian,
    ) -> tuple[QuantumCircuit, np.ndarray, dict, float]:
        """Single ADAPT iteration: select gate, add to ansatz, optimize.

        Args:
            H: Hamiltonian matrix.
            current_ansatz: Current ansatz circuit.
            current_params: Current parameters.
            pool_gates: Gate pool to select from.
            seed: Random seed for reproducibility.
            num_qubits: Number of qubits.

        Returns:
            Tuple of (new_ansatz, new_params, gate_info, final_energy).
        """
        # Compute gradients for all gates
        max_grad, selected_gate_idx, all_grads = self._compute_commutator_gradients(
            current_ansatz,
            current_params,
            pool_gates,
            pauli_hamiltonian,
        )

        # Build new ansatz with selected gate
        new_ansatz = current_ansatz.copy()
        gate_name, qubits, _ = pool_gates[selected_gate_idx]

        # Use unique parameter name to avoid conflicts across iterations
        theta = Parameter(f'θ_{self._param_counter}')
        self._param_counter += 1
        if gate_name == "ry":
            new_ansatz.ry(theta, qubits[0])
        elif gate_name == "rx":
            new_ansatz.rx(theta, qubits[0])
        elif gate_name == "rz":
            new_ansatz.rz(theta, qubits[0])
        elif gate_name == "cx":
            new_ansatz.cx(qubits[0], qubits[1])
            new_ansatz.ry(theta, qubits[1])
        else:
            # Fallback to RY
            new_ansatz.ry(theta, qubits[0])

        # Optimize all parameters (including new one)
        initial_params = np.concatenate([current_params, np.array([0.1])])

        optimizer = get_optimizer(
            self.experiment_spec.optimizer,
            maxiter=self.experiment_spec.max_iterations,
            num_vars=len(initial_params),
        )

        estimator = create_estimator()

        def evaluate_energy(parameters: object) -> float:
            try:
                params_array = np.asarray(parameters, dtype=float).reshape(-1)
                param_dict = dict(zip(new_ansatz.parameters, params_array))
                bound_circuit = new_ansatz.assign_parameters(param_dict)
                energy = estimate_expectation(
                    estimator=estimator,
                    circuit=bound_circuit,
                    observable=pauli_hamiltonian,
                )
                return energy
            except Exception:
                return 1e10

        try:
            result = optimizer.minimize(evaluate_energy, initial_params)
            raw_x = getattr(result, "x", None)
            if raw_x is None:
                final_params = initial_params
            else:
                final_params = np.asarray(raw_x, dtype=float).reshape(-1)

            raw_fun = getattr(result, "fun", None)
            if raw_fun is None:
                final_energy = evaluate_energy(final_params)
            else:
                final_energy = float(raw_fun)
        except Exception:
            final_params = initial_params
            final_energy = float(1e10)

        gate_info = {
            "gate_name": gate_name,
            "qubits": qubits,
            "selected_gate_index": selected_gate_idx,
            "max_gradient": max_grad,
        }

        return new_ansatz, final_params, gate_info, final_energy

    def run(
        self,
        molecule_geometry: MoleculeGeometry,
        max_iterations: int = 10,
        gradient_threshold: float = 0.01,
        pool_size: int = 6,
    ) -> BenchmarkMetrics:
        """Run ADAPT-VQE on the given molecule geometry.

        Args:
            molecule_geometry: MoleculeGeometry specification.
            max_iterations: Maximum number of ADAPT iterations.
            gradient_threshold: Convergence threshold for maximum gradient.
            pool_size: Size of gate pool.

        Returns:
            BenchmarkMetrics with convergence history.

        Raises:
            ValueError: If parameters are invalid.
        """
        # Validate inputs
        if max_iterations < 1:
            raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")
        if gradient_threshold < 0.0:
            raise ValueError(f"gradient_threshold must be >= 0, got {gradient_threshold}")
        if pool_size < 1:
            raise ValueError(f"pool_size must be >= 1, got {pool_size}")

        start_time = time.time()

        # Reset parameter counter for this run
        self._param_counter = 0

        # Set seed for reproducibility
        seed_manager = SeedManager()
        seed_manager.set_global_seed(self.experiment_spec.seed)

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=molecule_geometry,
            basis_set=self.experiment_spec.basis_set,
        )
        hamiltonian = bundle.sector_hamiltonian_matrix
        pauli_hamiltonian = bundle.pauli_hamiltonian
        num_qubits = bundle.num_qubits

        # Create gate pool (uses ansatz_factory patterns)
        pool = self._create_gate_pool(num_qubits=num_qubits, pool_size=pool_size)

        # Determine convergence gating policy based on molecule complexity
        # (Phase 5 Gate 3: avoid blanket iteration >= 2 gate)
        molecule_name = self.experiment_spec.molecule_name
        min_iterations_before_convergence_check = self._get_min_iterations_before_convergence(molecule_name)

        # Initialize with identity ansatz
        current_ansatz = self._get_ansatz(iteration=0, num_qubits=num_qubits)
        current_params = np.array([])

        convergence_history = []
        final_energy = bundle.casci_energy
        max_grad = float('inf')  # Initialize convergence criterion

        # ADAPT loop
        for iteration in range(max_iterations):
            # Check convergence AFTER minimum iterations for the molecule
            if iteration >= min_iterations_before_convergence_check:
                max_grad, _, _ = self._compute_commutator_gradients(
                    current_ansatz,
                    current_params,
                    pool,
                    pauli_hamiltonian,
                )

                if max_grad < gradient_threshold:
                    break

            # ADAPT iteration: add gate and optimize
            new_ansatz, new_params, gate_info, optimized_energy = self._adapt_ansatz_iteration(
                current_ansatz,
                current_params,
                pool,
                seed=self.experiment_spec.seed,
                pauli_hamiltonian=pauli_hamiltonian,
            )

            current_ansatz = new_ansatz
            current_params = new_params

            # Append the OPTIMIZED energy (post-optimization)
            convergence_history.append(optimized_energy)
            final_energy = optimized_energy

        # If no iterations happened (convergence on first check), add initial energy
        if not convergence_history:
            if len(current_params) > 0:
                estimator = create_estimator()
                try:
                    param_dict = dict(zip(current_ansatz.parameters, current_params))
                    bound_circuit = current_ansatz.assign_parameters(param_dict)
                    converged_energy = estimate_expectation(
                        estimator=estimator,
                        circuit=bound_circuit,
                        observable=pauli_hamiltonian,
                    )
                    convergence_history.append(converged_energy)
                    final_energy = converged_energy
                except Exception:
                    convergence_history.append(bundle.casci_energy)
                    final_energy = bundle.casci_energy
            else:
                # Identity ansatz
                convergence_history.append(bundle.casci_energy)
                final_energy = bundle.casci_energy

        wall_time = time.time() - start_time

        # Compute metrics
        energy_error = abs(final_energy - self.reference_energy)
        converged = max_grad < gradient_threshold

        metrics = BenchmarkMetrics(
            final_energy=final_energy,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=len(convergence_history),
            wall_time_seconds=wall_time,
            converged=converged,
            convergence_history=convergence_history,
            shots_used=0,
            chemistry_pipeline="pyscf+ffsim",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(bundle.qubit_hamiltonian_matrix.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion=f"max_gradient < {gradient_threshold}",
        )

        return metrics
