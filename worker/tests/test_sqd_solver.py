"""Tests for SQD solver HF reference circuit and sampling behavior."""

from __future__ import annotations

from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest

from worker.adapters.result_adapter import normalize_result
from worker.chemistry.algorithms.sqd import sampling_execution as sqd_sampling_execution
from worker.chemistry.algorithms.sqd import workflow as sqd_solver
from worker.chemistry.algorithms.sqd.workflow import (
    _aggregate_bitstring_frequencies,
    _build_hf_reference_circuit,
    _build_sqd_circuit_artifacts,
    _sample_bitstring_matrix,
    _selected_ci_strings_from_bitstrings,
    _serialize_circuit_preview,
)
from worker.jobs.control_state import RunCancelled, RunPaused

CONFIGURATION_RECOVERY_MODULE = "qiskit_addon_sqd.configuration_recovery"
FERMION_MODULE = "qiskit_addon_sqd.fermion"


def _import_sqd_addon_modules():
    configuration_recovery = pytest.importorskip(CONFIGURATION_RECOVERY_MODULE)
    fermion = pytest.importorskip(FERMION_MODULE)
    return configuration_recovery, fermion


class _ZeroAngleRng:
    def uniform(self, _low: float, _high: float, *, size: int) -> np.ndarray:
        return np.zeros(size)


class _UnexpectedRng:
    def uniform(self, *_args, **_kwargs) -> np.ndarray:
        raise AssertionError("HF reference circuit must not sample random rotations")


def test_hf_reference_circuit_qubit_count() -> None:
    circuit = _build_hf_reference_circuit(8, num_elec_a=2, num_elec_b=2)
    assert circuit.num_qubits == 8
    assert circuit.num_clbits == 8


def test_hf_reference_circuit_x_gate_count_matches_electrons() -> None:
    num_elec_a = 2
    num_elec_b = 3
    circuit = _build_hf_reference_circuit(10, num_elec_a=num_elec_a, num_elec_b=num_elec_b)

    x_count = sum(1 for instr in circuit.data if instr.operation.name == "x")
    assert x_count == num_elec_a + num_elec_b


def test_hf_reference_circuit_zero_electrons_produces_no_x_gates() -> None:
    circuit = _build_hf_reference_circuit(4, num_elec_a=0, num_elec_b=0)
    x_count = sum(1 for instr in circuit.data if instr.operation.name == "x")
    assert x_count == 0


def test_hf_reference_circuit_preserves_sector_without_random_rotations() -> None:
    circuit = _build_hf_reference_circuit(
        8,
        num_elec_a=2,
        num_elec_b=1,
        rng=_UnexpectedRng(),  # type: ignore[arg-type]
    )

    assert all(instruction.operation.name != "ry" for instruction in circuit.data)


def test_hf_reference_circuit_clamps_electrons_to_norb() -> None:
    norb = 2
    circuit = _build_hf_reference_circuit(2 * norb, num_elec_a=norb + 5, num_elec_b=norb + 5)
    x_count = sum(1 for instr in circuit.data if instr.operation.name == "x")
    assert x_count <= 2 * norb


def test_serialize_circuit_preview_includes_qasm_and_svg() -> None:
    circuit = _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1)

    preview = _serialize_circuit_preview(circuit)

    assert preview["qubits"] == 4
    assert preview["classical_bits"] == 4
    assert "OPENQASM 3.0" in preview["qasm"]
    assert "<svg" in preview["diagram_svg"]


def test_build_sqd_circuit_artifacts_downsamples_rich_previews() -> None:
    circuits = [
        (1, _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1)),
        (2, _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1)),
        (3, _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1)),
    ]

    artifacts, policy = _build_sqd_circuit_artifacts(circuits, total_iterations=3)

    assert policy["name"] == "all_or_windowed_sqd_iterations"
    assert policy["stored_iterations"] == [1, 2, 3]
    assert policy["dropped_iterations"] == []
    assert len(artifacts) == 3
    assert artifacts[0]["role"] == "sqd_sampling"
    assert artifacts[0]["preview"]["qasm"]
    assert artifacts[1]["preview"]["qasm"]
    assert artifacts[1]["downsampling"]["policy"] == policy["name"]
    assert artifacts[2]["preview"]["diagram_svg"]
    assert artifacts[2]["representative"] is True


def test_build_sqd_circuit_artifacts_marks_reused_measurement_representative() -> None:
    circuit = _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1)

    artifacts, _policy = _build_sqd_circuit_artifacts([(1, circuit)], total_iterations=3)

    assert len(artifacts) == 1
    assert artifacts[0]["iteration"] == 1
    assert artifacts[0]["representative"] is True


