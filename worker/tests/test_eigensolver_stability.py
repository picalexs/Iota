from __future__ import annotations

import numpy as np
import pytest

from worker.chemistry.eigensolver import (
    solve_exact_generalized_eigenproblem,
    solve_generalized_eigenproblem,
    solve_stabilized_generalized_eigenproblem,
)


def test_exact_generalized_eigenproblem_drops_duplicate_metric_modes() -> None:
    eigenvalues, diagnostics = solve_exact_generalized_eigenproblem(
        np.diag([-1.0, -0.5]).astype(complex),
        np.asarray([[1.0, 1.0], [1.0, 1.0]], dtype=complex),
    )

    assert eigenvalues == pytest.approx([-0.375])
    assert diagnostics["retained_rank"] == 1
    assert diagnostics["dropped_rank"] == 1
    assert diagnostics["stability_state"] == "stabilized"
    assert diagnostics["regularization"] == pytest.approx(0.0)


def test_exact_generalized_eigenproblem_keeps_full_rank_metric_stable() -> None:
    eigenvalues, diagnostics = solve_exact_generalized_eigenproblem(
        np.diag([-1.0, 0.5]).astype(complex),
        np.eye(2, dtype=complex),
    )

    assert eigenvalues == pytest.approx([-1.0, 0.5])
    assert diagnostics["retained_rank"] == 2
    assert diagnostics["dropped_rank"] == 0
    assert diagnostics["stability_state"] == "stable"


def test_exact_metric_condition_is_finite_for_small_nonzero_retained_mode() -> None:
    eigenvalues, diagnostics = solve_exact_generalized_eigenproblem(
        np.diag([-1.0, 0.5]).astype(complex),
        np.diag([1.0, 1e-9]).astype(complex),
    )

    assert eigenvalues == pytest.approx([-1.0, 5e8])
    assert diagnostics["overlap_condition"] == pytest.approx(1e9)
    assert np.isfinite(diagnostics["overlap_condition"])


def test_generalized_eigenproblem_does_not_hide_singular_overlap_with_regularization() -> None:
    _, diagnostics = solve_generalized_eigenproblem(
        np.diag([-1.0, -0.5]).astype(complex),
        np.array([[1.0, 1.0], [1.0, 1.0]], dtype=complex),
    )

    assert diagnostics["stability_state"] == "invalid"
    assert diagnostics["overlap_condition"] == pytest.approx(float("inf"))
    assert diagnostics["overlap_min_eigenvalue"] == pytest.approx(0.0)


def test_stabilized_generalized_eigenproblem_projects_negative_overlap_modes() -> None:
    result = solve_stabilized_generalized_eigenproblem(
        np.diag([-1.0, 0.5]).astype(complex),
        np.diag([1.0, -0.2]).astype(complex),
        max_standard_error=1e-2,
    )

    assert result.eigenvalues == pytest.approx([-1.0])
    assert result.raw_eigenvalues.size == 2
    assert result.diagnostics["stability_state"] == "stabilized"
    assert result.diagnostics["raw_spectrum_definition"] == (
        "regularized_unfiltered_generalized_spectrum"
    )
    assert result.diagnostics["psd_projected"] is True
    assert result.diagnostics["raw_projected_rank"] == 2
    assert result.diagnostics["retained_rank"] == 1
    assert result.diagnostics["stabilized_projected_rank"] == 1
    assert result.diagnostics["dropped_rank"] == 1
    assert result.diagnostics["stabilized_overlap_condition"] == pytest.approx(1.0)


def test_stabilized_generalized_eigenproblem_truncates_noisy_small_overlap_modes() -> None:
    result = solve_stabilized_generalized_eigenproblem(
        np.diag([-1.0, -0.5]).astype(complex),
        np.diag([1.0, 1e-5]).astype(complex),
        max_standard_error=1e-4,
    )

    assert result.eigenvalues == pytest.approx([-1.0])
    assert result.diagnostics["stability_state"] == "stabilized"
    assert result.diagnostics["retained_rank"] == 1
    assert result.diagnostics["threshold"] == pytest.approx(1e-3)
    assert result.diagnostics["overlap_uncertainty_cutoff_method"] == (
        "four_times_max_overlap_entry_standard_error_heuristic"
    )
    assert result.diagnostics["overlap_uncertainty_is_matrix_level_bound"] is False


def test_stabilized_generalized_eigenproblem_records_projected_ritz_residual() -> None:
    result = solve_stabilized_generalized_eigenproblem(
        np.diag([-1.0, 0.5]).astype(complex),
        np.eye(2, dtype=complex),
    )

    assert result.diagnostics["projected_ritz_residual_norm"] == pytest.approx(0.0)
    assert result.diagnostics["relative_projected_ritz_residual"] == pytest.approx(0.0)
    assert result.diagnostics["stabilized_ritz_residual_norm"] == pytest.approx(0.0)
    assert result.diagnostics["stabilized_relative_ritz_residual"] == pytest.approx(0.0)


