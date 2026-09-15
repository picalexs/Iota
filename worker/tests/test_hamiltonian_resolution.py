"""Tests for Hamiltonian resolution failure behavior."""

from __future__ import annotations

import pytest

from worker.chemistry.algorithms.kqd.workflow import run_kqd
from worker.chemistry.algorithms.qfd.workflow import run_qfd
from worker.chemistry.algorithms.qse.workflow import run_qse
from worker.chemistry.algorithms.sqd.workflow import run_sqd
from worker.chemistry.algorithms.vqe.workflow import run_vqe
from worker.chemistry.eigensolver import resolve_operator_matrix
from worker.chemistry.skqd_solver import run_skqd


def test_resolve_operator_matrix_raises_for_unsupported_input() -> None:
    with pytest.raises(ValueError, match="Unable to resolve operator matrix"):
        resolve_operator_matrix(object())


def test_run_vqe_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="Unable to resolve VQE operator"):
        run_vqe(hamiltonian=object(), backend=object(), config={})


def test_run_kqd_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="Unable to resolve operator matrix"):
        run_kqd(
            hamiltonian=object(),
            backend=object(),
            config={"algorithm": "kqd"},
        )


def test_run_qfd_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="Unable to resolve operator matrix"):
        run_qfd(
            hamiltonian=object(),
            backend=object(),
            config={"algorithm": "qfd"},
        )


def test_run_qse_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="Unable to resolve operator matrix"):
        run_qse(
            hamiltonian=object(),
            backend=object(),
            config={"algorithm": "qse"},
        )


def test_run_skqd_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="Unable to resolve operator matrix"):
        run_skqd(
            hamiltonian=object(),
            backend=object(),
            config={"algorithm": "skqd"},
        )


def test_run_sqd_raises_for_unsupported_hamiltonian() -> None:
    with pytest.raises(ValueError, match="SQD requires HamiltonianBundle tensors"):
        run_sqd(
            hamiltonian=object(),
            backend=object(),
            config={"algorithm": "sqd"},
        )