def test_build_sqd_circuit_artifacts_windows_large_iteration_sets() -> None:
    circuits = [
        (iteration, _build_hf_reference_circuit(4, num_elec_a=1, num_elec_b=1))
        for iteration in range(1, 41)
    ]

    artifacts, policy = _build_sqd_circuit_artifacts(circuits, total_iterations=40)

    assert policy["name"] == "all_or_windowed_sqd_iterations"
    assert len(policy["stored_iterations"]) == 32
    assert policy["stored_iterations"][:4] == [1, 2, 3, 4]
    assert policy["stored_iterations"][-12:] == list(range(29, 41))
    assert 5 in policy["stored_iterations"]
    assert 28 in policy["stored_iterations"]
    assert len(policy["dropped_iterations"]) == 8
    assert len(artifacts) == 32
    assert artifacts[-1]["iteration"] == 40
    assert artifacts[-1]["representative"] is True


def test_aggregate_bitstring_frequencies_uses_sampler_counts() -> None:
    samples = np.array(
        [
            [True, False, False],
            [True, False, False],
            [False, True, False],
            [True, False, False],
        ],
        dtype=bool,
    )

    unique, probabilities, counts = _aggregate_bitstring_frequencies(samples)

    distribution = {
        tuple(row.tolist()): (float(probability), int(count))
        for row, probability, count in zip(unique, probabilities, counts, strict=False)
    }
    assert distribution[(True, False, False)] == pytest.approx((0.75, 3))
    assert distribution[(False, True, False)] == pytest.approx((0.25, 1))


@pytest.mark.parametrize("num_elec_a,num_elec_b", [(1, 1), (2, 2), (3, 2)])
def test_hf_circuit_hamming_weight_matches_electrons(num_elec_a: int, num_elec_b: int) -> None:
    """The HF circuit must produce bitstrings with Hamming weight = num_elec_a + num_elec_b."""
    from qiskit.primitives import StatevectorSampler

    num_bits = 8
    circuit = _build_hf_reference_circuit(
        num_bits,
        num_elec_a=num_elec_a,
        num_elec_b=num_elec_b,
        rng=_ZeroAngleRng(),  # type: ignore[arg-type]
    )

    sampler = StatevectorSampler()
    job = sampler.run([(circuit,)], shots=10)
    result = job.result()
    data = result[0].data

    bitstrings = None
    if hasattr(data, "keys"):
        for key in data.keys():
            candidate = getattr(data, str(key), None)
            if candidate is not None and hasattr(candidate, "get_bitstrings"):
                bitstrings = candidate.get_bitstrings()
                break

    assert bitstrings is not None, "Sampler did not return bitstrings"
    for bs in bitstrings:
        hamming = sum(c == "1" for c in str(bs).replace(" ", ""))
        assert hamming == num_elec_a + num_elec_b, (
            f"Expected Hamming weight {num_elec_a + num_elec_b}, got {hamming} for bitstring '{bs}'"
        )


@pytest.mark.parametrize(
    ("num_elec_a", "num_elec_b"),
    [
        (1, 0),
        (0, 1),
        (1, 1),
        (2, 1),
    ],
)
def test_sampled_hf_bitstrings_use_addon_right_left_order(
    num_elec_a: int,
    num_elec_b: int,
) -> None:
    """Open-shell HF samples must satisfy qiskit-addon-sqd right/left Hamming checks."""
    from qiskit.primitives import StatevectorSampler
    from qiskit_addon_sqd.fermion import postselect_by_hamming_right_and_left

    norb = 2
    matrix = _sample_bitstring_matrix(
        StatevectorSampler(),
        num_bits=2 * norb,
        total_samples=8,
        num_elec_a=num_elec_a,
        num_elec_b=num_elec_b,
        rng=_ZeroAngleRng(),  # type: ignore[arg-type]
    )

    assert isinstance(matrix, np.ndarray)
    selected, _ = postselect_by_hamming_right_and_left(
        matrix,
        np.full(matrix.shape[0], 1 / matrix.shape[0]),
        hamming_right=num_elec_a,
        hamming_left=num_elec_b,
    )

    assert selected.shape[0] == matrix.shape[0]


def test_sample_bitstring_matrix_uses_supplied_circuit_factory() -> None:
    from qiskit import QuantumCircuit
    from qiskit.primitives import StatevectorSampler

    calls: list[tuple[int, int, int]] = []

    def factory(*, num_bits: int, num_elec_a: int, num_elec_b: int, rng: object) -> QuantumCircuit:
        del rng
        calls.append((num_bits, num_elec_a, num_elec_b))
        circuit = QuantumCircuit(num_bits)
        circuit.x(0)
        return circuit

    matrix, circuit = _sample_bitstring_matrix(
        StatevectorSampler(),
        num_bits=4,
        total_samples=8,
        num_elec_a=1,
        num_elec_b=0,
        sampling_circuit_factory=factory,
        return_circuit=True,
    )

    assert calls == [(4, 1, 0)]
    assert matrix.shape == (8, 4)
    assert circuit.num_clbits == 4
    assert any(instruction.operation.name == "measure" for instruction in circuit.data)


