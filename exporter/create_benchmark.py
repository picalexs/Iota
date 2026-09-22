#!/usr/bin/env python3
"""Create a real QSS benchmark campaign from a compact JSON manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlencode

try:
    from .benchmark_io import ExporterError, QssApiClient
except ImportError:  # pragma: no cover - direct script execution
    from benchmark_io import ExporterError, QssApiClient


SUPPORTED_ALGORITHMS = {"vqe", "qse", "kqd", "qfd", "sqd", "skqd"}
SUPPORTED_BACKENDS = {"statevector", "aer_simulator", "ibm_runtime"}
ALGORITHM_SEED_ALGORITHMS = {"vqe", "sqd", "skqd"}
SEED_ROLES = {"algorithm", "sampling", "reference", "simulator", "transpiler"}
DEFAULT_BASE_URL = "http://localhost:18000"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "qss-campaign"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExporterError(f"Cannot read campaign manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExporterError(f"Campaign manifest must contain a JSON object: {path}")
    return value


def _as_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ExporterError(f"Campaign field '{field}' must be a non-empty list")
    return list(value)


def _validate_seed_list(value: Any) -> list[int]:
    seeds = _as_list(value, field="seeds")
    result: list[int] = []
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed > 2**32 - 1:
            raise ExporterError("Campaign seeds must be integers in [0, 2**32 - 1]")
        if seed in result:
            raise ExporterError(f"Duplicate seed in campaign: {seed}")
        result.append(seed)
    return result


def _molecule_key(molecule: Mapping[str, Any]) -> str:
    return _text(molecule.get("key")) or _text(molecule.get("id")) or _text(molecule.get("name")) or "molecule"


def _normalize_molecules(value: Any) -> list[dict[str, Any]]:
    molecules = _as_list(value, field="molecules")
    result: list[dict[str, Any]] = []
    for item in molecules:
        if isinstance(item, str):
            name = _text(item)
            if name is None:
                raise ExporterError("Campaign molecule names cannot be empty")
            result.append({"name": name})
            continue
        if not isinstance(item, Mapping):
            raise ExporterError("Each campaign molecule must be a name or object")
        molecule = dict(item)
        if _molecule_key(molecule) == "molecule":
            raise ExporterError("Each campaign molecule needs an id or name")
        result.append(molecule)
    return result


def _normalize_variants(value: Any) -> list[dict[str, Any]]:
    variants = _as_list(value, field="algorithms")
    result: list[dict[str, Any]] = []
    for item in variants:
        if isinstance(item, str):
            result.append({"algorithm": item})
            continue
        if not isinstance(item, Mapping):
            raise ExporterError("Each campaign algorithm must be a name or object")
        variant = dict(item)
        algorithm = _text(variant.get("algorithm"))
        if algorithm is None:
            raise ExporterError("Each algorithm variant needs an algorithm")
        result.append(variant)
    return result


def _variant_key(variant: Mapping[str, Any]) -> str:
    """Return the stable manifest key used to distinguish configuration variants."""

    algorithm = _text(variant.get("algorithm")) or "algorithm"
    explicit = _text(
        variant.get("id", variant.get("variant_id", variant.get("variantId")))
    )
    if explicit is not None:
        return _slug(explicit)
    mode = _text(variant.get("mode")) or ("advanced" if variant.get("advanced_config") else "easy")
    return _slug(f"{algorithm}-{mode}")


def validate_campaign(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the user-facing campaign manifest."""

    name = _text(manifest.get("name"))
    if name is None:
        raise ExporterError("Campaign field 'name' is required")
    campaign_id = _text(manifest.get("campaign_id", manifest.get("campaignId"))) or _slug(name)
    seeds = _validate_seed_list(manifest.get("seeds"))
    molecules = _normalize_molecules(manifest.get("molecules"))
    variants = _normalize_variants(manifest.get("algorithms"))

    basis = _text(manifest.get("basis_set", manifest.get("basisSet"))) or "sto-3g"
    backend = dict(manifest.get("backend") or {})
    target = _text(backend.get("target", manifest.get("backend_target", "statevector")))
    if target not in SUPPORTED_BACKENDS:
        raise ExporterError(f"Unsupported backend target: {target}")
    backend_options = dict(backend.get("options") or manifest.get("backend_options") or {})
    if backend.get("name") is not None:
        backend_options.setdefault("backend_name", backend["name"])
    noise_profile = manifest.get("noise_profile")
    if noise_profile is not None and not isinstance(noise_profile, Mapping):
        raise ExporterError("Campaign noise_profile must be an object")

    for variant in variants:
        algorithm = str(variant["algorithm"]).lower()
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise ExporterError(f"Unsupported algorithm: {algorithm}")
        mode = _text(variant.get("mode")) or ("advanced" if variant.get("advanced_config") else "easy")
        if mode not in {"easy", "advanced"}:
            raise ExporterError(f"Unsupported mode for {algorithm}: {mode}")
        variant["algorithm"] = algorithm
        variant["mode"] = mode
        if "noise_profile" not in variant and noise_profile is not None:
            variant["noise_profile"] = dict(noise_profile)
        _seed_roles(algorithm, variant, target)

    variant_keys = [_variant_key(variant) for variant in variants]
    duplicates = sorted({key for key in variant_keys if variant_keys.count(key) > 1})
    if duplicates:
        raise ExporterError(
            "Algorithm variants need unique id values when repeated: "
            + ", ".join(duplicates)
        )

    return {
        "name": name,
        "campaign_id": campaign_id,
        "molecules": molecules,
        "algorithms": variants,
        "seeds": seeds,
        "basis_set": basis,
        "backend": {
            "target": target,
            "name": _text(backend_options.get("backend_name")),
            "options": backend_options,
        },
        "chemical_accuracy_target_ha": manifest.get(
            "chemical_accuracy_target_ha", manifest.get("chemicalAccuracyHa")
        ),
        "acquire_molecules": bool(manifest.get("acquire_molecules", False)),
        "metadata": dict(manifest.get("metadata") or {}),
    }


