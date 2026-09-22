from __future__ import annotations

import json
from pathlib import Path

import pytest

from exporter.benchmark_io import ExporterError
from exporter.create_benchmark import create_campaign, validate_campaign


class FakeWriteApi:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []
        self.patches: list[tuple[str, dict]] = []

    def get(self, path: str) -> object:
        if path == "/api/molecules/molecule-1":
            return {"id": "molecule-1", "name": "H2", "formula": "H2"}
        raise AssertionError(path)

    def post(self, path: str, payload: dict) -> object:
        self.posts.append((path, payload))
        if path == "/api/benchmarks":
            return {"id": "benchmark-1", **payload}
        if path == "/api/runs":
            return {
                "id": f"run-{len([item for item in self.posts if item[0] == '/api/runs'])}",
                "status": "QUEUED",
            }
        raise AssertionError(path)

    def patch(self, path: str, payload: dict) -> object:
        self.patches.append((path, payload))
        return {"id": "benchmark-1", **payload}


def _manifest() -> dict:
    return {
        "name": "H2 seeds",
        "campaign_id": "h2-seeds",
        "molecules": [{"id": "molecule-1", "name": "H2", "key": "h2"}],
        "algorithms": [
            {
                "algorithm": "vqe",
                "mode": "advanced",
                "advanced_config": {
                    "algorithm": "vqe",
                    "ansatz_name": "NumberPreserving",
                    "optimizer_name": "COBYLA",
                    "max_iterations": 3,
                },
            }
        ],
        "seeds": [11, 17],
        "basis_set": "sto-3g",
        "backend": {"target": "statevector"},
    }


def test_campaign_expands_seeds_into_idempotent_runs_and_checkpoint(tmp_path: Path) -> None:
    api = FakeWriteApi()

    result = create_campaign(
        _manifest(),
        base_url="http://unused",
        output_dir=tmp_path,
        client=api,  # type: ignore[arg-type]
    )

    run_posts = [payload for path, payload in api.posts if path == "/api/runs"]
    assert result["submitted_count"] == 2
    assert len(run_posts) == 2
    assert run_posts[0]["advanced_config"]["seed"] == 11
    assert run_posts[1]["advanced_config"]["seed"] == 17
    assert run_posts[0]["client_request_id"] != run_posts[1]["client_request_id"]
    assert all(item["seedRoles"] == ["algorithm"] for item in api.patches[-1][1]["entries"])

    checkpoint = json.loads((tmp_path / "submission.json").read_text(encoding="utf-8"))
    assert checkpoint["benchmark_id"] == "benchmark-1"
    assert [item["run_id"] for item in checkpoint["entries"]] == ["run-1", "run-2"]
    assert (tmp_path / "campaign.json").is_file()
    assert (tmp_path / "benchmark.json").is_file()


def test_campaign_uses_automatic_noisy_aer_precision_by_default(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["backend"] = {
        "target": "aer_simulator",
        "name": "ibm_kyiv",
        "options": {"shots": 1024},
    }
    manifest["noise_profile"] = {
        "source": "backend_derived",
        "reference_backend": "ibm_kyiv",
    }

    api = FakeWriteApi()
    create_campaign(
        manifest,
        base_url="http://unused",
        output_dir=tmp_path,
        client=api,  # type: ignore[arg-type]
    )

    payload = next(payload for path, payload in api.posts if path == "/api/runs")
    options = payload["backend_options"]
    assert options["shots"] == 1024
    assert "estimator_precision" not in options
    assert payload["noise_profile"] == manifest["noise_profile"]


def test_campaign_can_seed_sqd_and_nested_sampling_vqe(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["algorithms"] = [
        {
            "algorithm": "sqd",
            "mode": "advanced",
            "seed_roles": ["algorithm", "sampling"],
            "advanced_config": {
                "algorithm": "sqd",
                "sampling_state_source": "vqe",
            },
        }
    ]
    manifest["seeds"] = [23]

    api = FakeWriteApi()
    create_campaign(
        manifest,
        base_url="http://unused",
        output_dir=tmp_path,
        client=api,  # type: ignore[arg-type]
    )

    payload = next(payload for path, payload in api.posts if path == "/api/runs")
    assert payload["advanced_config"]["seed"] == 23
    assert payload["advanced_config"]["sampling_vqe_seed"] == 23
    assert api.patches[-1][1]["entries"][0]["seedRoles"] == ["algorithm", "sampling"]


def test_campaign_can_seed_qse_vqe_reference(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["algorithms"] = [
        {
            "algorithm": "qse",
            "mode": "advanced",
            "advanced_config": {
                "algorithm": "qse",
                "reference_method": "vqe",
            },
        }
    ]
    manifest["seeds"] = [29]

    api = FakeWriteApi()
    create_campaign(
        manifest,
        base_url="http://unused",
        output_dir=tmp_path,
        client=api,  # type: ignore[arg-type]
    )

    payload = next(payload for path, payload in api.posts if path == "/api/runs")
    assert payload["advanced_config"]["vqe_reference_seed"] == 29
    assert api.patches[-1][1]["entries"][0]["seedRoles"] == ["reference"]


def test_campaign_rejects_incompatible_seed_roles(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["algorithms"] = [
        {
            "algorithm": "sqd",
            "mode": "advanced",
            "seed_roles": ["sampling"],
            "advanced_config": {"algorithm": "sqd", "sampling_state_source": "hf"},
        }
    ]
    with pytest.raises(ExporterError, match="sampling_state_source='vqe'"):
        create_campaign(
            manifest,
            base_url="http://unused",
            output_dir=tmp_path,
            client=FakeWriteApi(),  # type: ignore[arg-type]
        )


def test_campaign_rejects_unknown_seed_roles() -> None:
    manifest = _manifest()
    manifest["algorithms"] = [{"algorithm": "vqe", "seed_roles": ["random"]}]
    with pytest.raises(ExporterError, match="Unsupported seed role"):
        validate_campaign(manifest)


def test_campaign_resume_does_not_submit_runs_again(tmp_path: Path) -> None:
    first_api = FakeWriteApi()
    create_campaign(_manifest(), base_url="http://unused", output_dir=tmp_path, client=first_api)  # type: ignore[arg-type]

    second_api = FakeWriteApi()
    result = create_campaign(_manifest(), base_url="http://unused", output_dir=tmp_path, client=second_api)  # type: ignore[arg-type]

    assert result["submitted_count"] == 2
    assert not [payload for path, payload in second_api.posts if path == "/api/runs"]


def test_algorithm_seed_requires_advanced_config(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["algorithms"] = [{"algorithm": "vqe", "seed_roles": ["algorithm"]}]
    with pytest.raises(ExporterError, match="algorithm seeds require mode=advanced"):
        create_campaign(
            manifest,
            base_url="http://unused",
            output_dir=tmp_path,
            client=FakeWriteApi(),  # type: ignore[arg-type]
        )


def test_ibm_submission_requires_explicit_opt_in(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["backend"] = {"target": "ibm_runtime"}
    with pytest.raises(ExporterError, match="IBM Runtime submission is disabled"):
        create_campaign(
            manifest,
            base_url="http://unused",
            output_dir=tmp_path,
            client=FakeWriteApi(),  # type: ignore[arg-type]
        )


def test_manifest_rejects_duplicate_seeds() -> None:
    manifest = _manifest()
    manifest["seeds"] = [11, 11]
    with pytest.raises(ExporterError, match="Duplicate seed"):
        validate_campaign(manifest)