@pytest.mark.parametrize("measurement_map", [((0, 0),), ((0, 0), (1, 1), (2, 3), (3, 2))])
def test_sample_bitstring_matrix_rejects_incomplete_or_remapped_measurements(
    measurement_map: tuple[tuple[int, int], ...],
) -> None:
    from qiskit import QuantumCircuit

    class _Sampler:
        calls = 0

        def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            raise AssertionError("invalid measurement circuits must fail before submission")

    def factory(*, num_bits: int, num_elec_a: int, num_elec_b: int, rng: object) -> QuantumCircuit:
        del num_elec_a, num_elec_b, rng
        circuit = QuantumCircuit(num_bits, num_bits)
        circuit.x(3)
        for qubit, clbit in measurement_map:
            circuit.measure(qubit, clbit)
        return circuit

    sampler = _Sampler()
    with pytest.raises(ValueError, match="measure every qubit|map each qubit"):
        _sample_bitstring_matrix(
            sampler,
            num_bits=4,
            total_samples=8,
            num_elec_a=1,
            num_elec_b=1,
            sampling_circuit_factory=factory,
        )

    assert sampler.calls == 0


@pytest.mark.parametrize("control_exception", [RunCancelled, RunPaused])
def test_sample_bitstring_matrix_propagates_run_control_without_retry(control_exception) -> None:
    class _ControllingSampler:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            raise control_exception("run stopped during sampler submission")

    sampler = _ControllingSampler()

    with pytest.raises(control_exception, match="run stopped during sampler submission"):
        _sample_bitstring_matrix(
            sampler,
            num_bits=4,
            total_samples=8,
            num_elec_a=1,
            num_elec_b=1,
        )

    assert sampler.calls == 1


def test_sample_bitstring_matrix_records_retry_work(monkeypatch) -> None:
    class _Sampler:
        def __init__(self) -> None:
            self.shots: list[int] = []

        def run(self, *args, **kwargs):
            del args
            self.shots.append(kwargs["shots"])
            if len(self.shots) == 1:
                raise RuntimeError("transient sampler failure")
            return SimpleNamespace(result=lambda: object())

    monkeypatch.setattr(
        sqd_sampling_execution,
        "extract_sampler_bitstrings",
        lambda _result: ["0000", "0000"],
    )
    sampler = _Sampler()
    ledger: dict[str, int] = {}

    matrix = _sample_bitstring_matrix(
        sampler,
        num_bits=4,
        total_samples=8,
        num_elec_a=0,
        num_elec_b=0,
        work_ledger=ledger,
    )

    assert matrix.shape == (2, 4)
    assert sampler.shots == [8, 16]
    assert ledger == {
        "sampler_run_attempts": 2,
        "sampler_successful_runs": 1,
        "sampler_retry_count": 1,
        "sampler_requested_shots_total": 24,
        "sampler_returned_raw_sample_rows": 2,
    }


def test_sample_bitstring_matrix_can_retry_without_increasing_requested_shots(
    monkeypatch,
) -> None:
    class _Sampler:
        def __init__(self) -> None:
            self.shots: list[int] = []

        def run(self, *args, **kwargs):
            del args
            self.shots.append(kwargs["shots"])
            if len(self.shots) == 1:
                raise RuntimeError("transient sampler failure")
            return SimpleNamespace(result=lambda: object())

    monkeypatch.setattr(
        sqd_sampling_execution,
        "extract_sampler_bitstrings",
        lambda _result: ["0000"] * 8,
    )
    sampler = _Sampler()
    ledger: dict[str, int] = {}

    matrix = _sample_bitstring_matrix(
        sampler,
        num_bits=4,
        total_samples=8,
        work_ledger=ledger,
        retry_with_increased_shots=False,
    )

    assert matrix.shape == (8, 4)
    assert sampler.shots == [8, 8]
    assert ledger["sampler_retry_count"] == 1
    assert ledger["sampler_requested_shots_total"] == 16


def test_sample_bitstring_matrix_does_not_retry_runtime_result_failure() -> None:
    class _RuntimeJob:
        def result(self):
            raise TimeoutError("runtime result timed out")

    class _RuntimeSampler:
        allow_sampler_submission_retries = False

        def __init__(self) -> None:
            self.calls = 0

        def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            return _RuntimeJob()

    sampler = _RuntimeSampler()
    ledger: dict[str, int] = {}

    with pytest.raises(TimeoutError, match="runtime result timed out"):
        _sample_bitstring_matrix(
            sampler,
            num_bits=4,
            total_samples=8,
            work_ledger=ledger,
        )

    assert sampler.calls == 1
    assert ledger["sampler_run_attempts"] == 1
    assert ledger["sampler_retry_count"] == 0
    assert ledger["sampler_requested_shots_total"] == 8
    assert ledger.get("sampler_successful_runs", 0) == 0
    assert ledger.get("sampler_returned_raw_sample_rows", 0) == 0