def _resolve_molecule(
    api: QssApiClient,
    molecule: Mapping[str, Any],
    *,
    acquire: bool,
) -> dict[str, Any]:
    molecule_id = _text(molecule.get("id"))
    if molecule_id:
        response = api.get(f"/api/molecules/{quote(molecule_id, safe='')}")
        if not isinstance(response, Mapping) or not _text(response.get("id")):
            raise ExporterError(f"Molecule lookup returned an invalid object: {molecule_id}")
        return dict(response)

    name = _text(molecule.get("name"))
    if name is None:
        raise ExporterError("Molecule needs an id or name")
    query = urlencode({"q": name, "limit": 200})
    response = api.get(f"/api/molecules?{query}")
    items = response.get("items", []) if isinstance(response, Mapping) else []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, Mapping) and str(item.get("name", "")).casefold() == name.casefold():
                return dict(item)

    if not acquire:
        raise ExporterError(
            f"Molecule '{name}' was not found. Add its id or set acquire_molecules=true."
        )
    imported = api.post("/api/molecules/pubchem/import", {"name": name})
    if not isinstance(imported, Mapping) or not _text(imported.get("id")):
        raise ExporterError(f"Molecule acquisition returned an invalid object: {name}")
    return dict(imported)


def _seed_roles(algorithm: str, variant: Mapping[str, Any], backend_target: str) -> list[str]:
    roles = variant.get("seed_roles")
    if roles is not None:
        if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
            raise ExporterError(f"seed_roles for {algorithm} must be a list of strings")
        normalized = [item.strip().lower() for item in roles if item.strip()]
        unknown = sorted(set(normalized) - SEED_ROLES)
        if unknown:
            raise ExporterError(
                f"Unsupported seed role(s) for {algorithm}: {', '.join(unknown)}"
            )
        if len(normalized) != len(set(normalized)):
            raise ExporterError(f"Duplicate seed role for {algorithm}")
        return normalized
    if algorithm in ALGORITHM_SEED_ALGORITHMS and variant.get("mode") == "advanced":
        return ["algorithm"]
    if backend_target == "ibm_runtime":
        return ["transpiler"]
    if (
        algorithm == "qse"
        and variant.get("mode") == "advanced"
        and str((variant.get("advanced_config") or {}).get("reference_method", "")).lower()
        == "vqe"
    ):
        return ["reference"]
    return ["simulator", "transpiler"]


