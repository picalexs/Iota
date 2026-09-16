"""Unit coverage for shared estimation and credential helper modules."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

ESTIMATION_MODULE = "shared.estimation"
CREDENTIAL_CRYPTO_MODULE = "shared.credential_crypto"
LOCAL_OPERATOR_AUTH_MODULE = "shared.local_operator_auth"


def test_bounded_positive_int_defaults_and_clamps() -> None:
    bounded_positive_int = import_module(ESTIMATION_MODULE).bounded_positive_int

    assert bounded_positive_int(None, default=3) == 3
    assert bounded_positive_int(True, default=3) == 3
    assert bounded_positive_int(-1, default=3) == 3
    assert bounded_positive_int(9, default=3, high=5) == 5
    assert bounded_positive_int(0, default=0, high=5) == 1


def test_estimate_vqe_parameter_count_respects_ansatz_name_and_bounds() -> None:
    estimate_vqe_parameter_count = import_module(ESTIMATION_MODULE).estimate_vqe_parameter_count

    assert estimate_vqe_parameter_count(config_payload={"reps": 2}, num_qubits=None) is None
    assert estimate_vqe_parameter_count(config_payload={"reps": 2}, num_qubits=0) is None
    assert (
        estimate_vqe_parameter_count(
            config_payload={"ansatz_name": "Real-Amplitudes", "reps": 3},
            num_qubits=4,
        )
        == 16
    )
    assert (
        estimate_vqe_parameter_count(
            config_payload={"ansatz_name": "TwoLocal", "reps": 10},
            num_qubits=3,
        )
        == 42
    )


def test_vqe_candidate_evaluations_handle_explicit_points_and_clamped_candidates() -> None:
    estimation = import_module(ESTIMATION_MODULE)
    vqe_candidate_evaluations = estimation.vqe_candidate_evaluations
    max_candidates = estimation.MAX_VQE_INITIAL_POINT_CANDIDATES

    assert vqe_candidate_evaluations({"initial_parameters": [0.1, 0.2]}) == 0
    assert vqe_candidate_evaluations({"initial_point": [0.1, 0.2]}) == 0
    assert vqe_candidate_evaluations({"initial_point_strategy": "custom"}) == 0
    assert (
        vqe_candidate_evaluations(
            {
                "initial_point_strategy": "zero_plus_seeded_random",
                "initial_point_candidates": max_candidates + 10,
            }
        )
        == max_candidates
    )


def test_estimate_total_iterations_covers_algorithm_specific_paths() -> None:
    estimate_total_iterations = import_module(ESTIMATION_MODULE).estimate_total_iterations

    assert (
        estimate_total_iterations(
            algorithm="vqe",
            config_payload={
                "advanced_config": {
                    "algorithm": "vqe",
                    "optimizer_options": {"maxfun": 77},
                }
            },
            num_qubits=4,
        )
        == 77
    )
    assert (
        estimate_total_iterations(
            algorithm="vqe",
            config_payload={
                "algorithm": "vqe",
                "optimizer_name": "SLSQP",
                "max_iterations": 10,
                "reps": 1,
            },
            num_qubits=4,
        )
        == 308
    )
    assert estimate_total_iterations(algorithm="sqd", config_payload={}) == 100
    assert estimate_total_iterations(algorithm="kqd", config_payload={}) == 16
    assert estimate_total_iterations(algorithm="qfd", config_payload={}) == 32
    assert (
        estimate_total_iterations(
            algorithm="qse",
            config_payload={"algorithm": "qse", "reference_method": "hf", "max_subspace_dim": 12},
        )
        == 12
    )
    assert (
        estimate_total_iterations(
            algorithm="skqd",
            config_payload={
                "algorithm": "skqd",
                "base_sampling_options": {"max_iterations": 45},
                "krylov_extension_dim": 7,
            },
        )
        == 7
    )
    assert (
        estimate_total_iterations(
            algorithm="kqd",
            config_payload={"algorithm": "kqd", "krylov_dim": 8},
            backend_target="aer_simulator",
        )
        == 8
    )
    assert (
        estimate_total_iterations(
            algorithm="kqd",
            config_payload={"algorithm": "kqd", "krylov_dim": 8},
            backend_target="aer_simulator",
            noise_profile_enabled=True,
        )
        == 44
    )
    assert (
        estimate_total_iterations(
            algorithm="kqd",
            config_payload={"algorithm": "kqd", "krylov_dim": 8},
            backend_target="ibm_runtime",
        )
        == 44
    )
    assert estimate_total_iterations(algorithm="unknown", config_payload={}) == 1


def test_estimate_total_iterations_covers_qse_reference_vqe_path() -> None:
    estimate_total_iterations = import_module(ESTIMATION_MODULE).estimate_total_iterations

    assert (
        estimate_total_iterations(
            algorithm="qse",
            config_payload={
                "algorithm": "qse",
                "reference_method": "vqe",
                "max_subspace_dim": 12,
                "vqe_reference_optimizer_name": "SLSQP",
                "vqe_reference_max_iterations": 10,
                "vqe_reference_reps": 1,
            },
            num_qubits=4,
        )
        == 320
    )


def test_estimate_total_iterations_uses_outer_vqe_config_when_nested_algorithm_differs() -> None:
    estimate_total_iterations = import_module(ESTIMATION_MODULE).estimate_total_iterations

    assert (
        estimate_total_iterations(
            algorithm="vqe",
            config_payload={
                "advanced_config": {
                    "algorithm": "qse",
                    "max_subspace_dim": 99,
                },
                "optimizer_name": "SPSA",
                "max_iterations": 10,
                "reps": 1,
            },
            num_qubits=4,
        )
        == 58
    )


def test_get_credential_cipher_uses_env_keys_and_masks_secrets(monkeypatch) -> None:
    credential_crypto = import_module(CREDENTIAL_CRYPTO_MODULE)

    key_a = Fernet.generate_key().decode("ascii")
    key_b = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("LOCAL_CREDENTIALS_KEYS", f"{key_a}, {key_b}")

    cipher = credential_crypto.get_credential_cipher()

    encrypted = cipher.encrypt("super-secret-token")
    assert cipher.decrypt(encrypted) == "super-secret-token"
    assert cipher.status.key_source == "LOCAL_CREDENTIALS_KEYS"
    assert cipher.rotate(encrypted) != ""
    assert credential_crypto.mask_secret("  abcdefghijkl  ") == "abcd...ijkl"
    assert credential_crypto.mask_secret("tiny", prefix=3, suffix=3) == "****"
    assert credential_crypto.mask_secret("   ") == ""


def test_get_credential_cipher_wraps_invalid_env_and_key_file_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    credential_crypto = import_module(CREDENTIAL_CRYPTO_MODULE)

    monkeypatch.setenv("LOCAL_CREDENTIALS_KEYS", "not-a-valid-fernet-key")
    with pytest.raises(credential_crypto.CredentialCipherError):
        credential_crypto.get_credential_cipher()

    monkeypatch.delenv("LOCAL_CREDENTIALS_KEYS", raising=False)
    bad_target = tmp_path / "target.key"
    bad_target.write_text("real-key", encoding="utf-8")
    bad_link = tmp_path / "cipher.key"
    bad_link.symlink_to(bad_target)
    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(bad_link))
    with pytest.raises(credential_crypto.CredentialCipherError):
        credential_crypto.get_credential_cipher()


def test_get_credential_cipher_file_mode_reports_warning_and_decrypt_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    credential_crypto = import_module(CREDENTIAL_CRYPTO_MODULE)

    monkeypatch.delenv("LOCAL_CREDENTIALS_KEYS", raising=False)
    key_file = tmp_path / "credential.key"
    monkeypatch.setenv("LOCAL_CREDENTIALS_KEY_FILE", str(key_file))

    cipher = credential_crypto.get_credential_cipher()

    assert cipher.status.key_source == str(key_file)
    assert cipher.status.generated_key_file is True
    assert cipher.status.warning is not None
    with pytest.raises(credential_crypto.CredentialCipherError):
        cipher.decrypt("not-a-token")
    with pytest.raises(credential_crypto.CredentialCipherError):
        cipher.rotate("not-a-token")


def test_local_operator_auth_supports_env_and_generated_file(monkeypatch, tmp_path: Path) -> None:
    local_operator_auth = import_module(LOCAL_OPERATOR_AUTH_MODULE)

    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN", "env-token")
    auth = local_operator_auth.get_local_operator_auth()
    assert auth.token == "env-token"
    assert auth.status.token_source == "LOCAL_OPERATOR_TOKEN"
    assert local_operator_auth.get_local_operator_header_name() == "X-Local-Operator-Token"

    monkeypatch.delenv("LOCAL_OPERATOR_TOKEN", raising=False)
    token_file = tmp_path / "operator.token"
    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN_FILE", str(token_file))
    file_auth = local_operator_auth.get_local_operator_auth()
    assert file_auth.status.token_source == str(token_file)
    assert file_auth.status.generated_token_file is True
    assert file_auth.status.warning is not None
    assert file_auth.token


def test_local_operator_auth_wraps_secret_file_failures(monkeypatch, tmp_path: Path) -> None:
    local_operator_auth = import_module(LOCAL_OPERATOR_AUTH_MODULE)

    bad_target = tmp_path / "target.token"
    bad_target.write_text("real-token", encoding="utf-8")
    bad_link = tmp_path / "operator.token"
    bad_link.symlink_to(bad_target)
    monkeypatch.delenv("LOCAL_OPERATOR_TOKEN", raising=False)
    monkeypatch.setenv("LOCAL_OPERATOR_TOKEN_FILE", str(bad_link))

    with pytest.raises(local_operator_auth.LocalOperatorAuthError):
        local_operator_auth.get_local_operator_auth()