def test_sample_bitstring_matrix_does_not_resubmit_unreadable_job_result(monkeypatch) -> None:
    class _Job:
        def result(self):
            return object()

    class _Sampler:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            return _Job()

    monkeypatch.setattr(sqd_sampling_execution, "extract_sampler_bitstrings", lambda _: None)
    sampler = _Sampler()

    with pytest.raises(RuntimeError, match="returned no measurement bitstrings"):
        _sample_bitstring_matrix(sampler, num_bits=4, total_samples=8)

    assert sampler.calls == 1


def test_sample_bitstring_matrix_does_not_retry_runtime_submission_failure() -> None:
    class _RuntimeSampler:
        allow_sampler_submission_retries = False

        def __init__(self) -> None:
            self.calls = 0

        def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            raise TimeoutError("runtime submission outcome is unknown")

    sampler = _RuntimeSampler()
    ledger: dict[str, int] = {}

    with pytest.raises(TimeoutError, match="runtime submission outcome is unknown"):
        _sample_bitstring_matrix(
            sampler,
            num_bits=4,
            total_samples=8,
            work_ledger=ledger,
        )

    assert sampler.calls == 1
    assert ledger["sampler_run_attempts"] == 1
    assert ledger["sampler_retry_count"] == 0
    assert ledger["sampler_requested_shots_total"] == 8
    assert ledger.get("sampler_successful_runs", 0) == 0
    assert ledger.get("sampler_returned_raw_sample_rows", 0) == 0


def test_open_shell_selected_ci_strings_preserve_alpha_on_right_half() -> None:
    """The right bitstring half maps to alpha determinants for open-shell SQD."""
    bitstrings = np.array(
        [
            # Display/addon order is [beta_1 beta_0 alpha_1 alpha_0].
            # This determinant has alpha orbitals 0 and 1 occupied, beta orbital 0 occupied.
            [False, True, True, True],
        ],
        dtype=bool,
    )

    ci_strings, summary = _selected_ci_strings_from_bitstrings(
        bitstrings,
        np.array([1.0]),
        max_dim=(4, 4),
        open_shell=True,
    )

    assert ci_strings[0].tolist() == [3]
    assert ci_strings[1].tolist() == [1]
    assert summary["ci_strings_alpha"] == 1
    assert summary["ci_strings_beta"] == 1


def test_closed_shell_selected_ci_strings_share_spin_pool_by_default() -> None:
    """Closed-shell SQD must merge alpha/beta determinant pools by default."""
    bitstrings = np.array(
        [
            [False, True, True, False],
            [False, True, True, False],
            [False, True, True, False],
            [True, False, True, False],
        ],
        dtype=bool,
    )
    probabilities = np.array([0.375, 0.375, 0.125, 0.125], dtype=float)

    default_selection, default_summary = _selected_ci_strings_from_bitstrings(
        bitstrings,
        probabilities,
        max_dim=(1, 1),
        open_shell=False,
        symmetrize_spin=False,
    )
    symmetrized, sym_summary = _selected_ci_strings_from_bitstrings(
        bitstrings,
        probabilities,
        max_dim=(1, 1),
        open_shell=False,
        symmetrize_spin=True,
    )

    assert default_selection[0].tolist() == [2]
    assert default_selection[1].tolist() == [2]
    assert default_summary["spin_symmetrized"] is True
    assert default_summary["selection_pool_mode"] == "shared_spin_pool"
    assert symmetrized[0].tolist() == [2]
    assert symmetrized[1].tolist() == [2]
    assert sym_summary["spin_symmetrized"] is True


def test_run_sqd_does_not_converge_on_single_selected_configuration(monkeypatch) -> None:
    """Stable energy from one selected determinant is insufficient convergence evidence."""
    configuration_recovery, fermion = _import_sqd_addon_modules()

    repeated_sample = np.array([[True, False, True, False]], dtype=bool)
    occupancies = (np.array([1.0, 0.0]), np.array([1.0, 0.0]))

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: repeated_sample,
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings[:1], probabilities[:1]),
    )
    monkeypatch.setattr(
        fermion,
        "solve_fermion",
        lambda *args, **kwargs: (0.0, None, occupancies, 0.0),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 3,
            "samples_per_batch": 16,
            "num_batches": 1,
            "energy_tol": 1e-6,
            "occupancies_tol": 1e-6,
        },
        sampling_circuit_factory=lambda **_kwargs: None,
    )

    assert result.primary_iterations == 2
    assert result.converged is False
    assert (
        result.sci_result_package["termination_reason"]
        == "fixed_point_insufficient_selected_configurations"
    )
    assert result.sci_result_package["min_selected_configurations"] == 2
    assert result.sci_result_package["sampling_source"] == "provided_circuit"
    assert result.sci_result_package["work_ledger"]["recovery_iterations"] == 2
    assert result.sci_result_package["work_ledger"]["selected_ci_batch_solves"] == 2
    assert (
        result.sci_result_package["reference_descriptor"]["preparation_path"]
        == "provided_sampling_circuit"
    )
    assert (
        result.sci_result_package["reference_descriptor"]["metadata"]
        ["state_fingerprint_status"]
        == "not_claimed_from_measurements"
    )


