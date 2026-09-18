"""Tests for responsibility-specific run schema modules and compatibility exports."""

from app.schemas import run as compatibility
from app.schemas.run_config import BackendOptions
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
    assert BackendOptions().estimator_precision == 0.0
    assert BackendOptions(estimator_precision=0.125).estimator_precision == 0.125

    for invalid in (-0.1, float("nan"), float("inf")):
        try:
            BackendOptions(estimator_precision=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid precision to fail: {invalid!r}")


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