def _build_seeded_config(
    *,
    campaign: Mapping[str, Any],
    molecule: Mapping[str, Any],
    variant: Mapping[str, Any],
    seed: int,
    client_request_id: str,
) -> tuple[dict[str, Any], list[str]]:
    algorithm = str(variant["algorithm"]).lower()
    backend = dict(campaign["backend"])
    backend_target = str(backend["target"])
    roles = _seed_roles(algorithm, variant, backend_target)
    if backend_target == "ibm_runtime" and "simulator" in roles:
        raise ExporterError("IBM Runtime campaigns cannot use simulator seed roles")
    if "algorithm" in roles and algorithm not in ALGORITHM_SEED_ALGORITHMS:
        raise ExporterError(f"{algorithm} has no exposed algorithm-level seed field")
    if "algorithm" in roles and variant.get("mode") != "advanced":
        raise ExporterError(
            f"{algorithm} algorithm seeds require mode=advanced with advanced_config"
        )
    if (
        any(role in roles for role in {"sampling", "reference"})
        and variant.get("mode") != "advanced"
    ):
        raise ExporterError(
            f"{algorithm} sampling and reference seeds require mode=advanced with advanced_config"
        )
    advanced_variant = dict(variant.get("advanced_config") or {})
    if "sampling" in roles:
        if algorithm != "sqd":
            raise ExporterError(f"{algorithm} has no exposed nested sampling seed field")
        if str(advanced_variant.get("sampling_state_source", "hf")).lower() != "vqe":
            raise ExporterError(
                "SQD sampling seed requires advanced_config.sampling_state_source='vqe'"
            )
    if "reference" in roles:
        if algorithm != "qse":
            raise ExporterError(f"{algorithm} has no exposed reference seed field")
        if str(advanced_variant.get("reference_method", "")).lower() != "vqe":
            raise ExporterError(
                "QSE reference seed requires advanced_config.reference_method='vqe'"
            )

    backend_options = {
        "selection_policy": "manual",
        "backend_name": backend.get("name"),
        "shots": 4096,
        "optimization_level": 1,
        "seed_simulator": None,
        "seed_transpiler": None,
        "aer_method": "automatic",
    }
    backend_options.update(dict(backend.get("options") or {}))
    if "simulator" in roles:
        backend_options["seed_simulator"] = seed
    if "transpiler" in roles:
        backend_options["seed_transpiler"] = seed

    config: dict[str, Any] = {
        "molecule_id": str(molecule["id"]),
        "client_request_id": client_request_id,
        "algorithm": algorithm,
        "mode": variant.get("mode", "easy"),
        "backend_target": backend_target,
        "backend_options": backend_options,
        "basis_set_override": campaign["basis_set"],
        "ibm_runtime_confirmed": bool(variant.get("ibm_runtime_confirmed", False)),
    }
    if campaign.get("chemical_accuracy_target_ha") is not None:
        config["chemical_accuracy_target_ha"] = campaign["chemical_accuracy_target_ha"]

    if config["mode"] == "easy":
        config["easy_options"] = dict(variant.get("easy_options") or {"goal": "balanced"})
    else:
        advanced = advanced_variant
        advanced.setdefault("algorithm", algorithm)
        if "algorithm" in roles:
            if algorithm == "skqd":
                sampling = dict(advanced.get("base_sampling_options") or {})
                sampling["seed"] = seed
                advanced["base_sampling_options"] = sampling
            else:
                advanced["seed"] = seed
        if "sampling" in roles:
            advanced["sampling_vqe_seed"] = seed
        if "reference" in roles:
            advanced["vqe_reference_seed"] = seed
        config["advanced_config"] = advanced

    if variant.get("noise_profile") is not None:
        config["noise_profile"] = dict(variant["noise_profile"])
    return config, roles


def _entry_id(
    molecule: Mapping[str, Any], variant: Mapping[str, Any], seed: int
) -> str:
    return f"{_slug(_molecule_key(molecule))}:{_variant_key(variant)}:seed={seed}"


