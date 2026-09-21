"""Tests for responsibility-specific run schema modules and compatibility exports."""

from app.schemas import run as compatibility
from app.schemas.run_config import (
    BackendDerivedNoiseProfile,
    BackendOptions,
    ChemistryOptions,
    CustomPresetNoiseProfile,
)
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import RunResponse
from app.schemas.run_results import RunResultResponse


def test_run_schema_families_have_single_owning_modules() -> None:
    assert BackendOptions.__module__ == "app.schemas.run_config"
    assert RunCreate.__module__ == "app.schemas.run_requests"
    assert RunResponse.__module__ == "app.schemas.run_responses"
    assert RunResultResponse.__module__ == "app.schemas.run_results"


def test_legacy_run_imports_reexport_specific_schema_types() -> None:
    assert compatibility.BackendOptions is BackendOptions
    assert compatibility.RunCreate is RunCreate
    assert compatibility.RunResponse is RunResponse
    assert compatibility.RunResultResponse is RunResultResponse
    assert set(compatibility.__all__) == {
        name for name in compatibility.__dict__ if not name.startswith("_")
    } - {"annotations"}


def test_backend_options_validate_estimator_precision() -> None:
    assert BackendOptions().estimator_precision is None
    assert BackendOptions(estimator_precision=0.125).estimator_precision == 0.125

    for invalid in (-0.1, float("nan"), float("inf")):
        try:
            BackendOptions(estimator_precision=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid precision to fail: {invalid!r}")


def test_run_snapshot_omits_automatic_precision_but_keeps_explicit_exact() -> None:
    automatic = RunCreate(
        molecule_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        algorithm="vqe",
        mode="easy",
        backend_target="aer_simulator",
        noise_profile={
            "source": "custom_preset",
            "preset": "depolarizing_cx",
            "strength": 0.01,
        },
        easy_options={"goal": "balanced"},
    )
    automatic_options = automatic.snapshot_config()["backend_options"]
    assert "estimator_precision" not in automatic_options

    exact = automatic.model_copy(
        update={"backend_options": BackendOptions(estimator_precision=0.0)}
    )
    assert exact.snapshot_config()["backend_options"]["estimator_precision"] == 0.0


def test_backend_options_keep_aer_tuning_fields_optional_and_bounded() -> None:
    assert "device" not in BackendOptions().model_dump()
    options = BackendOptions(
        device="CPU",
        max_parallel_threads=4,
        aer_pub_chunk_size=4,
    )

    assert options.model_dump()["device"] == "CPU"
    assert options.model_dump()["max_parallel_threads"] == 4
    assert options.model_dump()["aer_pub_chunk_size"] == 4

    for field, value in (("max_parallel_threads", 0), ("aer_pub_chunk_size", 33)):
        try:
            BackendOptions(**{field: value})
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid {field} to fail: {value!r}")


def test_chemistry_options_keep_accelerators_optional_and_typed() -> None:
    assert ChemistryOptions().model_dump() == {}
    options = ChemistryOptions(reference_device="GPU", selected_ci_device="AUTO")
    assert options.model_dump() == {
        "reference_device": "GPU",
        "selected_ci_device": "AUTO",
    }


def test_noise_profiles_require_explicit_parameters_and_real_references() -> None:
    assert CustomPresetNoiseProfile(
        source="custom_preset",
        preset="readout_bias",
        p01=0.01,
        p10=0.02,
    ).model_dump(exclude_none=True) == {
        "source": "custom_preset",
        "preset": "readout_bias",
        "p01": 0.01,
        "p10": 0.02,
    }

    for payload in (
        {"source": "custom_preset", "preset": "readout_bias", "strength": 0.01},
        {
            "source": "custom_preset",
            "preset": "thermal_relaxation",
            "t1_us": 100,
            "t2_us": 250,
            "gate_time_us": 0.1,
        },
    ):
        try:
            CustomPresetNoiseProfile(**payload)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid noise profile to fail: {payload!r}")

    for reference_backend in ("aer_simulator", "statevector"):
        try:
            BackendDerivedNoiseProfile(
                source="backend_derived",
                reference_backend=reference_backend,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected simulator reference to fail: {reference_backend}")
