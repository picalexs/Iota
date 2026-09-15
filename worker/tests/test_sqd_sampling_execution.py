"""Tests for the SQD sampling-execution boundary."""

from worker.chemistry.algorithms.sqd import sampling_execution as sqd_sampling_execution
from worker.chemistry.algorithms.sqd import workflow as sqd_solver


def test_solver_keeps_sampling_helpers_as_compatibility_aliases() -> None:
    assert sqd_solver._SQDIterationSampling is sqd_sampling_execution.SQDIterationSampling
    assert (
        sqd_solver._build_hf_reference_circuit is sqd_sampling_execution.build_hf_reference_circuit
    )
    assert sqd_solver._sample_bitstring_matrix is sqd_sampling_execution.sample_bitstring_matrix
    assert sqd_solver._run_sqd_sampler_attempt is sqd_sampling_execution._run_sampler_attempt
    assert (
        sqd_solver._is_control_flow_exception is sqd_sampling_execution._is_control_flow_exception
    )