def test_run_sqd_reports_best_observed_energy_not_last_iteration(monkeypatch) -> None:
    configuration_recovery, fermion = _import_sqd_addon_modules()

    sampled = np.array([[False, True, False, True]], dtype=bool)
    energies = iter([-1.0, -1.2, -1.1])
    selected_states = [SimpleNamespace(state_index=index) for index in range(3)]
    states = iter(selected_states)

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )

    def fake_solve_fermion(*args, **kwargs):
        del args, kwargs
        energy = next(energies)
        occupancies = (np.array([0.9, 0.1]), np.array([0.8, 0.2]))
        return energy, next(states), occupancies, 0.0

    monkeypatch.setattr(fermion, "solve_fermion", fake_solve_fermion)

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 3,
            "samples_per_batch": 1,
            "num_batches": 1,
            "energy_tol": 1e-9,
            "occupancies_tol": 1e-9,
            "min_selected_configurations": 1,
        },
    )

    assert result.sci_energies == [-1.0, -1.2, -1.1]
    assert result.primary_energy == -1.2
    assert result.sci_result_package["final_energy"] == -1.1
    assert result.sci_result_package["best_energy"] == -1.2
    assert result.sci_result_package["best_iteration"] == 2
    assert result.sci_result_package["reported_energy_source"] == "best_observed_sqd_iteration"
    assert result.configuration_recovery_trace[-1]["best_iteration"] == 2
    assert result.best_sci_state is selected_states[1]


def test_run_sqd_passes_invalid_frequency_probabilities_to_recovery(monkeypatch) -> None:
    """Recovery receives only invalid rows and their raw probability mass."""
    configuration_recovery, fermion = _import_sqd_addon_modules()

    sampled = np.array(
        [
            [True, False],
            [True, False],
            [False, True],
            [True, False],
        ],
        dtype=bool,
    )
    captured_probabilities: list[np.ndarray] = []
    occupancies = (np.array([1.0]), np.array([0.0]))

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )

    def fake_recover(bitstrings, probabilities, **kwargs):
        del kwargs
        captured_probabilities.append(np.asarray(probabilities, dtype=float))
        return bitstrings, probabilities

    monkeypatch.setattr(configuration_recovery, "recover_configurations", fake_recover)
    monkeypatch.setattr(
        fermion,
        "solve_fermion",
        lambda *args, **kwargs: (0.0, None, occupancies, 0.0),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 2,
            "samples_per_batch": 4,
            "num_batches": 1,
            "min_selected_configurations": 1,
        },
    )

    assert captured_probabilities == [pytest.approx([0.75])]
    assert result.sci_result_package["final_bitstring_probabilities"]


