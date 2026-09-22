from __future__ import annotations

from quantum_diag.run_benchmark_demo import build_profile_matrix_config, parse_args


def test_profile_smoke_defaults() -> None:
    profile = build_profile_matrix_config("smoke")
    assert profile["methods"] == ["VQE", "KQD", "SQD"]
    assert profile["molecules"] == ["H2", "LiH"]
    assert profile["ansatz_types"] == ["RealAmplitudes"]
    assert profile["optimizers"] == ["COBYLA"]


def test_parse_args_profile_override_methods() -> None:
    args = parse_args([
        "--profile",
        "smoke",
        "--methods",
        "VQE,QFD",
        "--molecules",
        "H2",
        "--seeds",
        "11",
        "--max-iterations",
        "5",
    ])

    assert args.methods == ["VQE", "QFD"]
    assert args.molecules == ["H2"]
    assert args.seeds == [11]
    assert args.max_iterations == 5
    assert args.ansatz_types == ["RealAmplitudes"]
    assert args.optimizers == ["COBYLA"]
