"""Optional selected-CI backends for SQD."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable

import numpy as np
from packaging.version import Version

from worker.chemistry.accelerators import normalize_chemistry_device
from worker.chemistry.sector_basis import sector_dimension


@dataclass(frozen=True)
class SelectedCIResolution:
    """Resolved selected-CI provider and device."""

    solve_fermion: Callable[..., tuple[float, Any, tuple[np.ndarray, np.ndarray], float]]
    requested_device: str
    actual_device: str
    provider: str
    fallback_reason: str | None = None


def _sbd_addon_compatibility_error() -> str | None:
    """Return a clear error when the SQD/SBD integration contract is too old."""
    try:
        addon_version = Version(version("qiskit-addon-sqd"))
    except PackageNotFoundError:
        return "qiskit-addon-sqd is not installed"
    if addon_version < Version("0.13.1"):
        return f"qiskit-addon-sqd {addon_version} is too old; SBD requires >= 0.13.1"
    return None


def _sbd_gpu_backend(sbd: Any) -> str | None:
    """Return the first supported SBD GPU backend."""
    available = {str(value).lower() for value in sbd.available_backends()}
    if "gpu" in available:
        return "gpu"
    if "gpu-omp" in available:
        return "gpu-omp"
    return None


def _sbd_device_config(device_config_type: Any, backend: str) -> Any:
    """Build the SBD device configuration for the selected backend."""
    if backend == "gpu":
        factory = getattr(device_config_type, "gpu", None)
    else:
        factory = getattr(device_config_type, "gpu_omp", None)
    if not callable(factory):
        raise RuntimeError(
            f"SBD exposes {backend!r}, but its DeviceConfig does not provide the matching GPU config"
        )
    return factory()


def _sbd_solver_config(solver_options: dict[str, Any]) -> dict[str, Any]:
    """Translate qiskit-addon-sqd options to the SBD solver configuration."""
    nested = solver_options.pop("sbd_config", None)
    if nested is not None and not isinstance(nested, dict):
        raise ValueError("SQD sbd_config must be an object when provided")
    config = {
        "method": 0,
        "eps": 1e-8,
        "max_it": 50,
    }
    if isinstance(nested, dict):
        config.update(nested)
    if "max_cycle" in solver_options:
        config["max_it"] = int(solver_options.pop("max_cycle"))
    if solver_options:
        unknown = ", ".join(sorted(solver_options))
        raise ValueError(f"SBD selected-CI does not support solver options: {unknown}")
    return config


def _spin_square_from_sci_state(sci_state: Any, *, norb: int, nelec: tuple[int, int]) -> float:
    """Read spin square from an SCI state, with a ffsim compatibility fallback."""
    spin_square = getattr(sci_state, "spin_square", None)
    if callable(spin_square):
        return float(spin_square())

    amplitudes = np.asarray(getattr(sci_state, "amplitudes"), dtype=complex)
    strings_a = np.asarray(getattr(sci_state, "ci_strs_a"), dtype=np.int64)
    strings_b = np.asarray(getattr(sci_state, "ci_strs_b"), dtype=np.int64)
    if amplitudes.shape != (len(strings_a), len(strings_b)):
        raise ValueError("SBD returned an SCI state with inconsistent determinant dimensions")

    import ffsim

    state = np.zeros(sector_dimension(norb, nelec), dtype=complex)
    for alpha_index, alpha_string in enumerate(strings_a):
        for beta_index, beta_string in enumerate(strings_b):
            display_string = format(int(beta_string), f"0{norb}b") + format(
                int(alpha_string), f"0{norb}b"
            )
            address = int(ffsim.strings_to_addresses([display_string], norb, nelec)[0])
            state[address] = amplitudes[alpha_index, beta_index]
    norm = np.linalg.norm(state)
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("SBD returned an SCI state with no finite amplitude")
    return float(ffsim.spin_square(state / norm, norb, nelec))


def _build_sbd_solver(sbd: Any, *, backend: str, device_config_type: Any) -> Callable[..., Any]:
    """Adapt SBD's batch solver to the SQD ``solve_fermion`` contract."""
    from sbd.sbd_solver import solve_sci_batch

    device_config = _sbd_device_config(device_config_type, backend)

    def solve_fermion(
        ci_strings: tuple[np.ndarray, np.ndarray],
        hcore: np.ndarray,
        eri: np.ndarray,
        *,
        open_shell: bool = False,
        spin_sq: float | None = None,
        **solver_options: Any,
    ) -> tuple[float, Any, tuple[np.ndarray, np.ndarray], float]:
        del open_shell
        options = dict(solver_options)
        sbd_config = _sbd_solver_config(options)
        strings_a, strings_b = ci_strings
        if len(strings_a) == 0 or len(strings_b) == 0:
            raise ValueError("SBD selected-CI requires non-empty alpha and beta determinant sets")
        norb = int(np.asarray(hcore).shape[0])
        nelec = (
            int(int(strings_a[0]).bit_count()),
            int(int(strings_b[0]).bit_count()),
        )
        results = solve_sci_batch(
            [(np.asarray(strings_a, dtype=np.int64), np.asarray(strings_b, dtype=np.int64))],
            np.asarray(hcore),
            np.asarray(eri),
            norb,
            nelec,
            spin_sq=spin_sq,
            sbd_config=sbd_config,
            device_config=device_config,
        )
        if len(results) != 1:
            raise RuntimeError(f"SBD returned {len(results)} selected-CI results for one batch")
        result = results[0]
        sci_state = result.sci_state
        occupancies = tuple(np.asarray(value) for value in result.orbital_occupancies)
        return (
            float(result.energy),
            sci_state,
            (occupancies[0], occupancies[1]),
            _spin_square_from_sci_state(sci_state, norb=norb, nelec=nelec),
        )

    return solve_fermion