def test_run_sqd_solves_raw_sector_before_recovering_invalid_rows_and_persists_stages(
    monkeypatch,
) -> None:
    """SQD must preserve valid rows and expose every sampling stage."""
    configuration_recovery, fermion = _import_sqd_addon_modules()

    valid = np.array([False, True, False, True], dtype=bool)
    invalid = np.array([True, True, False, True], dtype=bool)
    recovered = np.array([True, False, False, True], dtype=bool)
    samples = np.asarray([valid, valid, valid, invalid], dtype=bool)
    sample_calls = 0
    events: list[str] = []
    recovery_inputs: list[np.ndarray] = []
    solved_strings: list[tuple[list[int], list[int]]] = []
    occupancies = (np.array([0.8, 0.2]), np.array([0.7, 0.3]))

    def fake_sample(*args, **kwargs):
        nonlocal sample_calls
        del args
        sample_calls += 1
        ledger = kwargs["work_ledger"]
        ledger["sampler_run_attempts"] += 1
        ledger["sampler_successful_runs"] += 1
        ledger["sampler_requested_shots_total"] += kwargs["total_samples"]
        ledger["sampler_returned_raw_sample_rows"] += int(samples.shape[0])
        return samples

    monkeypatch.setattr(sqd_solver, "_sample_bitstring_matrix", fake_sample)

    def fake_recover(bitstrings, probabilities, **kwargs):
        del kwargs
        events.append("recover")
        recovery_inputs.append(np.asarray(bitstrings, dtype=bool).copy())
        assert np.asarray(probabilities, dtype=float) == pytest.approx([0.25])
        return np.asarray([recovered], dtype=bool), np.asarray([1.0])

    monkeypatch.setattr(configuration_recovery, "recover_configurations", fake_recover)

    def fake_subsample(selected_bits, selected_probs, **kwargs):
        del selected_probs, kwargs
        return [selected_bits]

    def fake_solve(ci_strings, *args, **kwargs):
        del args, kwargs
        events.append("solve")
        solved_strings.append((ci_strings[0].tolist(), ci_strings[1].tolist()))
        return -1.0, None, occupancies, 0.0

    monkeypatch.setattr(
        sqd_solver,
        "_import_sqd_dependencies",
        lambda: sqd_solver._SQDDependencies(
            recover_configurations=configuration_recovery.recover_configurations,
            postselect_by_hamming_right_and_left=fermion.postselect_by_hamming_right_and_left,
            solve_fermion=fake_solve,
            subsample=fake_subsample,
        ),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 2,
            "samples_per_batch": 4,
            "num_batches": 1,
            "max_dim": 2,
            "min_selected_configurations": 1,
        },
    )

    assert events == ["solve", "recover", "solve"]
    assert len(recovery_inputs) == 1
    np.testing.assert_array_equal(recovery_inputs[0], np.asarray([invalid], dtype=bool))
    assert sample_calls == 1
    assert solved_strings[0] == ([1], [1])
    assert solved_strings[1] == ([1, 2], [1, 2])

    first, second = result.configuration_recovery_trace
    assert first["first_solve_source"] == "raw_valid_sector"
    assert first["recovery_applied"] is False
    assert first["raw_valid_configurations"] == 1
    assert first["recovered_configurations"] == 0
    assert first["accepted_bitstring_distribution"][0]["bitstring"] == "0101"
    assert {row["bitstring"] for row in first["raw_bitstring_distribution"]} == {
        "0101",
        "1101",
    }
    assert second["recovery_applied"] is True
    assert second["raw_valid_configurations"] == 1
    assert second["recovered_configurations"] == 1
    assert second["recovered_bitstring_distribution"][0]["bitstring"] == "1001"
    assert second["selected_bitstring_distribution"]
    assert result.sci_result_package["final_sampling_stages"]["recovered"]
    assert result.sci_result_package["best_sampling_stages"]["raw"]
    assert len(result.sci_result_package["occupation_history"]) == 2
    assert result.sci_result_package["work_ledger"]["sampler_run_attempts"] == 1
    assert result.sci_result_package["work_ledger"]["sampler_requested_shots_total"] == 4
    assert first["raw_bitstring_distribution"] == second["raw_bitstring_distribution"]


def test_run_sqd_requires_raw_valid_sector_for_first_solve(monkeypatch) -> None:
    """Iteration one must fail instead of recovering without occupations."""
    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: np.asarray([[True, False]], dtype=bool),
    )
    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    with pytest.raises(ValueError, match="first iteration produced no raw valid-sector"):
        sqd_solver.run_sqd(
            hamiltonian=hamiltonian,
            backend=object(),
            config={
                "algorithm": "sqd",
                "max_iterations": 1,
                "samples_per_batch": 1,
                "num_batches": 1,
            },
        )


def test_run_sqd_reports_effective_seed_and_selection_floor(monkeypatch) -> None:
    configuration_recovery, fermion = _import_sqd_addon_modules()

    sampled = np.array(
        [
            [True, False],
            [False, True],
        ],
        dtype=bool,
    )
    occupancies = (np.array([0.5]), np.array([0.5]))

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "solve_fermion",
        lambda *args, **kwargs: (0.0, None, occupancies, 0.0),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 2,
            "samples_per_batch": 2,
            "num_batches": 1,
            "seed": 0,
            "min_selected_configurations": 2,
        },
    )

    assert result.subsampling_summary["seed"] == 0
    assert result.postselection_summary["min_selected_configurations"] == 2
    assert result.sci_result_package["seed"] == 0
    assert result.sci_result_package["min_selected_configurations"] == 2
    assert "symmetrized" not in result.spin_diagnostics


