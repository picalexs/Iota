"""Ownership checks for extracted validation policy modules."""

from app.services import validation_service
from app.services.validation import (
    algorithm_policies,
    backend_policies,
    config_alignment,
    molecule_policies,
)


def test_config_alignment_helpers_have_a_single_owner() -> None:
    assert (
        validation_service._append_mode_validation_messages
        is config_alignment._append_mode_validation_messages
    )
    assert (
        validation_service._append_advanced_config_alignment_messages
        is config_alignment._append_advanced_config_alignment_messages
    )


def test_algorithm_helpers_have_a_single_owner() -> None:
    helper_names = (
        "_append_kqd_validation_messages",
        "_append_qse_execution_validation_messages",
        "_append_qse_runtime_path_warning",
        "_append_skqd_validation_messages",
        "_append_sqd_validation_messages",
        "_append_vqe_validation_messages",
    )

    assert all(
        getattr(validation_service, name) is getattr(algorithm_policies, name)
        for name in helper_names
    )


def test_backend_helpers_have_a_single_owner() -> None:
    helper_names = (
        "_append_aer_matrix_validation_messages",
        "_append_backend_credential_validation_messages",
        "_append_backend_target_validation_messages",
        "_append_basis_set_validation_messages",
        "_append_ibm_runtime_validation_messages",
        "_append_projected_matrix_validation_messages",
    )

    assert all(
        getattr(validation_service, name) is getattr(backend_policies, name)
        for name in helper_names
    )


def test_molecule_guardrails_have_a_single_owner() -> None:
    assert (
        validation_service._append_molecule_guardrail_messages
        is molecule_policies._append_molecule_guardrail_messages
    )
