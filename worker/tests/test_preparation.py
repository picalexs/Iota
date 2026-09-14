"""Focused tests for the worker backend and Hamiltonian preparation seam."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from worker.adapters.base import BackendExecutionContext
from worker.chemistry.types import ChemistryInput
from worker.jobs.execution_context import StartedRunContext
from worker.jobs.preparation import prepare_backend_and_hamiltonian


def _started_context() -> StartedRunContext:
    return StartedRunContext(
        expected_generation=4,
        algorithm="vqe",
        mode="easy",
        backend_target="statevector",
        config_snapshot={"algorithm": "vqe"},
        algorithm_config={"max_iterations": 3},
        backend_options_runtime={},
        chemistry_input=ChemistryInput(
            atoms=["H", "H"],
            coordinates=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.7]],
            active_space=(2, 2),
        ),
        eta_seed_seconds_per_iteration=None,
        eta_seed_confidence=None,
    )


def _session_context() -> tuple[MagicMock, object]:
    session = object()
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = False
    return context, session


def test_preparation_keeps_backend_and_chemistry_setup_order() -> None:
    started = _started_context()
    context, session = _session_context()
    order: list[str] = []
    backend_context = BackendExecutionContext(backend_target="statevector")
    backend_adapter = MagicMock()
    backend_adapter.execution_metadata.return_value = {"adapter": "statevector"}
    hamiltonian_bundle = SimpleNamespace(
        num_qubits=4,
        num_spatial_orbitals=2,
        metadata={"active_space": [2, 2], "pipeline": "test"},
    )
    progress_state: dict[str, object] = {}

    def build_backend_context(**_: object) -> BackendExecutionContext:
        order.append("backend_context")
        return backend_context

    def select_backend(_: str) -> MagicMock:
        order.append("backend_adapter")
        return backend_adapter

    def build_hamiltonian_bundle(**_: object) -> SimpleNamespace:
        order.append("hamiltonian")
        return hamiltonian_bundle

    def emit_setup_milestone(_: str, **kwargs: object) -> None:
        order.append(str(kwargs["stage"]))

    def handle_setup_control_state(*_: object, **__: object) -> None:
        order.append("control")
        return None

    def insert_event(actual_session: object, *_: object) -> None:
        if actual_session is session:
            order.append("setup_event")

    prepared, early_result = prepare_backend_and_hamiltonian(
        run_id_str="run-1",
        started=started,
        progress_state=progress_state,
        run_wall_start=0.0,
        build_backend_context=build_backend_context,
        select_backend=select_backend,
        build_hamiltonian_bundle=build_hamiltonian_bundle,
        emit_setup_milestone=emit_setup_milestone,
        handle_setup_control_state=handle_setup_control_state,
        build_hamiltonian_message=lambda _: "Building Hamiltonian",
        active_space_payload=lambda _: {"n_electrons": 2, "n_orbitals": 2},
        merge_backend_metadata=lambda **_: {"adapter": "statevector"},
        build_setup_payload=lambda **_: {"stage": "setup"},
        session_factory=lambda: context,
        insert_run_event=insert_event,
    )

    assert early_result is None
    assert prepared is not None
    assert prepared.backend_adapter is backend_adapter
    assert prepared.backend_context is backend_context
    assert prepared.hamiltonian_bundle is hamiltonian_bundle
    timing_components = progress_state["timing_components"]
    assert isinstance(timing_components, dict)
    assert timing_components["backend_setup_seconds"] >= 0.0
    assert timing_components["hamiltonian_preparation_seconds"] >= 0.0
    assert order == [
        "backend_context",
        "backend_adapter",
        "backend_selected",
        "hamiltonian_building",
        "hamiltonian",
        "control",
        "setup_event",
    ]


def test_preparation_returns_setup_control_result_without_setup_event() -> None:
    started = _started_context()
    context, _ = _session_context()
    stopped = {"status": "CANCELLED"}
    insert_run_event = MagicMock()

    prepared, early_result = prepare_backend_and_hamiltonian(
        run_id_str="run-1",
        started=started,
        progress_state={},
        run_wall_start=0.0,
        build_backend_context=lambda **_: BackendExecutionContext(backend_target="statevector"),
        select_backend=lambda _: MagicMock(execution_metadata=lambda _: {}),
        build_hamiltonian_bundle=lambda **_: SimpleNamespace(
            num_qubits=4,
            num_spatial_orbitals=2,
            metadata={},
        ),
        emit_setup_milestone=lambda *_args, **_kwargs: None,
        handle_setup_control_state=lambda *_args, **_kwargs: stopped,
        build_hamiltonian_message=lambda _: "Building Hamiltonian",
        active_space_payload=lambda _: None,
        merge_backend_metadata=lambda **_: {},
        build_setup_payload=lambda **_: {},
        session_factory=lambda: context,
        insert_run_event=insert_run_event,
    )

    assert prepared is None
    assert early_result is stopped
    insert_run_event.assert_not_called()