def test_run_sqd_uses_average_batch_occupancies_and_best_energy(monkeypatch) -> None:
    sampled = np.array(
        [
            [False, True, False, True],
            [True, False, True, False],
        ],
        dtype=bool,
    )
    batch_occupancies = iter(
        [
            (np.array([0.9, 0.1]), np.array([0.85, 0.15])),
            (np.array([0.1, 0.9]), np.array([0.2, 0.8])),
        ]
    )
    batch_energies = iter([-1.2, -0.8])
    selected_states = [SimpleNamespace(batch_index=index) for index in range(2)]
    states = iter(selected_states)
    effective_batch_sizes: list[int] = []

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )

    def fake_subsample(
        selected_bits,
        _selected_probs,
        samples_per_batch,
        num_batches,
        rand_seed,
    ):
        del rand_seed
        effective_batch_sizes.append(samples_per_batch)
        return [selected_bits[:samples_per_batch].copy() for _ in range(num_batches)]

    def fake_import_deps():
        return sqd_solver._SQDDependencies(
            recover_configurations=lambda bitstrings, probabilities, **kwargs: (
                bitstrings,
                probabilities,
            ),
            postselect_by_hamming_right_and_left=lambda bitstrings, probabilities, **kwargs: (
                bitstrings,
                probabilities,
            ),
            solve_fermion=lambda *args, **kwargs: (
                next(batch_energies),
                next(states),
                next(batch_occupancies),
                0.0,
            ),
            subsample=fake_subsample,
        )

    monkeypatch.setattr(sqd_solver, "_import_sqd_dependencies", fake_import_deps)

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
        num_spatial_orbitals=2,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 1,
            "samples_per_batch": 8,
            "num_batches": 2,
            "min_selected_configurations": 1,
            "max_dim": 1,
        },
    )

    assert result.primary_energy == pytest.approx(-1.2)
    assert result.sci_result_package["final_occupancies"] == pytest.approx(
        [0.5, 0.5, 0.525, 0.475]
    )
    assert result.sci_result_package["selected_ci"]["occupancies_source"] == "mean_over_batches"
    assert result.sci_result_package["selected_ci"]["best_batch"] == 1
    assert result.sci_result_package["selected_ci"]["selected_ci_dimension"] == 1
    assert result.sci_result_package["selected_ci"]["exact_sector_solve"] is False
    assert result.sci_result_package["selected_ci"]["selected_ci_regime"] == "partial_sector"
    assert result.sci_result_package["selected_ci"]["selected_determinant_count"] == 1
    assert result.configuration_recovery_trace[-1]["selected_ci_dimension"] == 1
    assert result.best_sci_state is selected_states[0]
    assert effective_batch_sizes == [2]
    trace = result.configuration_recovery_trace[-1]
    assert trace["requested_samples_per_batch"] == 8
    assert trace["effective_samples_per_batch"] == 2
    serialized_trace = normalize_result(result)["algorithm_metrics"][
        "configuration_recovery_trace"
    ][-1]
    assert serialized_trace["effective_samples_per_batch"] == 2


def test_run_sqd_carries_over_high_weight_ci_strings(monkeypatch) -> None:
    configuration_recovery, fermion = _import_sqd_addon_modules()

    first_sample = np.array(
        [
            [False, False, True, False, False, True],
            [False, False, True, False, False, True],
            [False, False, True, False, False, True],
            [False, True, False, False, True, False],
        ],
        dtype=bool,
    )
    second_sample = np.array(
        [
            [False, True, False, False, True, False],
            [False, True, False, False, True, False],
            [False, True, False, False, True, False],
            [True, False, False, True, False, False],
        ],
        dtype=bool,
    )
    sampled = iter([first_sample, second_sample])
    occupancies = (np.array([0.8, 0.1, 0.1]), np.array([0.8, 0.1, 0.1]))
    captured_ci_strings: list[tuple[list[int], list[int]]] = []

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: next(sampled),
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )

    def fake_solve_fermion(ci_strings, *args, **kwargs):
        del args, kwargs
        captured_ci_strings.append((ci_strings[0].tolist(), ci_strings[1].tolist()))
        iteration = len(captured_ci_strings)
        if iteration == 1:
            sci_state = SimpleNamespace(
                amplitudes=np.array([[0.85, 0.0], [0.0, 0.15]], dtype=float),
                ci_strs_a=np.array([1, 2], dtype=np.int64),
                ci_strs_b=np.array([1, 2], dtype=np.int64),
            )
            return -1.0, sci_state, occupancies, 0.0
        sci_state = SimpleNamespace(
            amplitudes=np.array([[1.0]], dtype=float),
            ci_strs_a=np.array([1], dtype=np.int64),
            ci_strs_b=np.array([1], dtype=np.int64),
        )
        return -0.9, sci_state, occupancies, 0.0

    monkeypatch.setattr(fermion, "solve_fermion", fake_solve_fermion)

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((3, 3), dtype=float),
        two_body_tensor=np.zeros((3, 3, 3, 3), dtype=float),
        constant=0.0,
        num_spatial_orbitals=3,
        num_electrons_alpha=1,
        num_electrons_beta=1,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 2,
            "samples_per_batch": 4,
            "num_batches": 1,
            "max_dim": 2,
            "carryover_threshold": 0.5,
        },
    )

    assert captured_ci_strings[0] == ([1, 2], [1, 2])
    assert captured_ci_strings[1] == ([1, 2], [1, 2])
    assert result.sci_result_package["carryover_threshold"] == pytest.approx(0.5)
    assert result.sci_result_package["selected_ci"]["carryover_strings_alpha"] == 1
    assert result.subsampling_summary["carryover_threshold"] == pytest.approx(0.5)


