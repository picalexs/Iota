"""Backend and Hamiltonian preparation for the ordered worker run story."""

from __future__ import annotations

import logging
import time
from typing import Any

from .run_execution.contracts import (
    EventInserter,
    PreparedRunContext,
    SessionFactory,
    StartedRunContext,
)

logger = logging.getLogger(__name__)


def prepare_backend_and_hamiltonian(
    *,
    run_id_str: str,
    started: StartedRunContext,
    progress_state: dict[str, Any],
    run_wall_start: float,
    session_factory: SessionFactory,
    insert_run_event: EventInserter,
    **setup_dependencies: Any,
) -> tuple[PreparedRunContext | None, dict[str, Any] | None]:
    """Prepare backend and chemistry artifacts before algorithm dispatch.

    The callbacks keep the compatibility facade's existing patch points
    injectable while this module owns the ordered setup story and its timing.
    """
    build_backend_context = setup_dependencies["build_backend_context"]
    select_backend = setup_dependencies["select_backend"]
    build_hamiltonian_bundle = setup_dependencies["build_hamiltonian_bundle"]
    emit_setup_milestone = setup_dependencies["emit_setup_milestone"]
    handle_setup_control_state = setup_dependencies["handle_setup_control_state"]
    build_hamiltonian_message = setup_dependencies["build_hamiltonian_message"]
    active_space_payload = setup_dependencies["active_space_payload"]
    merge_backend_metadata = setup_dependencies["merge_backend_metadata"]
    build_setup_payload = setup_dependencies["build_setup_payload"]
    t_backend = time.monotonic()
    backend_context = build_backend_context(
        run_id_str=run_id_str,
        backend_target=started.backend_target,
        backend_options_runtime=started.backend_options_runtime,
        config_snapshot=started.config_snapshot,
        run_wall_start=run_wall_start,
    )
    backend_adapter = select_backend(started.backend_target)
    setup_message = (
        f"Selected {backend_context.backend_target} backend; building molecular Hamiltonian next."
    )
    logger.info("Run %s: %s", run_id_str, setup_message)
    emit_setup_milestone(
        run_id_str,
        stage="backend_selected",
        algorithm=started.algorithm,
        mode=started.mode,
        backend_target=backend_context.backend_target,
        message=setup_message,
        extra=merge_backend_metadata(
            algorithm=started.algorithm,
            adapter_metadata=backend_adapter.execution_metadata(backend_context),
            backend_context=backend_context,
            provisional=True,
        ),
    )
    logger.info(
        "Run %s: backend selected target=%s elapsed=%.3fs",
        run_id_str,
        started.backend_target,
        time.monotonic() - t_backend,
    )
    progress_state.setdefault("timing_components", {})[
        "backend_setup_seconds"
    ] = time.monotonic() - t_backend

    t_hamiltonian = time.monotonic()
    hamiltonian_message = build_hamiltonian_message(started.chemistry_input)
    logger.info("Run %s: %s", run_id_str, hamiltonian_message)
    emit_setup_milestone(
        run_id_str,
        stage="hamiltonian_building",
        algorithm=started.algorithm,
        mode=started.mode,
        backend_target=backend_context.backend_target,
        message=hamiltonian_message,
        extra={
            "active_space": active_space_payload(started.chemistry_input.active_space),
            "basis": started.chemistry_input.basis,
            "charge": started.chemistry_input.charge,
            "multiplicity": started.chemistry_input.multiplicity,
        },
    )
    hamiltonian_bundle = build_hamiltonian_bundle(
        chemistry_input=started.chemistry_input,
        chemistry_options=started.chemistry_options_runtime or {},
    )
    for key in (
        "reference_device_actual",
        "reference_provider",
        "reference_gpu_fallback_reason",
        "scf_device",
        "casci_device",
        "reference_scf_seconds",
        "casci_seconds",
        "pauli_build_seconds",
        "hamiltonian_total_seconds",
        "reference_transfer_seconds",
    ):
        if key in hamiltonian_bundle.metadata:
            backend_context.resource_metadata[key] = hamiltonian_bundle.metadata[key]
    logger.info(
        "Run %s: hamiltonian built num_qubits=%d num_spatial_orbitals=%d "
        "active_space=%s pipeline=%s elapsed=%.3fs",
        run_id_str,
        hamiltonian_bundle.num_qubits,
        hamiltonian_bundle.num_spatial_orbitals,
        hamiltonian_bundle.metadata.get("active_space"),
        hamiltonian_bundle.metadata.get("pipeline"),
        time.monotonic() - t_hamiltonian,
    )
    progress_state.setdefault("timing_components", {})[
        "hamiltonian_preparation_seconds"
    ] = time.monotonic() - t_hamiltonian
    if hamiltonian_bundle.metadata.get("active_space_auto_reduced"):
        logger.warning(
            "Run %s: active space was auto-reduced from %s orbitals to %s orbitals",
            run_id_str,
            hamiltonian_bundle.metadata.get("original_num_orbitals"),
            hamiltonian_bundle.num_spatial_orbitals,
        )

    with session_factory() as session:
        setup_result = handle_setup_control_state(
            session,
            run_id=run_id_str,
            execution_generation=started.expected_generation,
            algorithm=started.algorithm,
            progress_state=progress_state,
            config_snapshot=started.config_snapshot,
            hamiltonian_bundle=hamiltonian_bundle,
        )
        if setup_result is not None:
            return None, setup_result

        setup_payload = build_setup_payload(
            algorithm=started.algorithm,
            mode=started.mode,
            backend_context=backend_context,
            backend_adapter=backend_adapter,
            hamiltonian_bundle=hamiltonian_bundle,
        )
        insert_run_event(session, run_id_str, "iteration_update", setup_payload)

    return PreparedRunContext(backend_adapter, backend_context, hamiltonian_bundle), None


__all__ = ["prepare_backend_and_hamiltonian"]
