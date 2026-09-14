"""Mode and algorithm/config alignment policies for run validation."""

from __future__ import annotations

from app.models.enums import RunMode
from app.schemas.run_requests import RunCreate
from app.schemas.run_responses import (
    RunValidationErrorDetail,
    ValidationErrorCode,
)

__all__ = [
    "_append_advanced_config_alignment_messages",
    "_append_mode_validation_messages",
]


def _append_mode_validation_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
) -> None:
    if payload.mode == RunMode.EASY:
        if payload.easy_options is None:
            errors.append(
                RunValidationErrorDetail(
                    field="easy_options",
                    code=ValidationErrorCode.MISSING_REQUIRED,
                    message="easy_options is required when mode=easy",
                )
            )
        if payload.advanced_config is not None:
            errors.append(
                RunValidationErrorDetail(
                    field="advanced_config",
                    code=ValidationErrorCode.UNSUPPORTED_OPTION,
                    message="advanced_config is not allowed when mode=easy",
                )
            )

    if payload.mode == RunMode.ADVANCED:
        if payload.advanced_config is None:
            errors.append(
                RunValidationErrorDetail(
                    field="advanced_config",
                    code=ValidationErrorCode.MISSING_REQUIRED,
                    message="advanced_config is required when mode=advanced",
                )
            )
        if payload.easy_options is not None:
            errors.append(
                RunValidationErrorDetail(
                    field="easy_options",
                    code=ValidationErrorCode.UNSUPPORTED_OPTION,
                    message="easy_options is not allowed when mode=advanced",
                )
            )


def _append_advanced_config_alignment_messages(
    payload: RunCreate,
    *,
    errors: list[RunValidationErrorDetail],
) -> None:
    if payload.advanced_config is not None and payload.algorithm is not None:
        if payload.advanced_config.algorithm != payload.algorithm:
            errors.append(
                RunValidationErrorDetail(
                    field="advanced_config.algorithm",
                    code=ValidationErrorCode.INCOMPATIBLE_BACKEND,
                    message="advanced_config.algorithm must match top-level algorithm",
                )
            )