def resolve_selected_ci_solver(
    cpu_solver: Callable[..., tuple[float, Any, tuple[np.ndarray, np.ndarray], float]],
    requested_device: str | None,
) -> SelectedCIResolution:
    """Resolve CPU selected-CI or an optional SBD GPU provider."""
    requested = normalize_chemistry_device(requested_device)
    cpu_resolution = SelectedCIResolution(
        solve_fermion=cpu_solver,
        requested_device=requested,
        actual_device="CPU",
        provider="qiskit_addon_sqd",
    )
    if requested == "CPU":
        return cpu_resolution

    try:
        import sbd
        from sbd.device_config import DeviceConfig

        backend = _sbd_gpu_backend(sbd)
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError) as exc:
        backend = None
        import_error = exc
    else:
        import_error = None

    compatibility_error = _sbd_addon_compatibility_error() if backend is not None else None
    if compatibility_error is not None:
        backend = None
        import_error = RuntimeError(compatibility_error)

    if backend is None:
        reason = (
            "SBD with a compiled GPU backend is not installed"
            if import_error is None
            else f"SBD GPU provider is unavailable: {import_error}"
        )
        if requested == "GPU":
            raise RuntimeError(
                "GPU selected-CI was requested, but "
                f"{reason}. Install SBD in a compatible MPI/NVHPC GPU environment."
            )
        return SelectedCIResolution(
            **{**cpu_resolution.__dict__, "fallback_reason": reason}
        )

    try:
        solver = _build_sbd_solver(sbd, backend=backend, device_config_type=DeviceConfig)
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError) as exc:
        if requested == "GPU":
            raise RuntimeError(f"GPU selected-CI could not initialize SBD: {exc}") from exc
        return SelectedCIResolution(
            **{
                **cpu_resolution.__dict__,
                "fallback_reason": f"SBD GPU provider could not initialize: {exc}",
            }
        )
    return SelectedCIResolution(
        solve_fermion=solver,
        requested_device=requested,
        actual_device="GPU",
        provider=f"sbd:{backend}",
    )