def _entry_snapshot(
    *,
    entry_id: str,
    molecule: Mapping[str, Any],
    variant: Mapping[str, Any],
    seed: int,
    seed_roles: list[str],
    status: str = "planned",
    run_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    variant_key = _variant_key(variant)
    variant_label = _text(variant.get("label")) or variant_key
    return {
        "id": entry_id,
        "preset": {
            "key": _molecule_key(molecule),
            "name": _text(molecule.get("name")) or _molecule_key(molecule),
            "formula": _text(molecule.get("formula")),
        },
        "algorithm": variant["algorithm"],
        "variantId": f"{variant_key}:seed={seed}",
        "variantLabel": f"{variant_label} seed={seed}",
        "mode": variant.get("mode", "easy"),
        "status": status,
        "moleculeId": molecule.get("id"),
        "runId": run_id,
        "seed": seed,
        "seedRoles": seed_roles,
        "energy": None,
        "currentEnergy": None,
        "converged": None,
        "errorMessage": error_message,
        "latestEventSequence": 0,
    }


def _campaign_entries(campaign: Mapping[str, Any], molecules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for molecule in molecules:
        for variant in campaign["algorithms"]:
            for seed in campaign["seeds"]:
                algorithm = str(variant["algorithm"])
                roles = _seed_roles(algorithm, variant, campaign["backend"]["target"])
                entry_id = _entry_id(molecule, variant, seed)
                entries.append(
                    {
                        "entry_id": entry_id,
                        "molecule": molecule,
                        "variant": variant,
                        "seed": seed,
                        "seed_roles": roles,
                        "snapshot": _entry_snapshot(
                            entry_id=entry_id,
                            molecule=molecule,
                            variant=variant,
                            seed=seed,
                            seed_roles=roles,
                        ),
                    }
                )
    return entries


def _benchmark_payload(campaign: Mapping[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    selected_molecule_keys = list(dict.fromkeys(_molecule_key(item["molecule"]) for item in entries))
    selected_algorithms = list(dict.fromkeys(item["variant"]["algorithm"] for item in entries))
    backend = campaign["backend"]
    return {
        "name": campaign["name"],
        "campaignId": campaign["campaign_id"],
        "campaignMetadata": {
            "schema_version": "campaign.v1",
            "seed_count": len(campaign["seeds"]),
            "seed_values": campaign["seeds"],
            "source": "exporter/create_benchmark.py",
            **campaign.get("metadata", {}),
        },
        "selectedMoleculeKeys": selected_molecule_keys,
        "selectedAlgorithms": selected_algorithms,
        "selectedBasis": campaign["basis_set"],
        "selectedBackendMode": backend["target"],
        "selectedBackendName": backend.get("name"),
        "chemicalAccuracyHa": campaign.get("chemical_accuracy_target_ha") or 1.6e-3,
        "customMolecules": [],
        "entries": [item["snapshot"] for item in entries],
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExporterError(f"Cannot read checkpoint {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExporterError(f"Checkpoint must contain an object: {path}")
    return value


def _status_for_run(value: Any) -> str:
    return str(value or "created").strip().lower()


def _wait_for_runs(
    api: QssApiClient,
    entries: list[dict[str, Any]],
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    pending = {item["run_id"] for item in entries if item.get("run_id")}
    while pending and time.monotonic() < deadline:
        for item in entries:
            run_id = item.get("run_id")
            if not run_id or run_id not in pending:
                continue
            response = api.get(f"/api/runs/{run_id}")
            if not isinstance(response, Mapping):
                raise ExporterError(f"Run status response is invalid: {run_id}")
            status = _status_for_run(response.get("status"))
            item["status"] = status
            item["snapshot"]["status"] = status
            if status in {"completed", "failed", "cancelled", "excluded"}:
                pending.remove(run_id)
        if pending:
            time.sleep(max(0.1, poll_seconds))
    if pending:
        raise ExporterError(
            f"Timed out waiting for {len(pending)} run(s): {', '.join(sorted(pending))}"
        )


def create_campaign(
    manifest: Mapping[str, Any],
    *,
    base_url: str,
    output_dir: Path,
    timeout: float = 30.0,
    wait: bool = False,
    wait_timeout: float = 3600.0,
    poll_seconds: float = 5.0,
    allow_ibm: bool = False,
    client: QssApiClient | None = None,
) -> dict[str, Any]:
    campaign = validate_campaign(manifest)
    if campaign["backend"]["target"] == "ibm_runtime" and not allow_ibm:
        raise ExporterError(
            "IBM Runtime submission is disabled. Pass --allow-ibm only for an explicitly approved workload."
        )

    api = client or QssApiClient(base_url, timeout=timeout)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "submission.json"
    checkpoint = _load_checkpoint(checkpoint_path)

    if checkpoint is not None:
        if checkpoint.get("campaign_id") != campaign["campaign_id"]:
            raise ExporterError("Existing submission checkpoint belongs to another campaign")
        benchmark_id = _text(checkpoint.get("benchmark_id"))
        items = list(checkpoint.get("entries") or [])
        if not benchmark_id or not items:
            raise ExporterError(f"Checkpoint is incomplete: {checkpoint_path}")
        molecules = list(checkpoint.get("molecules") or [])
    else:
        molecules = [_resolve_molecule(api, molecule, acquire=campaign["acquire_molecules"]) for molecule in campaign["molecules"]]
        entries = _campaign_entries(campaign, molecules)
        payload = _benchmark_payload(campaign, entries)
        benchmark = api.post("/api/benchmarks", payload)
        if not isinstance(benchmark, Mapping) or not _text(benchmark.get("id")):
            raise ExporterError("Benchmark creation returned no benchmark ID")
        benchmark_id = str(benchmark["id"])
        items = []
        for item in entries:
            request_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"qss:{campaign['campaign_id']}:{item['entry_id']}")
            )
            run_config, seed_roles = _build_seeded_config(
                campaign=campaign,
                molecule=item["molecule"],
                variant=item["variant"],
                seed=item["seed"],
                client_request_id=request_id,
            )
            item["seed_roles"] = seed_roles
            item["snapshot"]["seedRoles"] = seed_roles
            items.append(
                {
                    "entry_id": item["entry_id"],
                    "seed": item["seed"],
                    "seed_roles": seed_roles,
                    "snapshot": item["snapshot"],
                    "run_config": run_config,
                    "run_id": None,
                    "status": "planned",
                    "error_message": None,
                }
            )
        checkpoint = {
            "schema_version": "qss-campaign.v1",
            "campaign_id": campaign["campaign_id"],
            "benchmark_id": benchmark_id,
            "molecules": molecules,
            "entries": items,
        }
        _write_json(output_dir / "campaign.json", campaign)
        _write_json(output_dir / "benchmark.json", dict(benchmark))
        _write_json(checkpoint_path, checkpoint)

    snapshot_entries = [item["snapshot"] for item in items]
    for item in items:
        if item.get("run_id"):
            continue
        try:
            run = api.post("/api/runs", item["run_config"])
            if not isinstance(run, Mapping) or not _text(run.get("id")):
                raise ExporterError(f"Run creation returned no run ID for {item['entry_id']}")
            item["run_id"] = str(run["id"])
            item["status"] = _status_for_run(run.get("status"))
            item["snapshot"]["runId"] = item["run_id"]
            item["snapshot"]["status"] = item["status"]
        except ExporterError as exc:
            item["status"] = "failed"
            item["error_message"] = str(exc)
            item["snapshot"]["status"] = "failed"
            item["snapshot"]["errorMessage"] = str(exc)
        checkpoint["entries"] = items
        _write_json(checkpoint_path, checkpoint)
        try:
            api.patch(f"/api/benchmarks/{benchmark_id}", {"entries": [entry["snapshot"] for entry in items]})
        except ExporterError as exc:
            raise ExporterError(
                f"Run checkpoint saved, but benchmark snapshot update failed: {exc}"
            ) from exc

    if wait:
        _wait_for_runs(
            api,
            items,
            timeout_seconds=wait_timeout,
            poll_seconds=poll_seconds,
        )
        checkpoint["entries"] = items
        _write_json(checkpoint_path, checkpoint)
        api.patch(f"/api/benchmarks/{benchmark_id}", {"entries": [entry["snapshot"] for entry in items]})

    checkpoint["entries"] = items
    _write_json(checkpoint_path, checkpoint)
    failed = [item for item in items if item.get("status") == "failed"]
    result = {
        "benchmark_id": benchmark_id,
        "campaign_id": campaign["campaign_id"],
        "output_dir": str(output_dir),
        "submitted_count": sum(1 for item in items if item.get("run_id")),
        "failed_count": len(failed),
        "entry_count": len(items),
    }
    _write_json(output_dir / "submission_summary.json", result)
    if failed:
        raise ExporterError(f"{len(failed)} campaign entry/entries failed; checkpoint retained")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit and save a QSS benchmark campaign.")
    parser.add_argument("campaign_file", type=Path, help="JSON campaign manifest.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"QSS API base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--output-dir", type=Path, default=None, help="Checkpoint directory. Default: output/campaign_id.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    parser.add_argument("--wait", action="store_true", help="Wait for submitted runs to reach terminal states.")
    parser.add_argument("--wait-timeout", type=float, default=3600.0, help="Maximum wait time in seconds.")
    parser.add_argument("--poll-seconds", type=float, default=5.0, help="Run status polling interval.")
    parser.add_argument("--allow-ibm", action="store_true", help="Allow an explicitly configured IBM Runtime campaign.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = _read_json(args.campaign_file.expanduser().resolve())
        campaign = validate_campaign(manifest)
        output_dir = args.output_dir or Path("output") / campaign["campaign_id"]
        result = create_campaign(
            manifest,
            base_url=args.base_url,
            output_dir=output_dir,
            timeout=max(0.1, args.timeout),
            wait=args.wait,
            wait_timeout=max(0.1, args.wait_timeout),
            poll_seconds=max(0.1, args.poll_seconds),
            allow_ibm=args.allow_ibm,
        )
    except ExporterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