def test_stabilized_generalized_eigenproblem_caps_retained_condition_on_noisy_h2_example() -> None:
    noisy_hamiltonian = np.array(
        [
            [
                -1.1162568536566981 + 0.0j,
                -1.1115012862949976 - 0.1021714526095188j,
                -1.0978070625495162 - 0.2034804590910007j,
                -1.0751542836594208 - 0.3030692929461712j,
                -1.0440585045362107 - 0.4003087853372077j,
                -1.0042771016582774 - 0.4941624929582062j,
                -0.9564053153909614 - 0.5839851775949453j,
                -0.9004521183305597 - 0.6686860305046934j,
            ],
            [
                -1.1115012862949976 + 0.1021714526095188j,
                -1.1130421584849317 + 0.0j,
                -1.1102683936971245 - 0.1019639784271117j,
                -1.0954939379680366 - 0.2028668662414684j,
                -1.074104091356185 + -0.302485910994031j,
                -1.0438049783802203 - 0.3996973553788845j,
                -1.0050966973547226 - 0.4939039612234019j,
                -0.9561696020758386 - 0.5828568591329707j,
            ],
            [
                -1.0978070625495162 + 0.2034804590910007j,
                -1.1102683936971245 + 0.1019639784271117j,
                -1.1155094250620856 + 0.0j,
                -1.110956457264533 - 0.1019351575091273j,
                -1.097618155329444 - 0.2031244453968558j,
                -1.075220755974466 - 0.302437382760838j,
                -1.0444711505589672 - 0.3993600059533657j,
                -1.0056187797962692 - 0.4932959144715767j,
            ],
            [
                -1.0751542836594208 + 0.3030692929461712j,
                -1.0954939379680366 + 0.2028668662414684j,
                -1.110956457264533 + 0.1019351575091273j,
                -1.1165896663224817 + 0.0j,
                -1.1132034379941949 - 0.10200079910526j,
                -1.0991218817526696 - 0.203051834256982j,
                -1.0770659060250345 - 0.3025479605100991j,
                -1.0460743013241889 - 0.3993638674782788j,
            ],
            [
                -1.0440585045362107 + 0.4003087853372077j,
                -1.074104091356185 + 0.302485910994031j,
                -1.097618155329444 + 0.2031244453968558j,
                -1.1132034379941949 + 0.10200079910526j,
                -1.1158040582833553 + 0.0j,
                -1.1136250957576808 - 0.1018444023749791j,
                -1.1002882557544285 - 0.2029541225634427j,
                -1.0788732486907198 - 0.3024030854927456j,
            ],
            [
                -1.0042771016582774 + 0.4941624929582062j,
                -1.0438049783802203 + 0.3996973553788845j,
                -1.075220755974466 + 0.302437382760838j,
                -1.0991218817526696 + 0.203051834256982j,
                -1.1136250957576808 + 0.1018444023749791j,
                -1.117150673683462 + 0.0j,
                -1.1156736796265163 - 0.1019133924491312j,
                -1.101766193190215 - 0.2027247077699888j,
            ],
            [
                -0.9564053153909614 + 0.5839851775949453j,
                -1.0050966973547226 + 0.4939039612234019j,
                -1.0444711505589672 + 0.3993600059533657j,
                -1.0770659060250345 + 0.3025479605100991j,
                -1.1002882557544285 + 0.2029541225634427j,
                -1.1156736796265163 + 0.1019133924491312j,
                -1.1200901149776439 + 0.0j,
                -1.116074721483332 - 0.1017139815379585j,
            ],
            [
                -0.9004521183305597 + 0.6686860305046934j,
                -0.9561696020758386 + 0.5828568591329707j,
                -1.0056187797962692 + 0.4932959144715767j,
                -1.0460743013241889 + 0.3993638674782788j,
                -1.0788732486907198 + 0.3024030854927456j,
                -1.101766193190215 + 0.2027247077699888j,
                -1.116074721483332 + 0.1017139815379585j,
                -1.1210258675518563 + 0.0j,
            ],
        ],
        dtype=complex,
    )
    noisy_overlap = np.array(
        [
            [
                1.0000000000000002 + 0.0j,
                0.9959096222125317 + 0.0891809486004067j,
                0.9836742510313082 + 0.1776074271237607j,
                0.9634011470646262 + 0.2645293309165916j,
                0.935238361636071 + 0.3493255296273391j,
                0.899448079745101 + 0.4311651641463872j,
                0.8563190361378897 + 0.5093971962306183j,
                0.8062798165329847 + 0.5832884878441706j,
            ],
            [
                0.9959096222125317 - 0.0891809486004067j,
                0.9980458157208106 + 0.0j,
                0.9951861433330184 + 0.0889848098617932j,
                0.9815295907662898 + 0.177041016566384j,
                0.9617714436822108 + 0.2638904466945913j,
                0.9346142348390629 + 0.3487347635319273j,
                0.8992795960563185 + 0.4307056897418022j,
                0.8551625395430049 + 0.5081484742434652j,
            ],
            [
                0.9836742510313082 - 0.1776074271237607j,
                0.9951861433330184 - 0.0889848098617932j,
                0.9990212939768552 + 0.0j,
                0.9949430712966183 + 0.0889119214625535j,
                0.9819985418172525 + 0.1771578979018201j,
                0.9620243686083416 + 0.2637874706527532j,
                0.9341874775149688 + 0.3482395121091285j,
                0.8989195424932458 + 0.4300803670439989j,
            ],
            [
                0.9634011470646262 - 0.2645293309165916j,
                0.9815295907662898 - 0.177041016566384j,
                0.9949430712966183 - 0.0889119214625535j,
                0.9987749975176672 + 0.0j,
                0.9959093147239865 + 0.0888878479110337j,
                0.9827346635719155 + 0.1770122775484169j,
                0.9622596727391219 + 0.2637236185350083j,
                0.9341949827050776 + 0.3480613155368358j,
            ],
            [
                0.935238361636071 - 0.3493255296273391j,
                0.9617714436822108 - 0.2638904466945913j,
                0.9819985418172525 - 0.1771578979018201j,
                0.9959093147239865 - 0.0888878479110337j,
                0.9977872198356833 + 0.0j,
                0.9956664488356969 + 0.088688763352112j,
                0.9825005622931079 + 0.1768376181420404j,
                0.9630139481213029 + 0.2634761284818732j,
            ],
            [
                0.899448079745101 - 0.4311651641463872j,
                0.9346142348390629 - 0.3487347635319273j,
                0.9620243686083416 - 0.2637874706527532j,
                0.9827346635719155 - 0.1770122775484169j,
                0.9956664488356969 - 0.088688763352112j,
                0.9975369689437925 + 0.0j,
                0.9954193380828283 + 0.0887150681494835j,
                0.9829849079240935 + 0.176476811700035j,
            ],
            [
                0.8563190361378897 - 0.5093971962306183j,
                0.8992795960563185 - 0.4307056897418022j,
                0.9341874775149688 - 0.3482395121091285j,
                0.9622596727391219 - 0.2637236185350083j,
                0.9825005622931079 - 0.1768376181420404j,
                0.9954193380828283 - 0.0887150681494835j,
                0.9992062853256588 + 0.0j,
                0.9944309311491812 + 0.0884348769623604j,
            ],
            [
                0.8062798165329847 - 0.5832884878441706j,
                0.8551625395430049 - 0.5081484742434652j,
                0.8989195424932458 - 0.4300803670439989j,
                0.9341949827050776 - 0.3480613155368358j,
                0.9630139481213029 - 0.2634761284818732j,
                0.9829849079240935 - 0.176476811700035j,
                0.9944309311491812 - 0.0884348769623604j,
                0.9984994596446758 + 0.0j,
            ],
        ],
        dtype=complex,
    )

    baseline = solve_stabilized_generalized_eigenproblem(
        noisy_hamiltonian,
        noisy_overlap,
        regularization=1e-8,
        max_standard_error=0.0,
    )

    assert baseline.eigenvalues[0] == pytest.approx(-1.136258405257436)
    assert baseline.raw_eigenvalues[0] < baseline.eigenvalues[0] - 0.5
    assert baseline.diagnostics["raw_spectrum_definition"] == (
        "regularized_unfiltered_generalized_spectrum"
    )
    assert baseline.diagnostics["stability_state"] == "stabilized"
    assert baseline.diagnostics["retained_rank"] == 2
    assert baseline.diagnostics["dropped_rank"] == 6
    assert baseline.diagnostics["threshold"] == pytest.approx(0.00798428455849085)
    assert baseline.diagnostics["overlap_condition"] < 1e3


def test_stabilized_generalized_eigenproblem_rejects_empty_retained_space() -> None:
    with pytest.raises(ValueError, match="zero retained rank"):
        solve_stabilized_generalized_eigenproblem(
            np.diag([-1.0, -0.5]).astype(complex),
            np.diag([1e-9, 5e-10]).astype(complex),
        )


@pytest.mark.parametrize(
    ("hamiltonian", "overlap"),
    [
        (np.array([[np.nan]], dtype=complex), np.eye(1, dtype=complex)),
        (np.eye(1, dtype=complex), np.array([[np.inf]], dtype=complex)),
    ],
)
def test_stabilized_generalized_eigenproblem_rejects_nonfinite_matrices(
    hamiltonian: np.ndarray,
    overlap: np.ndarray,
) -> None:
    with pytest.raises(ValueError, match="must contain only finite values"):
        solve_stabilized_generalized_eigenproblem(hamiltonian, overlap)