def test_run_sqd_rejects_open_shell_spin_symmetrization(monkeypatch) -> None:
    configuration_recovery, fermion = _import_sqd_addon_modules()

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: np.array([[True, False]], dtype=bool),
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "solve_fermion",
        lambda *args, **kwargs: (0.0, None, (np.array([1.0]), np.array([0.0])), 0.0),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    with pytest.raises(ValueError, match="equal alpha and beta electron counts"):
        sqd_solver.run_sqd(
            hamiltonian=hamiltonian,
            backend=object(),
            config={
                "algorithm": "sqd",
                "max_iterations": 1,
                "samples_per_batch": 1,
                "num_batches": 1,
                "symmetrize_spin": True,
            },
        )


def test_run_sqd_caps_selected_ci_strings_before_solving(monkeypatch) -> None:
    """SQD should not silently expand a sampled determinant pool into the full FCI sector."""
    configuration_recovery, fermion = _import_sqd_addon_modules()

    norb = 4
    sampled_rows: list[list[bool]] = []
    for left_occ in combinations(range(norb), 2):
        for right_occ in combinations(range(norb), 2):
            row = [False] * (2 * norb)
            for orbital in left_occ:
                row[orbital] = True
            for orbital in right_occ:
                row[norb + orbital] = True
            sampled_rows.append(row)
    sampled = np.asarray(sampled_rows, dtype=bool)
    captured_ci_shapes: list[tuple[int, int]] = []
    occupancies = (np.full(norb, 0.5), np.full(norb, 0.5))

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )

    def fake_solve_fermion(ci_strings, *args, **kwargs):
        del args, kwargs
        assert isinstance(ci_strings, tuple)
        captured_ci_shapes.append((len(ci_strings[0]), len(ci_strings[1])))
        return -1.0, None, occupancies, 0.0

    monkeypatch.setattr(fermion, "solve_fermion", fake_solve_fermion)

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((norb, norb), dtype=float),
        two_body_tensor=np.zeros((norb, norb, norb, norb), dtype=float),
        constant=0.0,
        num_spatial_orbitals=norb,
        num_electrons_alpha=2,
        num_electrons_beta=2,
    )

    result = sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 1,
            "samples_per_batch": 128,
            "num_batches": 1,
            "max_dim": 2,
        },
    )

    assert captured_ci_shapes == [(2, 2)]
    selected_ci = result.sci_result_package["selected_ci"]
    assert selected_ci["full_sci_dimension"] == 36
    assert selected_ci["max_sci_dimension"] == 4
    assert selected_ci["exact_sector_solve"] is False
    assert selected_ci["selected_ci_regime"] == "partial_sector"
    assert selected_ci["selected_fraction"] == pytest.approx(4 / 36)
    assert selected_ci["classical_diagonalization_dimension"] == 4


def test_run_sqd_emits_pre_solve_progress_events(monkeypatch) -> None:
    configuration_recovery, fermion = _import_sqd_addon_modules()

    sampled = np.array([[False, True], [False, True]], dtype=bool)
    occupancies = (np.array([1.0]), np.array([0.0]))
    events: list[dict[str, object]] = []

    monkeypatch.setattr(
        sqd_solver,
        "_sample_bitstring_matrix",
        lambda *args, **kwargs: sampled,
    )
    monkeypatch.setattr(
        configuration_recovery,
        "recover_configurations",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "postselect_by_hamming_right_and_left",
        lambda bitstrings, probabilities, **kwargs: (bitstrings, probabilities),
    )
    monkeypatch.setattr(
        fermion,
        "solve_fermion",
        lambda *args, **kwargs: (0.0, None, occupancies, 0.0),
    )

    hamiltonian = SimpleNamespace(
        one_body_tensor=np.zeros((1, 1), dtype=float),
        two_body_tensor=np.zeros((1, 1, 1, 1), dtype=float),
        constant=0.0,
        num_spatial_orbitals=1,
        num_electrons_alpha=1,
        num_electrons_beta=0,
    )

    sqd_solver.run_sqd(
        hamiltonian=hamiltonian,
        backend=object(),
        config={
            "algorithm": "sqd",
            "max_iterations": 1,
            "samples_per_batch": 2,
            "num_batches": 1,
        },
        progress_callback=events.append,
    )

    assert [event["step"] for event in events[:3]] == [
        "sampling",
        "postselection",
        "selected_ci_solve",
    ]
    assert events[0]["completed_iterations"] == 0
